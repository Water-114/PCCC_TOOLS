"""AI đọc bản vẽ — hệ thống chữa cháy bằng bột (B16, TCVN 13877-2:2023).

LƯU Ý TÊN GỌI DỄ NHẦM: đây là hệ thống chữa cháy bằng BỘT (powder), KHÁC HẲN
"bọt" (foam, đã làm ở B7/botcodinh_reader.py/TCVN 5307:2009).

Cùng kiểu kiến trúc với gia_ke_hang_reader.py (B15): 1 template DUY NHẤT chứa
CẢ 2 nhánh (chữa cháy THEO THỂ TÍCH — Điều 9, và chữa cháy BỀ MẶT — Điều 10)
trong CÙNG 1 bảng — _EXPECTED_IDS là 1 bộ CỐ ĐỊNH, AI phải trả lời ĐỦ mọi id,
id thuộc nhánh không chọn nhận "ket_luan": "khong_ap_dung".

Nguồn số liệu DUY NHẤT: bot-chua-chay-tcvn13877.md (skill ra-mau-doi-chieu-pccc)
— skill này ghi rõ "đã đối chiếu TOÀN BỘ citation trong file B16 gốc với bản
TCVN 13877-2:2023 thật — KHÔNG phát hiện lỗi trích dẫn nào" (khác B15 có 2 lỗi
cần sửa) — không cần override citation nào ở đây.

Đã tự kiểm chứng lại toàn bộ 33 id qua mdc_filler._extract_rows() trên chính
B16_bot_chua_chay.docx (sau khi xoá bảng thừa 1x2) — khớp 100% id/nhánh do
owner cung cấp. Công thức Q1 (id=20, kèm đủ hệ số K1-K4 cho đám cháy
hydrocacbon) và Q2 (id=27, kèm K5=1,2 kg/m3) đã có ĐẦY ĐỦ trong chính nội dung
quy_dinh của 2 dòng này (đọc trực tiếp từ .docx) — không cần nhúng lại. Riêng
công thức tốc độ xả R (id=22) bị THIẾU trong quy_dinh (vốn là 1 công thức
dạng ảnh/equation object trong file .docx gốc không convert được sang text)
— bổ sung bằng khối riêng bên dưới, lấy đúng "R = Q1/30" từ skill reference.

KHÔNG áp dụng KHONG_UOC_LUONG_KHOANG_CACH/TOA_DO_TRUC_KHOANG_CACH cho form này
(owner quyết định — B16 không có tiêu chí "khoảng cách giữa 2 thiết bị" nào
như B15; id=47 "Khoảng cách giữa các giá treo" là 1 bảng số cố định (Bảng 2),
không phải dạng "đo trên bản vẽ so với ngưỡng" cần quy tắc chống ước lượng)."""

from . import mdc_filler, quy_mo_store
from .ai_reader_common import (
    DOC_CHU_XOAY_VA_KY_HIEU,
    NHOM_II_MAU_THUAN_CHECKLIST,
    STANDARD_PHRASES,
    AIReaderError,
    read_and_validate_drawing_json,
    system_prompt_version,
)
from .ai_schema import BotChuaChayReaderResult, validate_reader_result

_THE_TICH_IDS = (19, 20, 21, 22, 23, 24)
_BE_MAT_IDS = (27, 28, 29)

_TOC_DO_XA_GHI_CHU = """YÊU CẦU RIÊNG CHO id=22 (Tốc độ xả khí, nhánh thể tích): công thức gốc của tiêu chuẩn là "R = Q1/30" (R: tốc độ xả tối thiểu, kg/s; Q1: lượng bột tính theo id=20, kg; 30: thời gian xả tối đa, giây, Điều 9.3.2 TCVN 13877-2:2023) — dùng đúng công thức này để đối chiếu/tính toán khi bản vẽ có đủ dữ liệu Q1."""

_K_KHONG_NHAM_GHI_CHU = """YÊU CẦU RIÊNG CHO id=20 và id=27 (công thức lượng bột — KHÔNG được lẫn công thức giữa 2 nhánh): id=20 (nhánh thể tích, Điều 9.2) dùng công thức Q1 = K1.V + K2.AS + K3.AL + K4.Rv.t với 4 hệ số K1-K4 tra theo loại đám cháy (đã cho sẵn giá trị hydrocacbon trong chính nội dung quy định của id=20). id=27 (nhánh bề mặt, Điều 10.2) dùng công thức KHÁC HẲN: Q2 = K5 × Vi với DUY NHẤT 1 hệ số K5 = 1,2 kg/m³ CỐ ĐỊNH (không đổi theo loại đám cháy như K1-K4). TUYỆT ĐỐI KHÔNG áp K5 vào tính Q1 hay áp K1-K4 vào tính Q2."""

