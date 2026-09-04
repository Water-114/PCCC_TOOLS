"""Gọi AI provider để đọc bản vẽ (ảnh/PDF) và parse JSON trả về — dùng chung
cho mọi hạng mục rà soát MĐC (báo cháy, điện PCCC, ...). Ghi 1 dòng log cho
MỖI lần gọi AI (provider, model, phiên bản system prompt, thời gian xử lý,
usage) — Batch 4 sub-bước 2.
"""

import base64
import hashlib
import json
import logging
import time

from ..providers.resilience import CircuitBreakerOpen
from .ai_schema import SchemaValidationError

# Dung logger chuan (khong phai current_app.logger) vi ccnuoc_reader goi ham nay
# tu ben trong ThreadPoolExecutor - app context cua Flask la thread-local, KHONG
# tu dong co san trong cac worker thread do executor tao ra (da xac nhan bang
# script thu rieng: current_app.logger.* trong worker thread nem RuntimeError
# "Working outside of application context"). Logger ten "app.services.ai_reader_common"
# la con chau cua logger "app" (ten Flask app trong create_app()) trong logging
# hierarchy nen van chui qua dung handler/level Flask da cau hinh, khong can context.
logger = logging.getLogger(__name__)


class AIReaderError(Exception):
    pass


# Checklist "phát hiện mâu thuẫn logic nội bộ" (nhóm kiến nghị II) — dịch từ
# đúng Bước 3 của skill /ra-mau-doi-chieu-pccc. TRƯỚC bản này, cả 4 reader chỉ
# nói chung chung "nhóm II chỉ dùng khi có căn cứ rõ ràng" mà không có checklist
# cụ thể để AI chủ động đối chiếu chéo, khiến nhóm II gần như luôn để trống
# trong thực tế — dùng CHUNG 1 nguồn cho cả 4 reader (baochay/dienpccc/ccnuoc/
# densucco) để tránh 4 bản lệch nhau theo thời gian; ghép trực tiếp vào system
# prompt của từng reader, ngay sau bullet liệt kê 4 nhóm kiến nghị.
NHOM_II_MAU_THUAN_CHECKLIST = """
KIỂM TRA MÂU THUẪN LOGIC NỘI BỘ (nhóm II — "chưa thống nhất giữa nhiều nguồn số liệu"): CHỈ áp dụng khi bản vẽ ĐANG ĐỌC thực sự chứa ÍT NHẤT 2 nguồn số liệu độc lập để đối chiếu chéo (ví dụ vừa có mặt bằng vừa có bảng thống kê/bảng tính trong CÁC file đã đính cho lần đọc này) — nếu chỉ có 1 nguồn thông tin thì KHÔNG suy đoán, để mảng nhóm II rỗng như bình thường. Khi có đủ ít nhất 2 nguồn, chủ động đối chiếu chéo các loại mâu thuẫn sau:
1. Tổng số thiết bị đếm/cộng dồn từ mặt bằng KHÁC số liệu ghi trong bảng thống kê/bảng tính (nếu bản vẽ có cả 2 loại).
2. Thông số ghi trên sơ đồ nguyên lý KHÁC mặt bằng KHÁC ghi chú/thuyết minh (ví dụ: số loop/zone, cột áp bơm, dung tích bể, đường kính ống... tuỳ hạng mục đang đọc).
3. Hạng mục xuất hiện trên mặt bằng tổng thể nhưng KHÔNG có bản vẽ chi tiết riêng thể hiện đầy đủ trong cùng bộ bản vẽ được cung cấp.
4. Giá trị thiết kế lệch giá trị tính toán đi kèm (ví dụ chọn bơm/thiết bị có thông số cao hơn số liệu tính toán ghi kèm) — LƯU Ý: KHÔNG coi là lỗi nếu độ lệch thiên về an toàn (thiết kế cao hơn/an toàn hơn mức tính toán) — chỉ ghi nhận vào nhóm II để người dùng biết và tự đối chiếu thêm, TUYỆT ĐỐI KHÔNG xếp vào nhóm III (nhóm III chỉ dành cho giá trị thấp hơn/vi phạm mức quy định, không phải cho thiết kế an toàn hơn tính toán).
Khi phát hiện đúng 1 trong 4 loại trên: soạn câu kiến nghị theo đúng văn phong đã hướng dẫn ở trên, nêu rõ cụ thể 2 giá trị/nguồn đang mâu thuẫn với nhau, xếp vào nhóm II.
"""

