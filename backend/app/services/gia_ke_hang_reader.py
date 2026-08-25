"""AI đọc bản vẽ — hệ thống chữa cháy tự động giá kệ hàng (B15, TCVN 14496:2025).

Áp dụng cho nhà kho có chiều cao xếp hàng hoá trên giá đỡ/kệ hàng TRÊN 5,5m
đến 25m (≤5,5m dùng TCVN 7336 thông thường qua B6, KHÔNG dùng B15).

KHÁC khibotsolkhi_reader.py (B8-B11 — mỗi hệ có 1 template RIÊNG, route tự
chọn ĐÚNG 1 bộ _EXPECTED_IDS theo hệ AI phát hiện): B15 chỉ có 1 template DUY
NHẤT, chứa CẢ 2 nhánh (hệ 1 tầng đầu phun/hệ nhiều tầng đầu phun) trong CÙNG 1
bảng — _EXPECTED_IDS là 1 bộ CỐ ĐỊNH (toàn bộ 74 id của template), AI phải trả
lời ĐỦ mọi id dù chỉ 1 nhánh thật sự áp dụng; id thuộc nhánh KHÔNG chọn nhận
"ket_luan": "khong_ap_dung". Vì vậy dùng khuôn gần botcodinh_reader.py hơn
(1 template, 1 bộ expected_ids cố định), có thêm trường "nhanh" (giống "he_thong"
của khibotsolkhi_reader.py) để frontend hiển thị AI đã chọn nhánh nào.

Nguồn số liệu DUY NHẤT: chua-chay-gia-ke-hang-tcvn14496.md (skill
ra-mau-doi-chieu-pccc). Đã tự kiểm chứng lại toàn bộ 74 id + nội dung quy_dinh
thật của B15_chua_chay_gia_ke_hang.docx (owner đã sửa 2 lỗi trích dẫn trong
file gốc — Phụ lục A thay Phụ lục B cho nhóm nguy cơ phát sinh cháy id=40/56 —
file docx hiện tại ĐÃ đúng, không cần override thêm trong prompt này) trước
khi viết — khớp 100% id/nhánh do owner cung cấp, không có sai lệch.

Các bảng số (Bảng 2, 4, 5, 6, 7) chỉ được NHẮC TÊN trong nội dung quy_dinh của
từng dòng tiêu chí (đọc từ .docx qua mdc_filler), KHÔNG có giá trị số kèm theo
— phải nhúng nguyên các bảng này vào system prompt riêng (không suy đoán lại
số liệu). Bảng 3 (cường độ phun theo áp suất) đã có đủ trong chính quy_dinh
của id=41 (công thức mở rộng icđ khi Kx>1,26 tự chứa 2 giá trị nền 0,27/0,46
tại Kx=1,26) nên không nhúng lặp lại.
"""

from . import mdc_filler, quy_mo_store
from .ai_reader_common import (
    KHONG_UOC_LUONG_KHOANG_CACH,
    NHOM_II_MAU_THUAN_CHECKLIST,
    TOA_DO_TRUC_KHOANG_CACH,
    AIReaderError,
    read_and_validate_drawing_json,
    system_prompt_version,
)
from .ai_schema import GiaKeHangReaderResult, validate_reader_result

_MOT_TANG_IDS = (38, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51)
_NHIEU_TANG_IDS = (
    53, 56, 57, 58, 59, 60, 62, 63, 64, 65, 66, 67, 68, 69, 70,
    73, 74, 75, 76, 77, 78, 79, 80, 82, 83, 84, 85, 86, 88, 89,
)

_BANG_2_PSI = """Bảng 2 – Hệ số thay đổi chiều cao của gian phòng ψ (Điều 5.7, dùng cho công thức lưu lượng đầu phun chủ đạo id=44):
| Chiều cao gian phòng H, m | ψ, m⁻¹ |
|---|---|
| Đến 6,4 | 0 |
| Trên 6,4 đến 14,0 | 0,06 |"""

