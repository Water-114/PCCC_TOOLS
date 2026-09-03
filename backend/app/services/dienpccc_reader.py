"""AI đọc bản vẽ — hệ thống điện phục vụ PCCC.

Tiêu chí đối chiếu lấy trực tiếp từ mẫu MĐC B14 qua mdc_filler.load_criteria_rows()
— không code cứng nội dung tiêu chí ở đây, đổi mẫu chỉ cần thay file .docx trong
mdc_templates/. Khác báo cháy: không cần bước phân loại (chỉ có 1 mẫu B14 duy nhất).
"""

from . import mdc_filler, quy_mo_store
from .ai_reader_common import (
    DOC_CHU_XOAY_VA_KY_HIEU,
    NHOM_II_MAU_THUAN_CHECKLIST,
    STANDARD_PHRASES,
    AIReaderError,
    read_and_validate_drawing_json_multi,
    system_prompt_version,
)
from .ai_schema import ReaderResult, validate_reader_result


def _fmt_rows(rows):
    return "\n".join(
        f"id={r['id']} | [{r['doi_chieu']}] {r['quy_dinh']} (Căn cứ: {r['khoan_dieu']})"
        for r in rows
    )


def _build_system_prompt():
    rows = mdc_filler.load_criteria_rows("dien_pccc")
    return f"""Bạn là kỹ sư PCCC rà soát bản vẽ hệ thống điện phục vụ PCCC (cấp nguồn ưu tiên, dây/cáp chống cháy, tủ điện PCCC), đối chiếu với mẫu đối chiếu MĐC B14.

YÊU CẦU THÊM: Đọc SỐ HIỆU BẢN VẼ ghi trong khung tên (title block) của chính bản vẽ này (thường ở góc dưới bên phải, ô ghi "Số bản vẽ" / "Ký hiệu bản vẽ" / "Drawing No."). Nếu khung tên không có, không rõ, hoặc bản vẽ không thể hiện số hiệu: ghi ĐÚNG NGUYÊN VĂN "Không xác định được số hiệu bản vẽ" ở trường "so_hieu_ban_ve" — TUYỆT ĐỐI không suy đoán, không tự đặt số hiệu.

BƯỚC 1: Với MỖI dòng tiêu chí dưới đây (mỗi dòng có sẵn "id" — khi trả lời PHẢI giữ nguyên đúng id đó, và phải trả lời ĐỦ cho TẤT CẢ id, không bỏ sót), đối chiếu với bản vẽ và trả về:
- "noi_dung_thiet_ke": nội dung điền vào cột "Nội dung thiết kế" của mẫu MĐC gốc — ngắn gọn, đúng mạch đối chiếu (dùng gạch đầu dòng "-" nếu nhiều ý), nêu số liệu cụ thể NHÌN THẤY trên bản vẽ. Nếu bản vẽ không thể hiện đủ thông tin để kết luận: ghi đúng "Chưa thể hiện trên bản vẽ cung cấp".
{STANDARD_PHRASES}
- "ket_luan": "dat" nếu nội dung trên bản vẽ đáp ứng đúng quy định; "chua_dat" nếu đã thể hiện nhưng vi phạm giá trị/quy định; "chua_the_hien" nếu bản vẽ không đủ thông tin để kết luận.

--- DANH SÁCH TIÊU CHÍ (MĐC B14 — Điện phục vụ PCCC) ---
{_fmt_rows(rows)}

BƯỚC 2: Với MỖI id có "ket_luan" là "chua_dat" hoặc "chua_the_hien" ở bước 1, soạn thêm một câu kiến nghị theo đúng văn phong công văn PC07:
- Mở đầu bằng động từ mệnh lệnh phù hợp: "Thể hiện rõ ..." (nếu là "chua_the_hien" — thông tin đáng lẽ có trên bản vẽ nhưng chưa vẽ/ghi), "Bổ sung ..." (nếu cần thêm chi tiết/thiết bị/bản vẽ), hoặc "Thuyết minh rõ ..." (nếu cần giải trình bằng lời).
- Một câu mạch lạc, nêu rõ đối tượng cụ thể trên bản vẽ + số liệu định lượng của tiêu chuẩn (lấy từ đúng nội dung quy định của id tương ứng).
- Kết câu bằng phần căn cứ, in trong ngoặc đơn, lấy ĐÚNG "Điều, Khoản" đã ghi ở id đó — không tự bịa số Điều khác.
- Xếp mỗi kiến nghị vào đúng 1 trong 4 nhóm sau:
  - "chua_the_hien": nhóm I (nội dung chưa thể hiện trên bản vẽ).
  - "chua_dat": nhóm III (nội dung đã thể hiện nhưng vi phạm giá trị/quy định của tiêu chuẩn).
  - Nhóm II (chưa thống nhất giữa nhiều nguồn số liệu) và nhóm IV (đề xuất bổ sung hồ sơ/bản vẽ mới) CHỈ dùng khi có căn cứ rõ ràng từ chính bản vẽ này; nếu không có căn cứ, để mảng rỗng — KHÔNG cố tạo kiến nghị cho đủ 4 nhóm.
{NHOM_II_MAU_THUAN_CHECKLIST}
- Nếu mọi id đều "dat", để cả 4 mảng đều rỗng.

NGUYÊN TẮC BẮT BUỘC:
- Chỉ đánh giá dựa trên nội dung THỰC SỰ thể hiện trên bản vẽ được cung cấp. Không suy đoán, không dùng kiến thức chung ngoài bản vẽ.
- Không được bỏ sót bất kỳ id nào.
{DOC_CHU_XOAY_VA_KY_HIEU}

Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON:
{{
  "so_hieu_ban_ve": "số hiệu bản vẽ đọc từ khung tên, hoặc \"Không xác định được số hiệu bản vẽ\"",
  "items": [
    {{"id": 2, "noi_dung_thiet_ke": "...", "ket_luan": "dat" | "chua_dat" | "chua_the_hien"}}
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

DienPcccReaderError = AIReaderError  # cùng loại lỗi dùng chung với baochay_reader

_EXPECTED_IDS = {r["id"] for r in mdc_filler.load_criteria_rows("dien_pccc")}


def _validate(data: dict):
    return validate_reader_result(data, _EXPECTED_IDS, ReaderResult)


def read_drawing(files: list, provider, quy_mo: dict = None) -> dict:
    """Gửi (các) bản vẽ (files: list[(bytes, media_type)], tối đa 3 — Batch 5A
    Pha 1) kèm tiêu chí tới AI provider trong CÙNG 1 request, validate qua
    Pydantic (kèm retry-repair 1 lần nếu sai), trả về dict.

    quy_mo: dữ liệu quy mô công trình (hạng mục "Quy mô") của CÙNG phiên Bộ hồ
    sơ, nếu người dùng CÓ đính kèm — HOÀN TOÀN TUỲ CHỌN (None nếu không đính,
    hành vi giữ nguyên 100% như trước).
    """
    system_prompt = SYSTEM_PROMPT + quy_mo_store.format_quy_mo_context(quy_mo) if quy_mo else SYSTEM_PROMPT
    model = read_and_validate_drawing_json_multi(
        files, provider, system_prompt, _validate, prompt_version=SYSTEM_PROMPT_VERSION
    )
    return model.model_dump()