# Quy tac chung "khong uoc luong khoang cach bang mat" — ap dung cho MOI tieu
# chi co chu "khoang cach" trong noi dung quy dinh (giua 2 thiet bi, den
# tuong/tran, den duong thoat nan...). Nguong so lieu (vd <=7,2m/<=10,2m/<=45m)
# da co san DAY DU, DUNG trong quy_dinh cua tung tieu chi (lay truc tiep tu
# file .docx mau MDC) - khoang trong THAT la chua co quy tac ngan AI tu uoc
# luong khoang cach bang mat khi ban ve khong ghi ro so do. Dung CHUNG 1 nguon
# cho baochay/densucco (binh chua chay + den su co)/ccnuoc (B6 sprinkler) -
# ghep vao dung cho "NGUYEN TAC BAT BUOC" cua tung reader.
KHONG_UOC_LUONG_KHOANG_CACH = """
- Với MỌI tiêu chí có yêu cầu về khoảng cách (giữa 2 thiết bị, đến tường/trần, đến đường thoát nạn...): CHỈ được kết luận "dat" hoặc "chua_dat" khi bản vẽ CÓ GHI RÕ con số đo cụ thể (đường kích thước có ghi số, hoặc ghi chú nêu rõ khoảng cách). TUYỆT ĐỐI KHÔNG tự ước lượng khoảng cách bằng cách nhìn vị trí tương đối của các ký hiệu trên bản vẽ — nhìn ảnh để đoán khoảng cách không đáng tin cậy và bị coi là suy đoán, VI PHẠM nguyên tắc bắt buộc. Nếu bản vẽ không ghi rõ số đo cho tiêu chí này: "ket_luan" PHẢI là "chua_the_hien", "noi_dung_thiet_ke" ghi "Chưa thể hiện khoảng cách cụ thể trên bản vẽ cung cấp".
"""

# Toa do truc ket cau (chu doc A,B,C.../so ngang 1,2,3...) cho thiet bi VI PHAM
# khoang cach ("chua_dat", so do THAT tu KHONG_UOC_LUONG_KHOANG_CACH o tren, khong
# phai uoc luong) - de dinh vi nhanh tren ban ve. Xuat hien o CA 2 cho trong moi
# system prompt: (1) BUOC 1, ngay sau dong sinh "noi_dung_thiet_ke" - vi day la
# noi dung dien vao cot 3 "Noi dung thiet ke" cua chinh bang doi chieu MDC .docx,
# KHONG chi o kien nghi; (2) BUOC 2/3, ngay sau dong mo ta doi tuong trong cau
# kien nghi. Dung chung cho 5 reader da co KHONG_UOC_LUONG_KHOANG_CACH: baochay,
# densucco, ccnuoc (CHI B6 chua_chay_tu_dong), khibotsolkhi, botcodinh.
TOA_DO_TRUC_KHOANG_CACH = """
- Riêng với tiêu chí về khoảng cách có "ket_luan" là "chua_dat": NẾU bản vẽ có lưới trục kết cấu (ký hiệu chữ dọc A, B, C... và số ngang 1, 2, 3... ghi ở khung/mép bản vẽ), xác định vị trí ô lưới hoặc giao điểm trục gần nhất chứa (các) thiết bị vi phạm — ghi thêm vào CẢ "noi_dung_thiet_ke" (ngay sau số liệu đo được) LẪN câu kiến nghị tương ứng (ngay sau phần mô tả đối tượng, trước phần căn cứ Điều/Khoản) — định dạng "tại vị trí trục (X-Y, N-M)" nếu thiết bị nằm giữa 2 trục dọc X-Y và 2 trục ngang N-M, hoặc "gần giao trục X-N" nếu nằm sát 1 giao điểm cụ thể. NẾU bản vẽ KHÔNG có lưới trục kết cấu rõ ràng (không ghi nhãn chữ/số trục nào): bỏ qua yêu cầu này, KHÔNG tự suy đoán hoặc đặt tên trục giả định.
"""