_BANG_4_DAU_PHUN_GIA_DO = """Bảng 4 – Đặc điểm kỹ thuật đầu phun lắp đặt bên trong giá đỡ (Điều 6.8, dùng cho id=85):
| Thông số | Lỗ phun 12mm | Lỗ phun 15mm |
|---|---|---|
| Dải áp suất làm việc, MPa | 0,1-1,0 | 0,1-1,0 |
| Diện tích bảo vệ dự kiến/đầu phun, m² | 3,0 | 3,0 |
| Cường độ phun tại 0,1MPa, l/(s.m²) | 0,3 | 0,4 |"""

_BANG_5_CHIEU_DAI_A = """Bảng 5 – Chiều dài tính toán A theo loại pallet (Điều 6.11, dùng cho id=74, tham số A trong công thức Qr id=77):
| Loại pallet | A, m |
|---|---|
| Dạng phẳng | 15 |
| Dạng hộp | 12 |
| Dạng hộp bằng kim loại | 8 |"""

_BANG_6_CUONG_DO_PHUN = """Bảng 6 – Cường độ phun yêu cầu trong không gian kệ hàng (Điều 6.12, dùng cho id=73, tham số i trong công thức Qr id=77) — TRA ĐÚNG 2 CHIỀU (loại hàng hoá lưu trữ × độ cao mỗi tầng chắn), đơn vị l/(s.m²):
| Loại hàng hoá lưu trữ | ≤2,0m | Trên 2,0-3,0m | Trên 3,0-4,5m |
|---|---|---|---|
| Vật liệu dễ cháy thể rắn | 0,24 | 0,36 | 0,5 |
| Vật liệu không cháy trong bao bì dễ cháy | 0,20 | 0,30 | 0,4 |
| Sản phẩm cao su | 0,40 | 0,60 | 0,8 |
Xác định ĐÚNG loại hàng hoá thực tế lưu trữ và độ cao thực tế mỗi tầng chắn (khoảng cách giữa 2 tấm chắn liên tiếp, xem id=76) trên bản vẽ/thuyết minh rồi TRA ĐÚNG Ô giao giữa hàng và cột tương ứng — KHÔNG được chọn nhầm hàng/cột. Nếu bản vẽ không nêu rõ loại hàng hoá hoặc độ cao tầng chắn: "chua_the_hien", không tự suy đoán."""

_BANG_7_VAT_LIEU_TAM_CHAN = """Bảng 7 – Vật liệu tấm chắn (Điều 6.16-6.17, dùng cho id=89):
| Loại vật liệu | Độ dày tối thiểu, mm |
|---|---|
| Tấm thép | 0,6 |
| Tấm vật liệu từ xi măng | 10 |"""

_COT_AP_GHI_CHU = """YÊU CẦU RIÊNG CHO id=45, id=60, id=78, id=80 (cột áp): đây là kết quả tính toán thuỷ lực nhiều bước theo Phụ lục B TCVN 7336:2021 (lưu lượng từng đầu phun → đường kính ống từng đoạn → tổn thất áp lực → áp suất tại mỗi điểm, lặp lại theo mạng đường ống thật) — KHÔNG có công thức rút gọn nào trong TCVN 14496. TUYỆT ĐỐI KHÔNG tự thực hiện chuỗi tính toán này. Nếu bản vẽ/bảng tính có ghi sẵn giá trị cột áp yêu cầu/thiết kế: trích nguyên giá trị đó vào "noi_dung_thiet_ke". Nếu không có: ghi "noi_dung_thiet_ke": "Tính toán theo Phụ lục B TCVN 7336:2021 (cần tính toán thuỷ lực nhiều bước theo sơ đồ mạng đường ống thật)", "ket_luan": "chua_the_hien"."""