_HINH_C_GHI_CHU = """YÊU CẦU RIÊNG CHO id=29 (Bố trí đầu phun, nhánh bề mặt — ĐIỂM DỄ SAI NHẤT của form này): "Lượng bột, thời gian xả tối thiểu và tốc độ xả" của nhánh bề mặt được tra theo Hình C.1-C.4 Phụ lục C TCVN 13877-2:2023 — đây là BIỂU ĐỒ TUYẾN TÍNH (nomogram) dạng log-log tra chéo trục hoành (diện tích bảo vệ, m²) để đọc 3 giá trị trên trục tung, KHÔNG PHẢI bảng số rời rạc, KHÔNG THỂ trích xuất chính xác bằng đọc text/OCR. TUYỆT ĐỐI KHÔNG được tự đoán/bịa 3 giá trị này dù bản vẽ có vẽ hình biểu đồ. Với id này: nếu bản vẽ có ghi diện tích bảo vệ (input), trích nguyên số liệu đó vào "noi_dung_thiet_ke", rồi ghi thêm "Tính toán theo Hình C.1-C.4 Phụ lục C TCVN 13877-2:2023 (cần tra biểu đồ thủ công)", "ket_luan": "chua_the_hien". Nếu bản vẽ không có cả diện tích bảo vệ: "noi_dung_thiet_ke": "Chưa thể hiện trên bản vẽ cung cấp", "ket_luan": "chua_the_hien"."""

_NHANH_BLOCK = f"""YÊU CẦU RIÊNG CHO 2 NHÁNH (loại trừ lẫn nhau — bản vẽ chỉ dùng ĐÚNG 1 nhánh thật, không phải "tuỳ chọn có thể bỏ trống"; TRỪ trường hợp bản vẽ thể hiện RÕ RÀNG kết hợp cả 2 — xem hướng dẫn Bước 1):
- id={", ".join(str(i) for i in _THE_TICH_IDS)} (nhánh "Hệ thống chữa cháy THEO THỂ TÍCH" — Điều 9): nếu bản vẽ dùng đúng nhánh này (hoặc dùng kết hợp cả 2), đối chiếu BÌNH THƯỜNG theo hướng dẫn chung. Nếu bản vẽ CHỈ dùng nhánh bề mặt (không dùng nhánh này): TẤT CẢ id trong nhóm này "ket_luan": "khong_ap_dung", "noi_dung_thiet_ke": "x - Không áp dụng".
- id={", ".join(str(i) for i in _BE_MAT_IDS)} (nhánh "Hệ thống chữa cháy BỀ MẶT" — Điều 10): nếu bản vẽ dùng đúng nhánh này (hoặc dùng kết hợp cả 2), đối chiếu BÌNH THƯỜNG theo hướng dẫn chung. Nếu bản vẽ CHỈ dùng nhánh thể tích (không dùng nhánh này): TẤT CẢ id trong nhóm này "ket_luan": "khong_ap_dung", "noi_dung_thiet_ke": "x - Không áp dụng".
{_TOC_DO_XA_GHI_CHU}
{_K_KHONG_NHAM_GHI_CHU}
{_HINH_C_GHI_CHU}
"""

_BUOC1_XAC_DINH_NHANH = """BƯỚC 1 — Xác định nhánh: đọc bản vẽ/thuyết minh để xác định phạm vi bảo vệ thực tế, rồi chọn nhánh theo bảng sau:
| Điều kiện | Nhánh |
|---|---|
| Bảo vệ TOÀN BỘ thể tích 1 không gian kín (phòng/khoang) | "the_tich" (Điều 9) |
| Bảo vệ 1 đối tượng/thiết bị độc lập, KHÔNG cần bảo vệ cả phòng (ví dụ máy biến áp ngoài trời, bể chứa dầu lộ thiên) | "be_mat" (Điều 10) |
Nếu bản vẽ thể hiện RÕ RÀNG kết hợp cả 2 (vừa bảo vệ cả phòng vừa bảo vệ 1 thiết bị độc lập trong/ngoài phòng đó — ví dụ Phụ lục B TCVN 13877-2:2023 ví dụ 2: kết hợp đám cháy bề mặt + đám cháy thiết bị ngoài trời): vẫn PHẢI chọn 1 nhánh CHÍNH cho trường "nhanh" (nhánh có phạm vi bảo vệ chính của công trình), đối chiếu ĐỦ id của CẢ 2 nhánh bình thường (không đánh "khong_ap_dung" cho nhánh phụ), và ghi rõ trong "noi_dung_thiet_ke" của các id liên quan là bản vẽ có kết hợp cả 2 hình thức bảo vệ. Nêu rõ căn cứ đã dùng trong "ly_do_nhan_dien"."""