# Chuan hoa 3 mau cau ket luan (doi chieu tu tai lieu "Bo quy tac doc ban ve
# va dien MDC" 03/9/2026, Phan III.14 + Phan IV) - truoc ban nay moi reader tu
# dien dat 1 kieu khac nhau cho cung 1 tinh huong, kho doi chieu khi 1 du an
# co nhieu form. Dung CHUNG cho moi reader co dung KHONG_UOC_LUONG_KHOANG_CACH.
STANDARD_PHRASES = """
CHUẨN HÓA CÂU CHỮ — dùng đúng 1 trong 3 mẫu câu sau (chỉ thay phần trong ngoặc
vuông), không tự diễn đạt khác đi:
1. Nội dung đáng lẽ phải có trên bản vẽ nhưng không tìm thấy: "noi_dung_thiet_ke"
   ghi đúng "Chưa thể hiện trên bản vẽ cung cấp".
2. Nội dung cần đo đạc/quan sát trực tiếp tại hiện trường mới khẳng định chắc
   chắn được (không thể chỉ nhìn bản vẽ để kết luận Đạt/chưa đạt): câu kiến
   nghị bắt đầu bằng "Khuyến cáo — đề nghị kiểm tra lại" thay vì "Bổ sung"/
   "Thể hiện rõ"/"Thuyết minh rõ".
3. Nội dung KHÔNG thuộc đối tượng áp dụng của công trình này ("ket_luan" =
   "khong_ap_dung"): "noi_dung_thiet_ke" ghi theo đúng khuôn "x - Không thuộc
   đối tượng áp dụng: [căn cứ ngưỡng quy định] - [số liệu thực tế của công
   trình]".
"""

# Ky nang doc ban ve #7 + #8 (Phan III.B tai lieu tren) - chua co reader nao
# nhac toi 2 ky nang nay (da grep xac nhan truoc khi them). Dung CHUNG cho moi
# reader co dung KHONG_UOC_LUONG_KHOANG_CACH.
DOC_CHU_XOAY_VA_KY_HIEU = """
- CHỮ XOAY DỌC / KÝ HIỆU BỊ TÁCH RỜI: trong lớp văn bản trích từ file PDF, các
  con số/chữ bị xoay 90° (thường là kích thước, bán kính, mã hiệu ghi dọc theo
  cạnh bản vẽ) có thể bị tách thành nhiều đoạn rời rạc xen kẽ khoảng trắng (ví
  dụ "0 20 R7" thực chất là "R7200" đọc ngược). TRƯỚC khi kết luận một nội
  dung "chưa thể hiện" vì không tìm thấy số liệu, thử ghép lại các đoạn
  chữ/số rời rạc nằm gần nhau (bỏ khoảng trắng, đọc xuôi và đọc ngược) xem có
  tạo thành 1 số liệu hợp lệ hay không.
- TRA BẢNG CHÚ THÍCH KÝ HIỆU (legend) trước khi diễn giải chức năng của bất kỳ
  ký hiệu nào trên mặt bằng — nếu bản vẽ có bảng chú thích/bảng ký hiệu riêng,
  PHẢI đối chiếu đúng ký hiệu đó với bảng chú thích trước khi kết luận đó là
  thiết bị gì, không suy đoán chức năng chỉ từ hình dạng ký hiệu.
"""


# Ky nang doc ban ve #1 "lap danh muc ban ve" (tai lieu tren) - Batch 5A Pha 2.
# LA HAM (khong phai hang so) vi noi dung phu thuoc so file THAT SU cua tung
# lan goi - noi THEM vao system prompt tai thoi diem goi (giong cach
# quy_mo_store.format_quy_mo_context(quy_mo) da lam cho ngu canh quy mo),
# khong phai luc build template tinh SYSTEM_PROMPT. Dung chung cho ca 9
# reader da sua o Pha 1 (khong dung o merged_reader/scan_quymo_reader - van
# giu 1 file/request, ngoai pham vi Pha 2).
def format_danh_muc_ban_ve_instruction(num_files: int) -> str:
    """Chi tra ve noi dung khi co TU 2 FILE TRO LEN trong 1 lan goi (Batch 5A
    Pha 2, doi chieu tai lieu "Bo quy tac doc ban ve va dien MDC" 03/9/2026,
    ky nang #1 "lap danh muc ban ve"). Voi 1 file (hoac 0, khong xay ra thuc
    te), tra ve chuoi rong - KHONG doi hanh vi cu, AI van chi dien so_hieu_ban_ve
    don le nhu truoc Pha 2."""
    if num_files <= 1:
        return ""
    return f"""
DANH MỤC BẢN VẼ (đang đọc {num_files} file cùng lúc trong lần này): với MỖI
file trong số {num_files} file được cung cấp (đánh số thứ tự từ 0, đúng theo
thứ tự file được đính kèm), đọc SỐ HIỆU BẢN VẼ ghi trong khung tên (góc dưới
bên phải) và tên bản vẽ của CHÍNH file đó, trả về thêm mảng
"danh_muc_ban_ve": [{{"ky_hieu": "...", "ten_ban_ve": "...", "file_index": 0}}, ...]
— ĐỦ {num_files} phần tử, mỗi phần tử ứng đúng 1 file theo "file_index". Nếu
1 file không có khung tên rõ ràng: "ky_hieu" ghi "Không xác định được số hiệu
bản vẽ", "ten_ban_ve" để chuỗi rỗng — KHÔNG suy đoán. Trường "so_hieu_ban_ve"
(số hiệu đơn — đã có sẵn) vẫn điền như cũ, dùng số hiệu của file đầu tiên
(file_index 0) làm đại diện — mảng "danh_muc_ban_ve" mới là danh sách đầy đủ.
"""


