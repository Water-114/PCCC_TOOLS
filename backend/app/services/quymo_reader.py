"""AI đọc bản vẽ — hạng mục "Quy mô" (Form A / MĐC Kiến trúc).

Khác 4 reader kia (báo cháy/điện/nước/đèn-bình): Form A hầu hết các dòng "Đối
tượng trang bị" được điền bằng CODE THUẦN qua các hàm evaluate_*() có sẵn
(tham_dinh.py/he_thong_bat_buoc.py/phuong_tien.py) — xem quy_mo_store.py. AI ở
đây CHỈ làm 2 việc:
1. Trích xuất CÓ CẤU TRÚC các field quy mô công trình (occ, floors, totalArea,
   hFire...) từ bản vẽ kiến trúc — dùng làm input truyền THẲNG vào các
   evaluate_*() (đúng tên field, xem ai_schema.QuyMoFields).
2. Trả lời 2 tiêu chí KHÔNG có rule sẵn — Bảng A.2 ("hạng mục/khu vực") và
   Bảng A.4 ("thiết bị") của QCVN 10:2025/BCA, cho CẢ báo cháy lẫn chữa cháy
   tự động (4 câu trả lời độc lập, xử lý giống hệt nhau — owner xác nhận
   không phân biệt A.2/A.4).
"""

from .ai_reader_common import (
    AIReaderError,
    format_danh_muc_ban_ve_instruction,
    read_and_validate_drawing_json_multi,
    system_prompt_version,
)
from .ai_schema import validate_quy_mo_reader_result
from .tham_dinh import OCCUPATIONS

_A2_A4_TEXT = {
    "bang_a2_bao_chay": (
        "Đối với hạng mục/khu vực — báo cháy",
        "Danh mục hạng mục/khu vực phải trang bị hệ thống báo cháy tự động theo quy định tại Bảng A.2.",
        "Điều 2.1 QCVN 10:2025/BCA, Bảng A.2 QCVN 10:2025/BCA",
    ),
    "bang_a4_bao_chay": (
        "Đối với thiết bị — báo cháy",
        "Danh mục thiết bị phải trang bị hệ thống báo cháy tự động theo quy định tại Bảng A.4.",
        "Bảng A.4 QCVN 10:2025/BCA",
    ),
    "bang_a2_sprinkler": (
        "Đối với hạng mục/khu vực — chữa cháy tự động",
        "Danh mục hạng mục/khu vực phải trang bị hệ thống chữa cháy tự động theo quy định tại Bảng A.2.",
        "Điều 2.5 QCVN 10:2025/BCA, Bảng A.2 QCVN 10:2025/BCA",
    ),
    "bang_a4_sprinkler": (
        "Đối với thiết bị — chữa cháy tự động",
        "Danh mục thiết bị phải trang bị hệ thống chữa cháy tự động, thiết bị chữa cháy tự động theo quy định tại Bảng A.4.",
        "Bảng A.4 QCVN 10:2025/BCA",
    ),
}

KHONG_XAC_DINH_A2_A4 = "Chưa xác định — cần đọc bản vẽ (Bảng A.2/A.4 QCVN 10:2025/BCA)."


def _fmt_occupations():
    return "\n".join(f'- "{o["id"]}": {o["label"]}' for o in OCCUPATIONS)


def _fmt_a2_a4():
    return "\n".join(
        f'- "{key}" ({label}): {quy_dinh} (Căn cứ: {khoan_dieu})'
        for key, (label, quy_dinh, khoan_dieu) in _A2_A4_TEXT.items()
    )


