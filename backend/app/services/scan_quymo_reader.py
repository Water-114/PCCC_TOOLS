"""AI đọc bản vẽ — "Lượt 0" quét NHẸ quy mô công trình (Quy mô Giai đoạn 1,
Phần A). Dùng cho route /api/aiho/scan-quymo, gọi TRÊN bản vẽ báo cháy hoặc
chữa cháy nước mà người dùng đã đính (KHÔNG phải bản vẽ kiến trúc riêng) —
mục đích CHỈ trích các field quy mô công trình NẾU bản vẽ tình cờ thể hiện
(khung tên/thuyết minh/ghi chú), KHÔNG chạy đủ checklist tiêu chí kỹ thuật
như baochay_reader.py/ccnuoc_reader.py đang làm cho hạng mục chính.

Khác quymo_reader.py (đọc ĐÚNG bản vẽ kiến trúc, "occ" luôn bắt buộc phải có
— xem ai_schema.QuyMoFields): ở đây bản vẽ báo cháy/ccnuoc THƯỜNG KHÔNG ghi
rõ công năng tổng thể công trình, nên dùng ScanQuyMoFields (mọi field kể cả
"occ" đều Optional) — không ép AI phải đoán "occ" chỉ để qua validation.

tim_thay=False khi bản vẽ không có bất kỳ thông tin quy mô nào (thay vì AI
tự bịa số liệu để trả lời cho có)."""

from .ai_reader_common import AIReaderError, read_and_validate_drawing_json, system_prompt_version
from .ai_schema import validate_scan_quy_mo_result

SYSTEM_PROMPT = """Bạn là kỹ sư PCCC đang quét NHANH 1 bản vẽ hệ thống PCCC (báo cháy, chữa cháy bằng nước, hoặc bản vẽ tương tự) để tìm THÔNG TIN QUY MÔ CÔNG TRÌNH — nếu bản vẽ này tình cờ có ghi (khung tên, thuyết minh, ghi chú, bảng thông tin công trình) — KHÔNG phải để rà soát kỹ thuật hệ thống đó.

YÊU CẦU THÊM: Đọc SỐ HIỆU BẢN VẼ ghi trong khung tên (title block) của chính bản vẽ này. Nếu khung tên không có, không rõ, hoặc bản vẽ không thể hiện số hiệu: ghi ĐÚNG NGUYÊN VĂN "Không xác định được số hiệu bản vẽ" ở trường "so_hieu_ban_ve" — TUYỆT ĐỐI không suy đoán.

Tìm CHÍNH XÁC các thông tin sau, CHỈ điền field nào bản vẽ THỰC SỰ thể hiện rõ ràng (để null nếu không thấy — TUYỆT ĐỐI không suy đoán/áng chừng cho đủ, không dùng kiến thức chung ngoài bản vẽ):
- "occ": công năng chính của công trình, CHỈ điền nếu bản vẽ ghi rõ tên loại hình công trình (ví dụ tên dự án/thuyết minh nêu rõ "chung cư", "trường học", "nhà xưởng"...) — nếu không chắc chắn, để null, KHÔNG tự đoán.
- "floors": số tầng nổi. "basements": số tầng hầm. "semiBasements": số tầng bán hầm.
- "areaFloor": diện tích 1 tầng điển hình (m²). "totalArea": tổng diện tích sàn ΣF toàn công trình (m²). "volume": khối tích V (m³).
- "hFire": chiều cao phục vụ PCCC (m), CHỈ điền nếu bản vẽ/thuyết minh nêu RÕ đúng khái niệm "chiều cao PCCC" (khác chiều cao kiến trúc tổng thể).
- "kids": số trẻ (chỉ nhà trẻ/mẫu giáo). "seats": số chỗ ngồi/khán đài (chỉ rạp hát/sân vận động).
- "hazard": hạng nguy hiểm cháy nổ A/B/C/D/E (chỉ nhà sản xuất/kho, nếu thuyết minh có nêu rõ).
- "pplFloor": số người lớn nhất trên 1 tầng, nếu thuyết minh có nêu.
- "hanhLangDaiNhat": chiều dài hành lang thoát nạn dài nhất (m), nếu bản vẽ thể hiện.
- "chieuCaoKeHang": chiều cao sắp xếp hàng hoá trên giá đỡ/kệ hàng (m), nếu bản vẽ là kho có kệ hàng và thể hiện rõ.
- "coBeXangDauNgoaiTroi": true nếu bản vẽ CÓ thể hiện bể chứa xăng dầu/dung môi dễ cháy đặt NGOÀI TRỜI, false nếu bản vẽ rõ ràng KHÔNG có, null nếu không đủ căn cứ để xác định.

NGUYÊN TẮC BẮT BUỘC:
- Nếu bản vẽ HOÀN TOÀN không có bất kỳ thông tin quy mô nào ở trên: "tim_thay": false, "quy_mo": null.
- Nếu có ít nhất 1 field tìm thấy: "tim_thay": true, "quy_mo": object chỉ điền đúng field tìm thấy, các field còn lại để null.
- Không suy đoán, không tự bịa số liệu để trả lời cho có.

Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON:
{
  "so_hieu_ban_ve": "số hiệu bản vẽ đọc từ khung tên, hoặc \\"Không xác định được số hiệu bản vẽ\\"",
  "tim_thay": true,
  "quy_mo": {
    "occ": null, "floors": null, "basements": null, "semiBasements": null,
    "areaFloor": null, "totalArea": null, "volume": null, "hFire": null,
    "kids": null, "seats": null, "hazard": null, "pplFloor": null,
    "hanhLangDaiNhat": null, "chieuCaoKeHang": null, "coBeXangDauNgoaiTroi": null
  }
}"""

SYSTEM_PROMPT_VERSION = system_prompt_version(SYSTEM_PROMPT)

ScanQuyMoReaderError = AIReaderError


def _validate(data: dict):
    return validate_scan_quy_mo_result(data)


def read_drawing(file_bytes: bytes, media_type: str, provider, quy_mo: dict = None) -> dict:
    """Gửi bản vẽ tới AI provider, validate qua Pydantic (kèm retry-repair 1
    lần nếu sai), trả về dict {so_hieu_ban_ve, tim_thay, quy_mo}.

    quy_mo: KHÔNG dùng ở đây (giữ tham số để đồng bộ chữ ký gọi qua
    routes/aiho.py — reader này SINH ra dữ liệu quy mô, không tiêu thụ).
    """
    model = read_and_validate_drawing_json(
        file_bytes, media_type, provider, SYSTEM_PROMPT, _validate, prompt_version=SYSTEM_PROMPT_VERSION
    )
    return model.model_dump()