def exclusive_alternative_block(ten_nhom, pairs, ghi_chu=""):
    """Dung chung cho cac reader co tieu chi dang "nhieu lua chon THAY THE LAN
    NHAU" (bản vẽ chỉ dùng ĐÚNG 1 lựa chọn thật, không có chuyện "không dùng
    cái nào cả" — khác hẳn tuỳ chọn "có thể không thiết kế"). pairs: list
    [(ids_tuple, ten_lua_chon), ...]. Lựa chọn KHÔNG khớp thực tế bản vẽ ->
    "khong_ap_dung" cho tất cả id thuộc lựa chọn đó. Dùng ở khibotsolkhi_reader.py
    (B8: HFC-227ea vs FK-5-1-12) và botcodinh_reader.py (B7: mái cố định vs
    mái nổi/phao trong) — chuyển ra đây (Batch 5A mở rộng B7) để tránh trùng
    lặp khi có ≥2 module cùng cần logic này."""
    lines = [f'YÊU CẦU RIÊNG CHO {ten_nhom}: đây là các lựa chọn THAY THẾ LẪN NHAU — bản vẽ chỉ dùng ĐÚNG 1 lựa chọn trong số sau (không phải "tuỳ chọn có thể bỏ trống" — luôn có 1 lựa chọn thật được dùng). Xác định rõ bản vẽ THẬT SỰ dùng lựa chọn nào rồi mới đối chiếu:']
    for ids, ten in pairs:
        ids_str = ", ".join(str(i) for i in ids)
        lines.append(
            f'- id={ids_str} ({ten}): nếu bản vẽ dùng đúng {ten}, đối chiếu BÌNH THƯỜNG theo hướng dẫn chung. '
            f'Nếu bản vẽ dùng lựa chọn KHÁC (không phải {ten}): TẤT CẢ id trong nhóm này "ket_luan": "khong_ap_dung", '
            f'"noi_dung_thiet_ke": "Bản vẽ không dùng {ten}" — KHÔNG tạo kiến nghị cho các id này.'
        )
    if ghi_chu:
        lines.append(ghi_chu)
    return "\n".join(lines) + "\n"


def system_prompt_version(system_prompt: str) -> str:
    """'Phiên bản' system prompt = 12 ký tự đầu sha256 nội dung prompt — tự động
    đổi mỗi khi nội dung prompt thay đổi, không cần nhớ tay bump số như semver
    (dễ quên, dễ sai). Dùng để biết log 1 lần gọi AI ứng với đúng bản prompt nào."""
    return hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:12]


def _log_ai_call(provider, prompt_version, status, started_at, usage=None, error=None):
    elapsed_s = round(time.monotonic() - started_at, 2)
    logger.info(
        "aiho_ai_call provider=%s model=%s prompt_version=%s status=%s elapsed_s=%s usage=%s%s",
        getattr(provider, "name", "?"),
        getattr(provider, "model", "?"),
        prompt_version,
        status,
        elapsed_s,
        usage,
        f" error={error}" if error else "",
    )


def _content_block_for(file_bytes: bytes, media_type: str) -> dict:
    b64 = base64.standard_b64encode(file_bytes).decode("ascii")
    if media_type == "application/pdf":
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": b64},
    }