def _fmt_rows(rows):
    return "\n".join(
        f"id={r['id']} | [{r['doi_chieu']}] {r['quy_dinh']} (Căn cứ: {r['khoan_dieu']})"
        for r in rows
    )


def _build_system_prompt():
    rows = mdc_filler.load_criteria_rows("bot_chua_chay")
    return f"""Bạn là kỹ sư PCCC rà soát bản vẽ hệ thống chữa cháy CỐ ĐỊNH bằng BỘT (xả bột từ bình chứa qua đầu phun bằng khí đẩy — KHÁC HẲN hệ thống chữa cháy bằng BỌT/foam), đối chiếu với mẫu đối chiếu MĐC B16 (TCVN 13877-2:2023).

YÊU CẦU THÊM: Đọc SỐ HIỆU BẢN VẼ ghi trong khung tên (title block) của chính bản vẽ này (thường ở góc dưới bên phải, ô ghi "Số bản vẽ" / "Ký hiệu bản vẽ" / "Drawing No."). Nếu khung tên không có, không rõ, hoặc bản vẽ không thể hiện số hiệu: ghi ĐÚNG NGUYÊN VĂN "Không xác định được số hiệu bản vẽ" ở trường "so_hieu_ban_ve" — TUYỆT ĐỐI không suy đoán, không tự đặt số hiệu.

{_BUOC1_XAC_DINH_NHANH}

BƯỚC 2 — Với MỖI dòng tiêu chí dưới đây (mỗi dòng có sẵn "id" — khi trả lời PHẢI giữ nguyên đúng id đó, và phải trả lời ĐỦ cho TẤT CẢ id, KỂ CẢ id thuộc nhánh KHÔNG được chọn ở Bước 1 — không bỏ sót bất kỳ id nào), đối chiếu với bản vẽ và trả về:
- "noi_dung_thiet_ke": nội dung điền vào cột "Nội dung thiết kế" của mẫu MĐC gốc — ngắn gọn, đúng mạch đối chiếu (dùng gạch đầu dòng "-" nếu nhiều ý), nêu số liệu cụ thể NHÌN THẤY trên bản vẽ. Nếu bản vẽ không thể hiện đủ thông tin để kết luận: ghi đúng "Chưa thể hiện trên bản vẽ cung cấp".
{STANDARD_PHRASES}
- "ket_luan": "dat" nếu nội dung trên bản vẽ đáp ứng đúng quy định; "chua_dat" nếu đã thể hiện nhưng vi phạm giá trị/quy định; "chua_the_hien" nếu bản vẽ không đủ thông tin để kết luận; "khong_ap_dung" CHỈ dùng cho id thuộc nhánh KHÔNG được chọn (xem hướng dẫn nhánh bên dưới) — KHÔNG tự ý dùng cho id khác.

{_NHANH_BLOCK}
--- DANH SÁCH TIÊU CHÍ (MĐC B16 — chữa cháy bằng bột) ---
{_fmt_rows(rows)}

BƯỚC 3: Với MỖI id có "ket_luan" là "chua_dat" hoặc "chua_the_hien" ở Bước 2, soạn thêm một câu kiến nghị theo đúng văn phong công văn PC07:
- Mở đầu bằng động từ mệnh lệnh phù hợp: "Thể hiện rõ ..." (nếu là "chua_the_hien" — thông tin đáng lẽ có trên bản vẽ nhưng chưa vẽ/ghi), "Bổ sung ..." (nếu cần thêm chi tiết/thiết bị/bản vẽ), hoặc "Thuyết minh rõ ..." (nếu cần giải trình bằng lời).
- Một câu mạch lạc, nêu rõ đối tượng cụ thể trên bản vẽ + số liệu định lượng của tiêu chuẩn (lấy từ đúng nội dung quy định của id tương ứng).
- Kết câu bằng phần căn cứ, in trong ngoặc đơn, lấy ĐÚNG "Khoản, Điều" đã ghi ở id đó — không tự bịa số Điều khác.
- Xếp mỗi kiến nghị vào đúng 1 trong 4 nhóm sau:
  - "chua_the_hien": nhóm I (nội dung chưa thể hiện trên bản vẽ).
  - "chua_dat": nhóm III (nội dung đã thể hiện nhưng vi phạm giá trị/quy định của tiêu chuẩn).
  - Nhóm II (chưa thống nhất giữa nhiều nguồn số liệu) và nhóm IV (đề xuất bổ sung hồ sơ/bản vẽ mới) CHỈ dùng khi có căn cứ rõ ràng từ chính bản vẽ này; nếu không có căn cứ, để mảng rỗng — KHÔNG cố tạo kiến nghị cho đủ 4 nhóm.
{NHOM_II_MAU_THUAN_CHECKLIST}
- id có "ket_luan" là "khong_ap_dung": KHÔNG tạo kiến nghị nào.
- Nếu mọi id đều "dat" hoặc "khong_ap_dung", để cả 4 mảng đều rỗng.

NGUYÊN TẮC BẮT BUỘC:
- Chỉ đánh giá dựa trên nội dung THỰC SỰ thể hiện trên bản vẽ được cung cấp. Không suy đoán, không dùng kiến thức chung ngoài bản vẽ.
- Không được bỏ sót bất kỳ id nào.
{DOC_CHU_XOAY_VA_KY_HIEU}

Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON:
{{
  "nhanh": "the_tich" | "be_mat",
  "ly_do_nhan_dien": "câu ngắn giải thích vì sao xác định nhánh này",
  "so_hieu_ban_ve": "số hiệu bản vẽ đọc từ khung tên, hoặc \\"Không xác định được số hiệu bản vẽ\\"",
  "items": [
    {{"id": 1, "noi_dung_thiet_ke": "...", "ket_luan": "dat" | "chua_dat" | "chua_the_hien" | "khong_ap_dung"}}
  ],
  "tong_ket": "1-2 câu tổng kết tình trạng chung",
  "kien_nghi": {{
    "I_chua_the_hien": ["câu kiến nghị theo khuôn PC07, kết bằng (Căn cứ Điều ..., Mục ... TCVN/QCVN ....)"],
    "II_chua_thong_nhat": [],
    "III_chua_phu_hop": ["câu kiến nghị tương tự cho các id chua_dat"],
    "IV_de_xuat_bo_sung": []
  }}
}}"""