_NHANH_BLOCK = f"""YÊU CẦU RIÊNG CHO 2 NHÁNH (loại trừ lẫn nhau — bản vẽ chỉ dùng ĐÚNG 1 nhánh thật, không phải "tuỳ chọn có thể bỏ trống"):
- id={", ".join(str(i) for i in _MOT_TANG_IDS)} (nhánh "Hệ 1 tầng đầu phun" — Điều 5.1): nếu bản vẽ dùng đúng nhánh này, đối chiếu BÌNH THƯỜNG theo hướng dẫn chung. Nếu bản vẽ dùng nhánh KHÁC: TẤT CẢ id trong nhóm này "ket_luan": "khong_ap_dung", "noi_dung_thiet_ke": "x - Không áp dụng".
- id={", ".join(str(i) for i in _NHIEU_TANG_IDS)} (nhánh "Hệ nhiều tầng đầu phun" — Điều 6.1): nếu bản vẽ dùng đúng nhánh này, đối chiếu BÌNH THƯỜNG theo hướng dẫn chung. Nếu bản vẽ dùng nhánh KHÁC: TẤT CẢ id trong nhóm này "ket_luan": "khong_ap_dung", "noi_dung_thiet_ke": "x - Không áp dụng".
{_BANG_2_PSI}
{_BANG_4_DAU_PHUN_GIA_DO}
{_BANG_5_CHIEU_DAI_A}
{_BANG_6_CUONG_DO_PHUN}
{_BANG_7_VAT_LIEU_TAM_CHAN}
{_COT_AP_GHI_CHU}
"""

_BUOC1_XAC_DINH_NHANH = """BƯỚC 1 — Xác định nhánh: đọc CHIỀU CAO XẾP HÀNG HOÁ THỰC TẾ TRÊN GIÁ ĐỠ (h) và CHIỀU CAO GIAN PHÒNG (H) ghi trên bản vẽ/thuyết minh, rồi chọn nhánh theo bảng sau:
| Điều kiện | Nhánh |
|---|---|
| h = 5,5-12,5m VÀ H ≤14m, nhóm nguy cơ phát sinh cháy 5 hoặc 6 (Phụ lục A TCVN 7336:2021) | "mot_tang" (Hệ 1 tầng đầu phun, Điều 5.1 — đầu phun chỉ bố trí dưới mái) |
| h đến 25m, giá đỡ cố định | "nhieu_tang" (Hệ nhiều tầng đầu phun, Điều 6.1 — gồm mạng dưới mái + các tầng đầu phun theo chiều cao giá đỡ) |
Nếu bản vẽ/thuyết minh KHÔNG ghi rõ h/H: có thể dùng "Chiều cao sắp xếp hàng hoá trên giá đỡ/kệ hàng" trong phần "Thông tin quy mô công trình đã ghi nhận" bên dưới (nếu có) làm GỢI Ý THAM KHẢO — nhưng vẫn PHẢI ưu tiên số đo thật trên bản vẽ nếu bản vẽ có ghi, không dùng dữ liệu quy mô để thay thế việc đọc bản vẽ. Nếu không có cả 2 nguồn: chọn nhánh có nhiều dấu hiệu phù hợp hơn trên bản vẽ (ví dụ có/không có tầng đầu phun trong không gian giá đỡ với tấm chắn — chỉ có ở nhánh nhiều tầng) và nêu rõ căn cứ đã dùng trong "ly_do_nhan_dien"; nếu hoàn toàn không đủ căn cứ chọn nhánh, ghi rõ trong "ly_do_nhan_dien" và vẫn phải chọn 1 nhánh hợp lý nhất để tiếp tục đối chiếu (không được bỏ trống "nhanh")."""


def _fmt_rows(rows):
    return "\n".join(
        f"id={r['id']} | [{r['doi_chieu']}] {r['quy_dinh']} (Căn cứ: {r['khoan_dieu']})"
        for r in rows
    )


