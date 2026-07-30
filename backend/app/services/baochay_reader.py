"""AI đọc bản vẽ — hệ thống báo cháy tự động (thí điểm 1 hạng mục).

Rút gọn ~8-10 tiêu chí chính từ mẫu đối chiếu MĐC B1 (báo cháy loại thường)
và B2 (báo cháy loại địa chỉ), dựa trên TCVN 7568-14:2025 và QCVN 06:2022.
AI phải tự nhận diện bản vẽ dùng loại thường hay loại địa chỉ rồi áp đúng
bộ tiêu chí tương ứng — không suy đoán ngoài nội dung bản vẽ được cung cấp.
"""

import base64
import json

CRITERIA_THUONG = [
    {"muc": "Vùng phát hiện cháy",
     "yeu_cau": "Một vùng phát hiện cháy giới hạn ≤ 2.000 m² diện tích sàn liên tục; kích thước lớn nhất ≤ 100 m, giới hạn trong một tầng nhà.",
     "can_cu": "Điều 5.7.2.1-5.7.2.5 TCVN 7568-14:2025"},
    {"muc": "Vị trí lắp đầu báo cháy",
     "yeu_cau": "Đầu báo cháy lắp gần đỉnh mái dốc/mái/bề mặt phẳng, tránh vùng không khí chết; đúng loại đầu báo theo đặc điểm khu vực (khói/nhiệt/lửa/hỗn hợp).",
     "can_cu": "Điều 5.9.1, 4.1.5 TCVN 7568-14:2025"},
    {"muc": "Khoảng cách đầu báo cháy khói/nhiệt kiểu điểm trên trần phẳng",
     "yeu_cau": "Đầu báo khói: khoảng cách đến điểm bất kỳ ≤ 7,2 m, giữa 2 đầu báo ≤ 10,2 m, đến tường ≤ 5,1 m. Đầu báo nhiệt: ≤ 5,1 m / ≤ 7,2 m tương ứng.",
     "can_cu": "Điều 5.9.1.1.2, 5.9.2.1.2 TCVN 7568-14:2025"},
    {"muc": "Trung tâm báo cháy — vị trí lắp đặt",
     "yeu_cau": "Đặt nơi có người trực 24/24 (hoặc có chức năng truyền tín hiệu đến nơi trực); có điện thoại liên lạc trực tiếp với Cảnh sát PCCC; khoảng trống phía trước tủ ≥ 1,5 m.",
     "can_cu": "Điều 5.12.2-5.12.7 TCVN 7568-14:2025"},
    {"muc": "Nguồn điện cấp cho tủ báo cháy",
     "yeu_cau": "Hai nguồn điện độc lập (220V xoay chiều + ắc quy dự phòng); ắc quy đảm bảo ≥ 24 giờ chế độ thường trực và 30 phút khi có cháy, nạp điện tự động.",
     "can_cu": "Điều 5.13, 5.13.1 TCVN 7568-14:2025"},
    {"muc": "Hộp nút ấn báo cháy",
     "yeu_cau": "Lắp ở vị trí dễ thấy, gần lối ra; khoảng cách giữa các hộp nút ấn ≤ 45 m; chiều cao lắp đặt (1,4 ± 0,2) m.",
     "can_cu": "Điều 5.10.1-5.10.4 TCVN 7568-14:2025"},
    {"muc": "Thiết bị báo cháy bằng âm thanh",
     "yeu_cau": "Mức cường độ âm thanh ≥ 65 dBA và ≤ 105 dBA, lớn hơn tiếng ồn môi trường xung quanh ≥ 10 dBA (khu vực ngủ: ≥ 15 dBA và ≥ 75 dBA).",
     "can_cu": "Điều 5.11.2.1 TCVN 7568-14:2025"},
    {"muc": "Cáp, dây tín hiệu",
     "yeu_cau": "Cáp/dây tín hiệu điều khiển thiết bị ngoại vi và kích hoạt chữa cháy tự động phải chịu nhiệt cao (chịu lửa ≥ 30 phút); tiết diện lõi đồng ≥ 0,75 mm² (đường trục chính).",
     "can_cu": "Điều 5.14.6, 5.14.9, 5.14.5 TCVN 7568-14:2025"},
]

