"""AI đọc bản vẽ — hệ thống báo cháy tự động.

Tiêu chí đối chiếu lấy trực tiếp từ mẫu MĐC B1 (báo cháy loại thường) và B2
(loại địa chỉ) qua mdc_filler.load_criteria_rows() — không code cứng nội dung
tiêu chí ở đây nữa, đổi mẫu chỉ cần thay file .docx trong mdc_templates/.
AI phải tự nhận diện bản vẽ dùng loại thường hay loại địa chỉ rồi áp đúng
bộ tiêu chí tương ứng — không suy đoán ngoài nội dung bản vẽ được cung cấp.
"""

from . import mdc_filler
from .ai_reader_common import AIReaderError, read_drawing_json


def _fmt_rows(rows):
    return "\n".join(
        f"id={r['id']} | [{r['doi_chieu']}] {r['quy_dinh']} (Căn cứ: {r['khoan_dieu']})"
        for r in rows
    )


def _build_system_prompt():
    rows_thuong = mdc_filler.load_criteria_rows("thuong")
    rows_dia_chi = mdc_filler.load_criteria_rows("dia_chi")
    return f"""Bạn là kỹ sư PCCC rà soát bản vẽ hệ thống báo cháy tự động, đối chiếu với mẫu đối chiếu MĐC B1 (báo cháy loại thường) hoặc B2 (báo cháy loại địa chỉ).

BƯỚC 1: Xác định bản vẽ được cung cấp là hệ báo cháy LOẠI THƯỜNG (zone theo khu vực, không có địa chỉ từng đầu báo) hay LOẠI ĐỊA CHỈ (mỗi đầu báo/module có địa chỉ riêng, thường dùng cho nhà cao tầng). Nêu rõ dấu hiệu nhận biết trên bản vẽ (ví dụ: ghi chú "hệ địa chỉ", loop/vòng lặp, hoặc chỉ có zone).

BƯỚC 2: CHỈ đối chiếu bản vẽ với danh sách tiêu chí thuộc ĐÚNG loại đã xác định ở Bước 1 (KHÔNG trả lời cho danh sách của loại còn lại). Mỗi dòng tiêu chí có sẵn "id" — khi trả lời PHẢI giữ nguyên đúng id đó, và phải trả lời ĐỦ cho TẤT CẢ id thuộc danh sách của loại đã xác định, không bỏ sót. Với mỗi id, trả về:
- "noi_dung_thiet_ke": nội dung điền vào cột "Nội dung thiết kế" của mẫu MĐC gốc — ngắn gọn, đúng mạch đối chiếu (dùng gạch đầu dòng "-" nếu nhiều ý), nêu số liệu cụ thể NHÌN THẤY trên bản vẽ. Nếu bản vẽ không thể hiện đủ thông tin để kết luận: ghi đúng "Chưa thể hiện trên bản vẽ cung cấp".
- "ket_luan": "dat" nếu nội dung trên bản vẽ đáp ứng đúng quy định; "chua_dat" nếu đã thể hiện nhưng vi phạm giá trị/quy định; "chua_the_hien" nếu bản vẽ không đủ thông tin để kết luận.

--- DANH SÁCH TIÊU CHÍ LOẠI THƯỜNG (MĐC B1) ---
{_fmt_rows(rows_thuong)}

--- DANH SÁCH TIÊU CHÍ LOẠI ĐỊA CHỈ (MĐC B2) ---
{_fmt_rows(rows_dia_chi)}

BƯỚC 3: Với MỖI id có "ket_luan" là "chua_dat" hoặc "chua_the_hien" ở bước 2, soạn thêm một câu kiến nghị theo đúng văn phong công văn PC07:
- Mở đầu bằng động từ mệnh lệnh phù hợp: "Thể hiện rõ ..." (nếu là "chua_the_hien" — thông tin đáng lẽ có trên bản vẽ nhưng chưa vẽ/ghi), "Bổ sung ..." (nếu cần thêm chi tiết/thiết bị/bản vẽ), hoặc "Thuyết minh rõ ..." (nếu cần giải trình bằng lời).
- Một câu mạch lạc, nêu rõ đối tượng cụ thể trên bản vẽ + số liệu định lượng của tiêu chuẩn (lấy từ đúng nội dung quy định của id tương ứng).
- Kết câu bằng phần căn cứ, in trong ngoặc đơn, lấy ĐÚNG "Khoản, Điều" đã ghi ở id đó — không tự bịa số Điều khác.
- Xếp mỗi kiến nghị vào đúng 1 trong 4 nhóm sau:
  - "chua_the_hien": nhóm I (nội dung chưa thể hiện trên bản vẽ).
  - "chua_dat": nhóm III (nội dung đã thể hiện nhưng vi phạm giá trị/quy định của tiêu chuẩn).
  - Nhóm II (chưa thống nhất giữa nhiều nguồn số liệu) và nhóm IV (đề xuất bổ sung hồ sơ/bản vẽ mới) CHỈ dùng khi có căn cứ rõ ràng từ chính bản vẽ này (ví dụ: hoàn toàn thiếu hẳn sơ đồ nguyên lý → nhóm IV); nếu không có căn cứ, để mảng rỗng — KHÔNG cố tạo kiến nghị cho đủ 4 nhóm.
- Nếu mọi id đều "dat", để cả 4 mảng đều rỗng.

NGUYÊN TẮC BẮT BUỘC:
- Chỉ đánh giá dựa trên nội dung THỰC SỰ thể hiện trên bản vẽ được cung cấp. Không suy đoán, không dùng kiến thức chung ngoài bản vẽ.
- Không được bỏ sót bất kỳ id nào thuộc danh sách của loại đã xác định.

Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON:
{{
  "loai_he_thong": "thuong" hoặc "dia_chi",
  "ly_do_nhan_dien": "câu ngắn giải thích vì sao xác định loại này",
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

BaoChayReaderError = AIReaderError  # giữ tên cũ để không phải sửa chỗ khác đang import


def read_drawing(file_bytes: bytes, media_type: str, provider) -> dict:
    """Gửi bản vẽ (ảnh hoặc PDF) kèm tiêu chí tới AI provider, trả về dict đã parse JSON."""
    return read_drawing_json(file_bytes, media_type, provider, SYSTEM_PROMPT)