def _build_system_prompt():
    rows = mdc_filler.load_criteria_rows("chua_chay_gia_ke_hang")
    return f"""Bạn là kỹ sư PCCC rà soát bản vẽ hệ thống chữa cháy tự động bằng nước cho nhà kho có giá kệ hàng cao tầng (chiều cao xếp hàng hoá trên giá đỡ TRÊN 5,5m đến 25m), đối chiếu với mẫu đối chiếu MĐC B15 (TCVN 14496:2025, dẫn kèm TCVN 7336:2021 cho trạm bơm/đường ống/tính toán thuỷ lực).

YÊU CẦU THÊM: Đọc SỐ HIỆU BẢN VẼ ghi trong khung tên (title block) của chính bản vẽ này (thường ở góc dưới bên phải, ô ghi "Số bản vẽ" / "Ký hiệu bản vẽ" / "Drawing No."). Nếu khung tên không có, không rõ, hoặc bản vẽ không thể hiện số hiệu: ghi ĐÚNG NGUYÊN VĂN "Không xác định được số hiệu bản vẽ" ở trường "so_hieu_ban_ve" — TUYỆT ĐỐI không suy đoán, không tự đặt số hiệu.

{_BUOC1_XAC_DINH_NHANH}
Nêu rõ căn cứ đã dùng trong "ly_do_nhan_dien".

BƯỚC 2 — Với MỖI dòng tiêu chí dưới đây (mỗi dòng có sẵn "id" — khi trả lời PHẢI giữ nguyên đúng id đó, và phải trả lời ĐỦ cho TẤT CẢ id, KỂ CẢ id thuộc nhánh KHÔNG được chọn ở Bước 1 — không bỏ sót bất kỳ id nào), đối chiếu với bản vẽ và trả về:
- "noi_dung_thiet_ke": nội dung điền vào cột "Nội dung thiết kế" của mẫu MĐC gốc — ngắn gọn, đúng mạch đối chiếu (dùng gạch đầu dòng "-" nếu nhiều ý), nêu số liệu cụ thể NHÌN THẤY trên bản vẽ. Nếu bản vẽ không thể hiện đủ thông tin để kết luận: ghi đúng "Chưa thể hiện trên bản vẽ cung cấp".
{TOA_DO_TRUC_KHOANG_CACH}
- "ket_luan": "dat" nếu nội dung trên bản vẽ đáp ứng đúng quy định; "chua_dat" nếu đã thể hiện nhưng vi phạm giá trị/quy định; "chua_the_hien" nếu bản vẽ không đủ thông tin để kết luận; "khong_ap_dung" CHỈ dùng cho id thuộc nhánh KHÔNG được chọn (xem hướng dẫn nhánh bên dưới) — KHÔNG tự ý dùng cho id khác.

{_NHANH_BLOCK}
--- DANH SÁCH TIÊU CHÍ (MĐC B15 — chữa cháy tự động giá kệ hàng) ---
{_fmt_rows(rows)}

BƯỚC 3: Với MỖI id có "ket_luan" là "chua_dat" hoặc "chua_the_hien" ở Bước 2, soạn thêm một câu kiến nghị theo đúng văn phong công văn PC07:
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
Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON:
{{
  "nhanh": "mot_tang" | "nhieu_tang",
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

GiaKeHangReaderError = AIReaderError

_EXPECTED_IDS = {r["id"] for r in mdc_filler.load_criteria_rows("chua_chay_gia_ke_hang")}


def _validate(data: dict):
    return validate_reader_result(data, _EXPECTED_IDS, GiaKeHangReaderResult)


def read_drawing(file_bytes: bytes, media_type: str, provider, quy_mo: dict = None) -> dict:
    """Gửi bản vẽ (ảnh hoặc PDF) kèm tiêu chí tới AI provider, validate qua Pydantic
    (kèm retry-repair 1 lần nếu sai), trả về dict.

    quy_mo: dữ liệu quy mô công trình (hạng mục "Quy mô") của CÙNG phiên Bộ hồ
    sơ, nếu người dùng CÓ đính kèm — HOÀN TOÀN TUỲ CHỌN (None nếu không đính).
    Dùng làm GỢI Ý THAM KHẢO cho Bước 1 (xác định nhánh qua chieuCaoKeHang) khi
    bản vẽ không ghi rõ h/H — không thay thế việc đọc bản vẽ thật.
    """
    system_prompt = SYSTEM_PROMPT + quy_mo_store.format_quy_mo_context(quy_mo) if quy_mo else SYSTEM_PROMPT
    model = read_and_validate_drawing_json(
        file_bytes, media_type, provider, system_prompt, _validate, prompt_version=SYSTEM_PROMPT_VERSION
    )
    return model.model_dump()
