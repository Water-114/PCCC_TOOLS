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
KIỂM TRA MÂU THUẪN LOGIC NỘI BỘ (nhóm II — "chưa thống nhất giữa nhiều nguồn số liệu"): CHỈ áp dụng khi bản vẽ ĐANG ĐỌC thực sự chứa ÍT NHẤT 2 nguồn số liệu độc lập để đối chiếu chéo (ví dụ vừa có mặt bằng vừa có bảng thống kê/bảng tính trong CÙNG file cung cấp) — nếu chỉ có 1 nguồn thông tin thì KHÔNG suy đoán, để mảng nhóm II rỗng như bình thường. Khi có đủ ít nhất 2 nguồn, chủ động đối chiếu chéo các loại mâu thuẫn sau:
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


def read_drawing_json(file_bytes: bytes, media_type: str, provider, system_prompt: str, prompt_version: str = None) -> dict:
    """Gửi bản vẽ (ảnh hoặc PDF) kèm system_prompt tới AI provider, trả về dict đã
    parse JSON. prompt_version: nhãn phiên bản prompt để ghi log (mặc định tự suy
    ra từ chính system_prompt nếu không truyền — xem system_prompt_version())."""
    b64 = base64.standard_b64encode(file_bytes).decode("ascii")

    if media_type == "application/pdf":
        content_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
    else:
        content_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }

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

    raw, usage = result.text, result.usage

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