CRITERIA_DIA_CHI = CRITERIA_THUONG + [
    {"muc": "Đối tượng bắt buộc báo cháy địa chỉ",
     "yeu_cau": "Nhà nhóm F1.2, F4.2, F4.3 và nhà hỗn hợp có chiều cao PCCC 50-150 m; nhà chung cư F1.3 cao 75-150 m phải trang bị báo cháy địa chỉ, báo rõ địa chỉ từng căn hộ/khu vực.",
     "can_cu": "Điều A.2.26.1 QCVN 06:2022, Điều A.3.1.16 Sửa đổi 1:2023 QCVN 06:2022"},
    {"muc": "Cáp cấp nguồn cho hệ thống bảo vệ chống cháy (nhà cao 50-150m)",
     "yeu_cau": "Đấu nối dây điện từ thiết bị phân phối đến hệ thống báo cháy/chữa cháy/hút xả khói/chiếu sáng thoát nạn dùng cáp chịu lửa ≥ 120 phút; nguồn điện duy trì ≥ 3 giờ từ 2 nguồn độc lập.",
     "can_cu": "Điều A.2.28.1, A.2.28.8 QCVN 06:2022"},
]


def _fmt_criteria(items):
    lines = []
    for i, c in enumerate(items, 1):
        lines.append(f"{i}. [{c['muc']}] {c['yeu_cau']} (Căn cứ: {c['can_cu']})")
    return "\n".join(lines)


SYSTEM_PROMPT = f"""Bạn là kỹ sư PCCC rà soát bản vẽ hệ thống báo cháy tự động, đối chiếu với mẫu đối chiếu MĐC B1 (báo cháy loại thường) hoặc B2 (báo cháy loại địa chỉ).

BƯỚC 1: Xác định bản vẽ được cung cấp là hệ báo cháy LOẠI THƯỜNG (zone theo khu vực, không có địa chỉ từng đầu báo) hay LOẠI ĐỊA CHỈ (mỗi đầu báo/module có địa chỉ riêng, thường dùng cho nhà cao tầng). Nêu rõ dấu hiệu nhận biết trên bản vẽ (ví dụ: ghi chú "hệ địa chỉ", loop/vòng lặp, hoặc chỉ có zone).

BƯỚC 2: Đối chiếu bản vẽ với ĐÚNG bộ tiêu chí dưới đây (dùng bộ LOẠI THƯỜNG nếu là loại thường; dùng bộ LOẠI ĐỊA CHỈ — đã gồm thêm tiêu chí riêng — nếu là loại địa chỉ):

--- TIÊU CHÍ LOẠI THƯỜNG (MĐC B1) ---
{_fmt_criteria(CRITERIA_THUONG)}

--- TIÊU CHÍ BỔ SUNG CHO LOẠI ĐỊA CHỈ (MĐC B2, dùng thêm các mục này ngoài các mục trên) ---
{_fmt_criteria(CRITERIA_DIA_CHI[len(CRITERIA_THUONG):])}

NGUYÊN TẮC BẮT BUỘC:
- Chỉ đánh giá dựa trên nội dung THỰC SỰ thể hiện trên bản vẽ được cung cấp. Không suy đoán, không dùng kiến thức chung ngoài bản vẽ.
- Nếu một tiêu chí không có đủ thông tin trên bản vẽ để kết luận, ghi kết luận "chưa thể hiện" — KHÔNG tự ý cho là đạt hay không đạt.
- Với mỗi tiêu chí, "ghi_chu" phải trích dẫn/diễn giải ngắn gọn nội dung thực tế nhìn thấy trên bản vẽ (hoặc nêu rõ "chưa thể hiện trên bản vẽ cung cấp").

Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON:
{{
  "loai_he_thong": "thuong" hoặc "dia_chi",
  "ly_do_nhan_dien": "câu ngắn giải thích vì sao xác định loại này",
  "items": [
    {{"muc": "tên mục", "ket_luan": "dat" | "chua_dat" | "chua_the_hien", "ghi_chu": "..."}}
  ],
  "tong_ket": "1-2 câu tổng kết tình trạng chung"
}}"""


class BaoChayReaderError(Exception):
    pass


def read_drawing(file_bytes: bytes, media_type: str, provider) -> dict:
    """Gửi bản vẽ (ảnh hoặc PDF) kèm tiêu chí tới AI provider, trả về dict đã parse JSON."""
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

    try:
        raw = provider.generate_with_document(SYSTEM_PROMPT, content_block)
    except AttributeError:
        raise BaoChayReaderError(
            f"Provider '{getattr(provider, 'name', '?')}' chưa hỗ trợ đọc ảnh/PDF (generate_with_document)."
        )

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BaoChayReaderError(f"AI trả về không đúng định dạng JSON: {exc}. Nội dung nhận được: {raw[:300]}")