def _parse_and_log(raw: str, usage, provider, version: str, started_at: float) -> dict:
    """Parse JSON tra ve tu AI + ghi log 1 dong (thanh cong/loi) - dung chung
    cho ca read_drawing_json() (1 file) va read_drawing_json_multi() (nhieu
    file), vi phan parse/log GIONG HET nhau bat ke goi 1 hay nhieu file."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Trích đoạn quanh đúng vị trí lỗi (exc.pos) — hữu ích hơn nhiều so với chỉ hiện
        # đầu chuỗi, vì lỗi "Unterminated string" thường xảy ra ở cuối văn bản AI trả về
        # (bị cắt giữa chừng do hết max_tokens), cách xa phần đầu.
        start = max(0, exc.pos - 200)
        snippet = raw[start:exc.pos + 50]
        _log_ai_call(provider, version, "json_error", started_at, usage=usage, error=str(exc))
        raise AIReaderError(
            f"AI trả về không đúng định dạng JSON: {exc}. "
            f"Tổng độ dài phản hồi: {len(raw)} ký tự. "
            f"Đoạn quanh vị trí lỗi: ...{snippet}..."
        )

    _log_ai_call(provider, version, "success", started_at, usage=usage)
    return parsed


def read_drawing_json(file_bytes: bytes, media_type: str, provider, system_prompt: str, prompt_version: str = None) -> dict:
    """Gửi bản vẽ (ảnh hoặc PDF) kèm system_prompt tới AI provider, trả về dict đã
    parse JSON. prompt_version: nhãn phiên bản prompt để ghi log (mặc định tự suy
    ra từ chính system_prompt nếu không truyền — xem system_prompt_version())."""
    content_block = _content_block_for(file_bytes, media_type)

    version = prompt_version if prompt_version is not None else system_prompt_version(system_prompt)
    started_at = time.monotonic()

    try:
        result = provider.generate_with_document(system_prompt, content_block)
    except AttributeError:
        _log_ai_call(provider, version, "error", started_at, error="provider khong ho tro generate_with_document")
        raise AIReaderError(
            f"Provider '{getattr(provider, 'name', '?')}' chưa hỗ trợ đọc ảnh/PDF (generate_with_document)."
        )
    except CircuitBreakerOpen as exc:
        # Loi ro rang, dung mo ta san co san (bao nhieu lan lien tiep/con nghi bao
        # lau) - boc thanh AIReaderError de di dung duong 502 co san o routes/aiho.py
        # thay vi roi vao nhanh 500 chung chung.
        _log_ai_call(provider, version, "circuit_open", started_at, error=str(exc))
        raise AIReaderError(str(exc)) from exc
    except Exception as exc:
        _log_ai_call(provider, version, "error", started_at, error=str(exc))
        raise

    return _parse_and_log(result.text, result.usage, provider, version, started_at)


def read_drawing_json_multi(files: list, provider, system_prompt: str, prompt_version: str = None) -> dict:
    """Giống read_drawing_json() nhưng gửi NHIỀU file (files: list[(bytes, media_type)])
    trong CÙNG 1 request AI — dùng khi 1 hạng mục có thể có nội dung nằm rải trên
    nhiều file bản vẽ khác nhau. Xem read_drawing_json() cho phần xử lý response/
    parse JSON/log (dùng chung qua _parse_and_log()) — hàm này chỉ khác ở bước
    dựng content_blocks và gọi generate_with_documents() thay vì generate_with_document()."""
    content_blocks = [_content_block_for(fb, mt) for fb, mt in files]

    version = prompt_version if prompt_version is not None else system_prompt_version(system_prompt)
    started_at = time.monotonic()

    try:
        result = provider.generate_with_documents(system_prompt, content_blocks)
    except AttributeError:
        _log_ai_call(provider, version, "error", started_at, error="provider khong ho tro generate_with_documents")
        raise AIReaderError(f"Provider '{getattr(provider, 'name', '?')}' chưa hỗ trợ đọc nhiều file cùng lúc.")
    except CircuitBreakerOpen as exc:
        _log_ai_call(provider, version, "circuit_open", started_at, error=str(exc))
        raise AIReaderError(str(exc)) from exc
    except Exception as exc:
        _log_ai_call(provider, version, "error", started_at, error=str(exc))
        raise

    return _parse_and_log(result.text, result.usage, provider, version, started_at)


def read_and_validate_drawing_json(file_bytes: bytes, media_type: str, provider, system_prompt: str, validate_fn, prompt_version: str = None):
    """Gọi read_drawing_json(), rồi validate kết quả qua validate_fn(dict) -> model
    Pydantic (raise SchemaValidationError nếu sai). Nếu thất bại lần 1: retry ĐÚNG
    1 LẦN, gọi lại AI với system_prompt được bổ sung thông báo lỗi cụ thể để AI tự
    sửa. Nếu lần 2 vẫn sai: raise AIReaderError rõ ràng — KHÔNG trả kết quả nửa vời.

    prompt_version: override nhãn phiên bản ghi log — dùng khi system_prompt bị
    NỐI THÊM dữ liệu động ở call-time (vd context "Quy mô" — xem quy_mo_store.py,
    Mức 1 tích hợp vào 4 reader hiện có) khiến sha256 nội dung đổi mỗi lần gọi dù
    prompt GỐC (template) không đổi; truyền SYSTEM_PROMPT_VERSION tĩnh của reader
    vào đây để log vẫn phản ánh đúng "phiên bản template", không bị phân mảnh theo
    dữ liệu quy mô cụ thể của từng lần gọi.
    """
    version = prompt_version if prompt_version is not None else system_prompt_version(system_prompt)  # tinh 1 lan tu prompt GOC, dung cho ca 2 lan goi (repair khong tinh la "phien ban" khac)
    raw = read_drawing_json(file_bytes, media_type, provider, system_prompt, prompt_version=version)
    try:
        return validate_fn(raw)
    except SchemaValidationError as first_err:
        repair_prompt = (
            system_prompt
            + "\n\n--- SỬA LỖI ĐỊNH DẠNG (bắt buộc) ---\n"
            + "Lần trả lời TRƯỚC của bạn KHÔNG đạt yêu cầu định dạng, lý do cụ thể:\n"
            + str(first_err)
            + "\nHãy đọc lại bản vẽ và trả lời LẠI TỪ ĐẦU, đúng nguyên cấu trúc JSON đã yêu cầu ở trên, sửa đúng lỗi trên. "
              "Không lặp lại lỗi này, không thêm văn bản nào khác ngoài JSON."
        )
        raw2 = read_drawing_json(file_bytes, media_type, provider, repair_prompt, prompt_version=version)
        try:
            return validate_fn(raw2)
        except SchemaValidationError as second_err:
            raise AIReaderError(
                f"AI trả kết quả không đúng định dạng ngay cả sau khi đã yêu cầu sửa lỗi 1 lần: {second_err}"
            ) from second_err


def read_and_validate_drawing_json_multi(files: list, provider, system_prompt: str, validate_fn, prompt_version: str = None):
    """Bản song song với read_and_validate_drawing_json() — giữ nguyên y hệt cơ
    chế retry-repair 1 lần khi validate_fn raise SchemaValidationError, chỉ đổi
    read_drawing_json() -> read_drawing_json_multi() và truyền files thay vì
    file_bytes/media_type đơn lẻ."""
    version = prompt_version if prompt_version is not None else system_prompt_version(system_prompt)
    raw = read_drawing_json_multi(files, provider, system_prompt, prompt_version=version)
    try:
        return validate_fn(raw)
    except SchemaValidationError as first_err:
        repair_prompt = (
            system_prompt
            + "\n\n--- SỬA LỖI ĐỊNH DẠNG (bắt buộc) ---\n"
            + "Lần trả lời TRƯỚC của bạn KHÔNG đạt yêu cầu định dạng, lý do cụ thể:\n"
            + str(first_err)
            + "\nHãy đọc lại bản vẽ và trả lời LẠI TỪ ĐẦU, đúng nguyên cấu trúc JSON đã yêu cầu ở trên, sửa đúng lỗi trên. "
              "Không lặp lại lỗi này, không thêm văn bản nào khác ngoài JSON."
        )
        raw2 = read_drawing_json_multi(files, provider, repair_prompt, prompt_version=version)
        try:
            return validate_fn(raw2)
        except SchemaValidationError as second_err:
            raise AIReaderError(
                f"AI trả kết quả không đúng định dạng ngay cả sau khi đã yêu cầu sửa lỗi 1 lần: {second_err}"
            ) from second_err
