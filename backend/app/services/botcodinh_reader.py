"""AI đọc bản vẽ — hệ thống chữa cháy bằng bọt cố định cho bể chứa xăng dầu (B7).

Độc lập hoàn toàn với khibotsolkhi_reader.py (B8-B11) — B7 chỉ có ĐÚNG 1 mẫu
đối chiếu MĐC (không cần bước phân loại "1-trong-N" như B8-B11), nên viết theo
đúng khuôn dienpccc_reader.py (đơn giản, dùng thẳng ReaderResult gốc từ
ai_schema.py, không cần thêm class Pydantic mới). B7 khác hẳn nhóm B8-B11 —
bảo vệ bể chứa dầu mỏ/sản phẩm dầu mỏ NGOÀI TRỜI, không phải phòng kín, dùng
TCVN 5307:2009 hoàn toàn riêng (không thuộc họ TCVN 7161/6101/13333 của
B8-B11) — vì vậy 3 quy tắc mặc định "tính thường xuyên có người"/"kết cấu bao
che kín khí" của B8-B11 KHÔNG áp dụng ở đây (bể ngoài trời không có khái niệm
"phòng bảo vệ").

Nguồn số liệu DUY NHẤT: bot-co-dinh-tcvn5307.md (skill ra-mau-doi-chieu-pccc)
— không hardcode số liệu ngoài file này.

Điểm đặc thù DUY NHẤT cần xử lý: cặp tiêu chí loại trừ lẫn nhau theo loại mái
bể — id=5 (mái CỐ ĐỊNH, áp Bảng 9/10) vs id=7 (mái NỔI hoặc CÓ PHAO TRONG, áp
Điều 5.9.11) — dùng exclusive_alternative_block() dùng chung từ
ai_reader_common.py (đã refactor ra khỏi khibotsolkhi_reader.py để 2 module
cùng tái dùng, tránh trùng lặp logic)."""

from . import mdc_filler, quy_mo_store
from .ai_reader_common import (
    DOC_CHU_XOAY_VA_KY_HIEU,
    KHONG_UOC_LUONG_KHOANG_CACH,
    NHOM_II_MAU_THUAN_CHECKLIST,
    STANDARD_PHRASES,
    TOA_DO_TRUC_KHOANG_CACH,
    AIReaderError,
    exclusive_alternative_block,
    read_and_validate_drawing_json,
    system_prompt_version,
)
from .ai_schema import ReaderResult, validate_reader_result

# --- id=5 (mai co dinh, Bang 9/10) vs id=7 (mai noi/phao trong, D 5.9.11) ---
_MAI_BE_BLOCK = exclusive_alternative_block(
    "id=5 và id=7 (cường độ, thời gian phun theo loại mái bể)",
    [
        ((5,), "bể MÁI CỐ ĐỊNH (áp Bảng 9 nếu bọt nở trung bình / Bảng 10 nếu bọt nở thấp)"),
        ((7,), "bể MÁI NỔI hoặc bể CÓ PHAO TRONG (đĩa kép/đĩa đơn kim loại — áp Điều 5.9.11)"),
    ],
    ghi_chu="LƯU Ý: nhầm bảng cường độ/thời gian giữa 2 loại mái bể là lỗi phổ biến nhất khi rà B7 — xác định ĐÚNG loại mái bể từ bản vẽ (ghi chú/mặt cắt bể) trước khi chọn nhánh.",
)


def _fmt_rows(rows):
    return "\n".join(
        f"id={r['id']} | [{r['doi_chieu']}] {r['quy_dinh']} (Căn cứ: {r['khoan_dieu']})"
        for r in rows
    )