def _build_system_prompt():
    return f"""Bạn là kỹ sư PCCC đọc bản vẽ kiến trúc (mặt bằng, mặt cắt, thuyết minh) để xác định QUY MÔ công trình, phục vụ đối chiếu mẫu MĐC "Kiến trúc" (Form A).

YÊU CẦU THÊM: Đọc SỐ HIỆU BẢN VẼ ghi trong khung tên (title block) của chính bản vẽ này. Nếu khung tên không có, không rõ, hoặc bản vẽ không thể hiện số hiệu: ghi ĐÚNG NGUYÊN VĂN "Không xác định được số hiệu bản vẽ" ở trường "so_hieu_ban_ve" — TUYỆT ĐỐI không suy đoán, không tự đặt số hiệu.

BƯỚC 1 — Trích xuất quy mô công trình vào object "quy_mo". CHỈ điền field nào bản vẽ THỰC SỰ thể hiện (để null nếu không thấy — TUYỆT ĐỐI không suy đoán/áng chừng cho đủ):
- "occ" (BẮT BUỘC phải có giá trị): công năng chính của công trình — PHẢI chọn ĐÚNG 1 trong danh sách id sau (không tự đặt id khác, chọn công năng gần đúng nhất nếu bản vẽ không ghi rõ tên loại hình):
{_fmt_occupations()}
- "floors": số tầng nổi (không tính hầm/bán hầm). "basements": số tầng hầm. "semiBasements": số tầng bán hầm.
- "areaFloor": diện tích 1 tầng điển hình (m²). "totalArea": tổng diện tích sàn ΣF toàn công trình (m²). "volume": khối tích V (m³).
- "hFire": chiều cao phục vụ PCCC (Điều 1.4.9 QCVN 06:2022/BXD và Sửa đổi 1:2023 — tính từ mặt đường xe chữa cháy tiếp cận đến mép dưới cửa sổ mở của tầng trên cùng, KHÁC chiều cao kiến trúc tổng thể — chỉ điền nếu bản vẽ/thuyết minh nêu rõ đúng khái niệm này).
- "kids": số trẻ (chỉ nhà trẻ/mẫu giáo). "seats": số chỗ ngồi/khán đài (chỉ rạp hát/sân vận động/nhà thi đấu).
- "hazard": hạng nguy hiểm cháy nổ A/B/C/D/E (chỉ nhà sản xuất/kho, nếu thuyết minh có nêu).
- "garaKin" ("kin"/"ho"), "garaKC12" ("le12"/"gt12"), "garaBcl" ("I".."V"), "garaCapS" ("S0".."S3"): chỉ áp dụng nhà để xe (gara).
- "pplFloor": số người lớn nhất trên 1 tầng (nếu thuyết minh có nêu).
- "extLevel" ("thap"/"tb"/"cao"): mức nguy hiểm cháy dùng tính bình chữa cháy — chỉ điền nếu thuyết minh nêu rõ, để null nếu không chắc (hệ thống sẽ tự suy ra theo công năng khi thiếu).
- "hanhLangDaiNhat": chiều dài hành lang thoát nạn dài nhất (m), nếu bản vẽ thể hiện.
- "chieuCaoKeHang": chiều cao sắp xếp hàng hoá trên giá đỡ/kệ hàng (m) — chỉ điền nếu công trình là kho có kệ hàng và bản vẽ/thuyết minh thể hiện rõ.
- "coBeXangDauNgoaiTroi": true nếu bản vẽ CÓ thể hiện bể chứa xăng dầu/dung môi dễ cháy đặt NGOÀI TRỜI, false nếu bản vẽ rõ ràng KHÔNG có, để null nếu không đủ căn cứ để xác định.

BƯỚC 2 — Với MỖI mục sau, đọc bản vẽ xem có hạng mục/khu vực hoặc thiết bị nào thuộc danh mục quy định hay không, điền vào nếu đọc thấy trên bản vẽ; nếu bản vẽ không thể hiện đủ thông tin để kết luận: ghi ĐÚNG NGUYÊN VĂN "{KHONG_XAC_DINH_A2_A4}" — KHÔNG suy đoán, KHÔNG tự mặc định là "Bổ sung":
{_fmt_a2_a4()}

NGUYÊN TẮC BẮT BUỘC:
- Chỉ dựa trên nội dung THỰC SỰ thể hiện trên bản vẽ được cung cấp. Không suy đoán, không dùng kiến thức chung ngoài bản vẽ.
- "occ" là field DUY NHẤT trong "quy_mo" bắt buộc phải có giá trị — các field còn lại được phép null nếu bản vẽ không thể hiện.

Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON:
{{
  "so_hieu_ban_ve": "số hiệu bản vẽ đọc từ khung tên, hoặc \\"Không xác định được số hiệu bản vẽ\\"",
  "quy_mo": {{
    "occ": "...",
    "floors": null, "basements": null, "semiBasements": null,
    "areaFloor": null, "totalArea": null, "volume": null, "hFire": null,
    "kids": null, "seats": null, "hazard": null,
    "garaKin": null, "garaKC12": null, "garaBcl": null, "garaCapS": null,
    "pplFloor": null, "extLevel": null, "hanhLangDaiNhat": null,
    "chieuCaoKeHang": null, "coBeXangDauNgoaiTroi": null
  }},
  "bang_a2_bao_chay": "...",
  "bang_a4_bao_chay": "...",
  "bang_a2_sprinkler": "...",
  "bang_a4_sprinkler": "..."
}}"""


SYSTEM_PROMPT = _build_system_prompt()
SYSTEM_PROMPT_VERSION = system_prompt_version(SYSTEM_PROMPT)

QuyMoReaderError = AIReaderError


def _validate(data: dict):
    return validate_quy_mo_reader_result(data)


def read_drawing(files: list, provider, quy_mo: dict = None) -> dict:
    """Gửi (các) bản vẽ kiến trúc (files: list[(bytes, media_type)], tối đa 3
    — Batch 5A Pha 1) tới AI provider trong CÙNG 1 request, validate qua
    Pydantic (kèm retry-repair 1 lần nếu sai), trả về dict {so_hieu_ban_ve,
    quy_mo, bang_a2_bao_chay, ...}.

    quy_mo: KHÔNG dùng ở đây — reader này SINH ra dữ liệu quy mô (không tiêu
    thụ dữ liệu quy mô có sẵn). Nhận tham số này chỉ để đồng bộ chữ ký gọi với
    4 reader kia qua routes/aiho.py::_handle_read_request().
    """
    system_prompt = SYSTEM_PROMPT + format_danh_muc_ban_ve_instruction(len(files))
    model = read_and_validate_drawing_json_multi(files, provider, system_prompt, _validate)
    return model.model_dump()