SYSTEM_PROMPT = _build_system_prompt()
SYSTEM_PROMPT_VERSION = system_prompt_version(SYSTEM_PROMPT)  # doi tu dong khi noi dung prompt tren doi

BotChuaChayReaderError = AIReaderError

_EXPECTED_IDS = {r["id"] for r in mdc_filler.load_criteria_rows("bot_chua_chay")}


def _validate(data: dict):
    return validate_reader_result(data, _EXPECTED_IDS, BotChuaChayReaderResult)


def read_drawing(file_bytes: bytes, media_type: str, provider, quy_mo: dict = None) -> dict:
    """Gửi bản vẽ (ảnh hoặc PDF) kèm tiêu chí tới AI provider, validate qua Pydantic
    (kèm retry-repair 1 lần nếu sai), trả về dict.

    quy_mo: dữ liệu quy mô công trình (hạng mục "Quy mô") của CÙNG phiên Bộ hồ
    sơ, nếu người dùng CÓ đính kèm — HOÀN TOÀN TUỲ CHỌN (None nếu không đính).
    B16 không có field quy mô riêng nào áp dụng trực tiếp (khác B15 với
    chieuCaoKeHang) — chỉ nhận tham số này để đồng bộ chữ ký gọi với các
    reader khác qua routes/aiho.py.
    """
    system_prompt = SYSTEM_PROMPT + quy_mo_store.format_quy_mo_context(quy_mo) if quy_mo else SYSTEM_PROMPT
    model = read_and_validate_drawing_json(
        file_bytes, media_type, provider, system_prompt, _validate, prompt_version=SYSTEM_PROMPT_VERSION
    )
    return model.model_dump()