def _build_system_prompt():
    rows = mdc_filler.load_criteria_rows("bot_co_dinh")
    return f"""Bạn là kỹ sư PCCC rà soát bản vẽ hệ thống chữa cháy bằng bọt cố định cho bể chứa xăng dầu/sản phẩm dầu mỏ NGOÀI TRỜI (kho DM&SPDM), đối chiếu với mẫu đối chiếu MĐC B7. Đây là hệ thống bảo vệ bể chứa NGOÀI TRỜI, KHÁC hẳn hệ thống chữa cháy khí/sol-khí cho phòng kín (B8-B11) — không có khái niệm "phòng bảo vệ" ở đây.

YÊU CẦU THÊM: Đọc SỐ HIỆU BẢN VẼ ghi trong khung tên (title block) của chính bản vẽ này (thường ở góc dưới bên phải, ô ghi "Số bản vẽ" / "Ký hiệu bản vẽ" / "Drawing No."). Nếu khung tên không có, không rõ, hoặc bản vẽ không thể hiện số hiệu: ghi ĐÚNG NGUYÊN VĂN "Không xác định được số hiệu bản vẽ" ở trường "so_hieu_ban_ve" — TUYỆT ĐỐI không suy đoán, không tự đặt số hiệu.

BƯỚC 1: Với MỖI dòng tiêu chí dưới đây (mỗi dòng có sẵn "id" — khi trả lời PHẢI giữ nguyên đúng id đó, và phải trả lời ĐỦ cho TẤT CẢ id, không bỏ sót), đối chiếu với bản vẽ và trả về:
- "noi_dung_thiet_ke": nội dung điền vào cột "Nội dung thiết kế" của mẫu MĐC gốc — ngắn gọn, đúng mạch đối chiếu (dùng gạch đầu dòng "-" nếu nhiều ý), nêu số liệu cụ thể NHÌN THẤY trên bản vẽ. Nếu bản vẽ không thể hiện đủ thông tin để kết luận: ghi đúng "Chưa thể hiện trên bản vẽ cung cấp".
{TOA_DO_TRUC_KHOANG_CACH}
{STANDARD_PHRASES}
- "ket_luan": "dat" nếu nội dung trên bản vẽ đáp ứng đúng quy định; "chua_dat" nếu đã thể hiện nhưng vi phạm giá trị/quy định; "chua_the_hien" nếu bản vẽ không đủ thông tin để kết luận; "khong_ap_dung" CHỈ dùng cho đúng id có hướng dẫn riêng bên dưới chỉ định rõ (cặp loại trừ theo loại mái bể) — KHÔNG tự ý dùng cho id khác.

{_MAI_BE_BLOCK}
--- DANH SÁCH TIÊU CHÍ (MĐC B7 — chữa cháy bằng bọt cố định cho bể chứa xăng dầu) ---
{_fmt_rows(rows)}

BƯỚC 2: Với MỖI id có "ket_luan" là "chua_dat" hoặc "chua_the_hien" ở bước 1, soạn thêm một câu kiến nghị theo đúng văn phong công văn PC07:
- Mở đầu bằng động từ mệnh lệnh phù hợp: "Thể hiện rõ ..." (nếu là "chua_the_hien" — thông tin đáng lẽ có trên bản vẽ nhưng chưa vẽ/ghi), "Bổ sung ..." (nếu cần thêm chi tiết/thiết bị/bản vẽ), hoặc "Thuyết minh rõ ..." (nếu cần giải trình bằng lời).
- Một câu mạch lạc, nêu rõ đối tượng cụ thể trên bản vẽ + số liệu định lượng của tiêu chuẩn (lấy từ đúng nội dung quy định của id tương ứng).
{TOA_DO_TRUC_KHOANG_CACH}
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
{KHONG_UOC_LUONG_KHOANG_CACH}
{DOC_CHU_XOAY_VA_KY_HIEU}

Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON:
{{
  "so_hieu_ban_ve": "số hiệu bản vẽ đọc từ khung tên, hoặc \\"Không xác định được số hiệu bản vẽ\\"",
  "items": [
    {{"id": 2, "noi_dung_thiet_ke": "...", "ket_luan": "dat" | "chua_dat" | "chua_the_hien" | "khong_ap_dung"}}
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

BotCoDinhReaderError = AIReaderError

_EXPECTED_IDS = {r["id"] for r in mdc_filler.load_criteria_rows("bot_co_dinh")}


def _validate(data: dict):
    return validate_reader_result(data, _EXPECTED_IDS, ReaderResult)


def read_drawing(file_bytes: bytes, media_type: str, provider, quy_mo: dict = None) -> dict:
    """Gửi bản vẽ (ảnh hoặc PDF) kèm tiêu chí tới AI provider, validate qua Pydantic
    (kèm retry-repair 1 lần nếu sai), trả về dict.

    quy_mo: dữ liệu quy mô công trình (hạng mục "Quy mô") của CÙNG phiên Bộ hồ
    sơ, nếu người dùng CÓ đính kèm — HOÀN TOÀN TUỲ CHỌN (None nếu không đính,
    hành vi giữ nguyên 100% như trước). B7 là bể ngoài trời nên quy mô công
    trình (số tầng/diện tích...) ít liên quan trực tiếp, nhưng vẫn nhận tham
    số này để đồng bộ chữ ký gọi với các reader khác qua routes/aiho.py.
    """
    system_prompt = SYSTEM_PROMPT + quy_mo_store.format_quy_mo_context(quy_mo) if quy_mo else SYSTEM_PROMPT
    model = read_and_validate_drawing_json(
        file_bytes, media_type, provider, system_prompt, _validate, prompt_version=SYSTEM_PROMPT_VERSION
    )
    return model.model_dump()
