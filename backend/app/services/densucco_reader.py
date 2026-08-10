"""AI đọc bản vẽ — đèn sự cố/chỉ dẫn thoát nạn và bình chữa cháy.

Giống "Chữa cháy bằng nước" (ccnuoc_reader.py): gộp 2 mẫu đối chiếu riêng biệt
CÙNG áp dụng cho 1 bộ bản vẽ (thường thiết kế chung 1 bản vẽ):
- MĐC B12 — bình chữa cháy xách tay/xe đẩy, bình bột tự động treo, mặt nạ lọc độc
- MĐC B13 — đèn chiếu sáng sự cố, chỉ dẫn thoát nạn, loa thông báo/hướng dẫn thoát nạn

Gọi AI 2 lần (mỗi lần 1 mẫu, cùng 1 file bản vẽ) chạy song song bằng
ThreadPoolExecutor để tổng thời gian chờ ≈ mẫu chậm nhất thay vì cộng dồn cả
2, rồi gộp kết quả lại. Nếu 1 mẫu lỗi vẫn trả về mẫu còn thành công.

Chỉ đạo nghiệp vụ của owner cho 6 nhóm tiêu chí đặc biệt trong 2 mẫu này
(không phải suy đoán — xem _SPECIAL_ID_BLOCKS bên dưới):
1. B12 id 4,7,8,9,10,11 (phân loại mức nguy hiểm + tính số bình): giữ nguyên
   logic đối chiếu, chỉ yêu cầu AI nêu rõ NGUỒN xác định công năng (ghi chú/
   thuyết minh nào trên bản vẽ) trong noi_dung_thiet_ke.
2. B12 id 14,15 (bình bột chữa cháy tự động kích hoạt loại treo — TUỲ CHỌN)
   và id 17-22 (bình khí/sol-khí chữa cháy tự động kích hoạt — cũng TUỲ
   CHỌN): nếu bản vẽ không thể hiện, kết luận "khong_ap_dung" (KHÔNG phải
   "dat" hay "chua_the_hien") — không thiết kế có thể là lựa chọn hợp lệ, cột
   "Kết luận" trong MĐC để TRỐNG cho giá trị này (xem routes/aiho.py
   _answers_from_items(), khác "Đạt"/"KN").
3. B12 id 28,29 (mặt nạ lọc độc/mặt nạ phòng độc cách ly): thuộc diện theo
   ĐÚNG điều kiện đã code trong evaluate_mat_na() (backend/app/services/
   phuong_tien.py, Phụ lục F QCVN 10:2025/BCA) — khách sạn ≥3 tầng hoặc
   karaoke/vũ trường (không phụ thuộc quy mô).
4. B13 id 15,19 (biển báo an toàn tầm thấp): thuộc diện theo ĐÚNG điều kiện
   trong evaluate_den() (phuong_tien.py, TCVN 13456:2022 mục 5.2.3) — khách
   sạn ≥7 tầng, hoặc khối tích ≥5.000 m³ có hành lang thoát nạn >10 m.
5. B13 id 24,25,26 (hệ thống loa thông báo và hướng dẫn thoát nạn): thuộc
   diện theo ĐÚNG điều kiện trong evaluate_loa() (phuong_tien.py, Phụ lục G
   Bảng G.1, TT1/TT2/TT3/TT4/TT6).

Với nhóm 3-5 (phụ thuộc quy mô công trình mà 1 bản vẽ đèn/bình đơn lẻ thường
KHÔNG thể hiện đủ — số tầng/khối tích/công năng/số người...): nếu bản vẽ tự
thể hiện đủ thông tin quy mô thì áp đúng ngưỡng; nếu không đủ, ghi rõ "Chưa
đủ thông tin quy mô công trình..." (KHÔNG mặc định "Bổ sung") và xếp kiến
nghị vào nhóm IV (đề xuất bổ sung hồ sơ) thay vì nhóm I.
"""

from concurrent.futures import ThreadPoolExecutor

from . import mdc_filler, quy_mo_store
from .ai_reader_common import NHOM_II_MAU_THUAN_CHECKLIST, AIReaderError, read_and_validate_drawing_json, system_prompt_version
from .ai_schema import KHONG_XAC_DINH_SO_HIEU, ReaderResult, validate_reader_result
from .phuong_tien import PhuongTienInputError, evaluate_bien_tam_thap, evaluate_loa, evaluate_mat_na

FORMS = [
    {"loai": "binh_chua_chay", "mdc_label": "MĐC B12", "ten_he_thong": "bình chữa cháy xách tay/xe đẩy"},
    {"loai": "den_su_co", "mdc_label": "MĐC B13", "ten_he_thong": "đèn chiếu sáng sự cố, đèn chỉ dẫn thoát nạn"},
]

# Câu chữ cố định (owner duyệt) dùng khi bản vẽ đơn lẻ không đủ thông tin quy
# mô công trình để áp điều kiện "thuộc diện hay không" — dùng nguyên văn cho
# noi_dung_thiet_ke, KHÔNG diễn giải lại.
CHUA_DU_QUY_MO_TEXT = (
    "Chưa đủ thông tin quy mô công trình (số tầng/khối tích/công năng) trên bản vẽ "
    "để xác định có thuộc diện trang bị hay không — cần đối chiếu thêm với hồ sơ quy mô công trình"
)


def _scope_dependent_block(ids, ten_tieu_chi, dieu_kien_thuoc_dien, nguon_dieu_kien, can_cu_nhom4):
    ids_str = ", ".join(str(i) for i in ids)
    return f"""
YÊU CẦU RIÊNG CHO id={ids_str} ({ten_tieu_chi}): đây là tiêu chí CHỈ áp dụng khi công trình thuộc diện theo quy mô — {dieu_kien_thuoc_dien} (nguồn: {nguon_dieu_kien}, LẤY ĐÚNG NGƯỠNG SỐ này, không tự đặt ngưỡng khác). Một bản vẽ đèn/bình đơn lẻ thường KHÔNG có đủ thông tin quy mô công trình (số tầng, khối tích, công năng, số người...) để tự áp điều kiện này — đây là giới hạn thật của loại bản vẽ này, không phải lỗi.
- Nếu bản vẽ TỰ THỂ HIỆN đủ thông tin quy mô cần thiết (qua ghi chú, thuyết minh, tên dự án ngay trên chính bản vẽ này): áp đúng điều kiện trên. Nếu xác định KHÔNG thuộc diện: "ket_luan": "dat", nêu rõ lý do không thuộc diện trong "noi_dung_thiet_ke" (ví dụ nêu công năng/số tầng đã đọc được và so với ngưỡng). Nếu xác định CÓ thuộc diện: đối chiếu bình thường theo Bước 1/Bước 2 bên dưới.
- Nếu bản vẽ KHÔNG thể hiện đủ thông tin quy mô để xác định thuộc diện hay không: "ket_luan": "chua_the_hien", "noi_dung_thiet_ke": "{CHUA_DU_QUY_MO_TEXT}". Với (các) id này, câu kiến nghị tương ứng PHẢI xếp vào NHÓM IV (đề xuất bổ sung hồ sơ) — KHÔNG xếp vào nhóm I — với văn phong: "Đối chiếu bổ sung hồ sơ quy mô công trình để xác định {ten_tieu_chi.lower()} có thuộc diện bắt buộc trang bị hay không (Căn cứ {can_cu_nhom4})."
"""


_MUC_NGUY_HIEM_BLOCK = """
YÊU CẦU RIÊNG CHO id=4, 7, 8, 9, 10, 11 (phân loại mức nguy hiểm và tính số bình chữa cháy): xác định mức nguy hiểm (Thấp/Trung bình/Cao theo Bảng 1 TCVN 7435-1:2004 / Bảng D.1 TCVN 7435-2) CĂN CỨ công năng công trình thể hiện trên chính bản vẽ (ghi chú, thuyết minh, tên dự án trong khung tên) — giữ nguyên cách đối chiếu bình thường (Bước 1/Bước 2), CHỈ THÊM yêu cầu: trong "noi_dung_thiet_ke" của các id này, PHẢI nêu rõ đã căn cứ ghi chú/thuyết minh/tên dự án nào trên bản vẽ để xác định công năng và mức nguy hiểm tương ứng (ví dụ: "Theo tên dự án/thuyết minh trên bản vẽ: [công năng] → mức nguy hiểm [Thấp/Trung bình/Cao] theo Bảng 1 TCVN 7435-1:2004..."). Nếu bản vẽ không ghi rõ công năng để căn cứ: ghi "Chưa thể hiện trên bản vẽ cung cấp" như bình thường (không phải trường hợp đặc biệt).
"""

def _optional_item_block(ids, ten_tieu_chi, can_cu):
    ids_str = ", ".join(str(i) for i in ids)
    ten_thuong = ten_tieu_chi[0].lower() + ten_tieu_chi[1:]
    return f"""
YÊU CẦU RIÊNG CHO id={ids_str} ({ten_tieu_chi}, {can_cu}): đây là hạng mục TUỲ CHỌN, không bắt buộc với mọi công trình.
- Nếu bản vẽ KHÔNG thể hiện gì về {ten_thuong}: "ket_luan": "khong_ap_dung" (KHÔNG phải "chua_the_hien" hay "dat"), "noi_dung_thiet_ke": "Không có thiết kế {ten_thuong}" — KHÔNG tạo kiến nghị nào cho (các) id này, vì không thiết kế có thể là lựa chọn thiết kế hợp lệ, không phải thiếu sót.
- Nếu bản vẽ CÓ thể hiện {ten_thuong}: đối chiếu bình thường theo Bước 1/Bước 2 (nêu rõ nội dung, vị trí, và số hiệu bản vẽ nơi thể hiện trong "noi_dung_thiet_ke").
"""


_BINH_BOT_TREO_BLOCK = _optional_item_block(
    ids=[14, 15],
    ten_tieu_chi="Bình bột chữa cháy tự động kích hoạt loại treo",
    can_cu="TCVN 12314-1:2018",
)

_BINH_KHI_TU_DONG_BLOCK = _optional_item_block(
    ids=[17, 18, 19, 20, 21, 22],
    ten_tieu_chi="Bình khí, bình sol-khí chữa cháy tự động kích hoạt",
    can_cu="QCVN 10:2025/BCA, TCVN 12314-2:2022",
)

_MAT_NA_BLOCK = _scope_dependent_block(
    ids=[28, 29],
    ten_tieu_chi="mặt nạ lọc độc và mặt nạ phòng độc cách ly",
    dieu_kien_thuoc_dien=(
        "CHỈ bắt buộc khi công năng là khách sạn/cơ sở lưu trú có số tầng ≥ 3, "
        "HOẶC công năng là karaoke/vũ trường (không phụ thuộc quy mô)"
    ),
    nguon_dieu_kien="evaluate_mat_na(), backend/app/services/phuong_tien.py — Phụ lục F QCVN 10:2025/BCA",
    can_cu_nhom4="Phụ lục F QCVN 10:2025/BCA",
)

_BIEN_TAM_THAP_BLOCK = _scope_dependent_block(
    ids=[15, 19],
    ten_tieu_chi="biển báo an toàn tầm thấp",
    dieu_kien_thuoc_dien=(
        "CHỈ bắt buộc khi công năng khách sạn có số tầng ≥ 7, "
        "HOẶC khối tích công trình ≥ 5.000 m³ VÀ có hành lang thoát nạn dài hơn 10 m"
    ),
    nguon_dieu_kien="evaluate_den(), backend/app/services/phuong_tien.py — TCVN 13456:2022 mục 5.2.3",
    can_cu_nhom4="Điều 5.2.3 TCVN 13456:2022",
)

_LOA_THONG_BAO_BLOCK = _scope_dependent_block(
    ids=[24, 25, 26],
    ten_tieu_chi="hệ thống loa thông báo và hướng dẫn thoát nạn",
    dieu_kien_thuoc_dien=(
        "CHỈ bắt buộc khi thuộc 1 trong các trường hợp: TT1 (công trình công cộng/hỗn hợp cao trên 10 tầng "
        "hoặc có từ 2 tầng hầm trở lên), TT2 (karaoke/vũ trường/nhà hát/bệnh viện có ≥50 người/tầng), "
        "TT3 (nhà để xe dạng kín có tổng diện tích sàn ΣF ≥18.000 m²), TT4 (nhà sản xuất có ΣF≥18.000 m² "
        "và ≥300 người/tầng đồng thời), TT6 (nhà ga hành khách — luôn thuộc diện)"
    ),
    nguon_dieu_kien="evaluate_loa(), backend/app/services/phuong_tien.py — Phụ lục G Bảng G.1 QCVN 10:2025/BCA",
    can_cu_nhom4="Phụ lục G QCVN 10:2025/BCA",
)

_SPECIAL_ID_BLOCKS = {
    "binh_chua_chay": _MUC_NGUY_HIEM_BLOCK + _BINH_BOT_TREO_BLOCK + _BINH_KHI_TU_DONG_BLOCK + _MAT_NA_BLOCK,
    "den_su_co": _BIEN_TAM_THAP_BLOCK + _LOA_THONG_BAO_BLOCK,
}


def _fmt_rows(rows):
    return "\n".join(
        f"id={r['id']} | [{r['doi_chieu']}] {r['quy_dinh']} (Căn cứ: {r['khoan_dieu']})"
        for r in rows
    )


def _build_system_prompt(loai, mdc_label, ten_he_thong):
    rows = mdc_filler.load_criteria_rows(loai)
    special_block = _SPECIAL_ID_BLOCKS.get(loai, "")
    return f"""Bạn là kỹ sư PCCC rà soát bản vẽ hệ thống {ten_he_thong}, đối chiếu với mẫu đối chiếu {mdc_label}.

YÊU CẦU THÊM: Đọc SỐ HIỆU BẢN VẼ ghi trong khung tên (title block) của chính bản vẽ này (thường ở góc dưới bên phải, ô ghi "Số bản vẽ" / "Ký hiệu bản vẽ" / "Drawing No."). Nếu khung tên không có, không rõ, hoặc bản vẽ không thể hiện số hiệu: ghi ĐÚNG NGUYÊN VĂN "Không xác định được số hiệu bản vẽ" ở trường "so_hieu_ban_ve" — TUYỆT ĐỐI không suy đoán, không tự đặt số hiệu.

BƯỚC 1: Với MỖI dòng tiêu chí dưới đây (mỗi dòng có sẵn "id" — khi trả lời PHẢI giữ nguyên đúng id đó, và phải trả lời ĐỦ cho TẤT CẢ id, không bỏ sót), đối chiếu với bản vẽ và trả về:
- "noi_dung_thiet_ke": nội dung điền vào cột "Nội dung thiết kế" của mẫu MĐC gốc — ngắn gọn, đúng mạch đối chiếu (dùng gạch đầu dòng "-" nếu nhiều ý), nêu số liệu cụ thể NHÌN THẤY trên bản vẽ. Nếu bản vẽ không thể hiện đủ thông tin để kết luận: ghi đúng "Chưa thể hiện trên bản vẽ cung cấp".
- "ket_luan": "dat" nếu nội dung trên bản vẽ đáp ứng đúng quy định; "chua_dat" nếu đã thể hiện nhưng vi phạm giá trị/quy định; "chua_the_hien" nếu bản vẽ không đủ thông tin để kết luận; "khong_ap_dung" CHỈ dùng cho đúng các id có hướng dẫn riêng bên dưới chỉ định rõ (hạng mục tuỳ chọn không thiết kế) — KHÔNG tự ý dùng cho id khác.
{special_block}
--- DANH SÁCH TIÊU CHÍ ({mdc_label} — {ten_he_thong}) ---
{_fmt_rows(rows)}

BƯỚC 2: Với MỖI id có "ket_luan" là "chua_dat" hoặc "chua_the_hien" ở bước 1, soạn thêm một câu kiến nghị theo đúng văn phong công văn PC07:
- Mở đầu bằng động từ mệnh lệnh phù hợp: "Thể hiện rõ ..." (nếu là "chua_the_hien" — thông tin đáng lẽ có trên bản vẽ nhưng chưa vẽ/ghi), "Bổ sung ..." (nếu cần thêm chi tiết/thiết bị/bản vẽ), hoặc "Thuyết minh rõ ..." (nếu cần giải trình bằng lời).
- Một câu mạch lạc, nêu rõ đối tượng cụ thể trên bản vẽ + số liệu định lượng của tiêu chuẩn (lấy từ đúng nội dung quy định của id tương ứng).
- Kết câu bằng phần căn cứ, in trong ngoặc đơn, lấy ĐÚNG "Khoản, Điều" đã ghi ở id đó — không tự bịa số Điều khác.
- Xếp mỗi kiến nghị vào đúng 1 trong 4 nhóm sau:
  - "chua_the_hien": nhóm I (nội dung chưa thể hiện trên bản vẽ) — TRỪ các id đã có hướng dẫn riêng ở trên chỉ định rõ xếp vào nhóm IV.
  - "chua_dat": nhóm III (nội dung đã thể hiện nhưng vi phạm giá trị/quy định của tiêu chuẩn).
  - Nhóm II (chưa thống nhất giữa nhiều nguồn số liệu) CHỈ dùng khi có căn cứ rõ ràng từ chính bản vẽ này; nếu không có căn cứ, để mảng rỗng.
  - Nhóm IV (đề xuất bổ sung hồ sơ/bản vẽ mới): dùng cho các id đã có hướng dẫn riêng ở trên chỉ định rõ, hoặc khi có căn cứ rõ ràng khác từ chính bản vẽ này — KHÔNG cố tạo kiến nghị cho đủ 4 nhóm.
{NHOM_II_MAU_THUAN_CHECKLIST}
- Nếu mọi id đều "dat", để cả 4 mảng đều rỗng.

NGUYÊN TẮC BẮT BUỘC:
- Chỉ đánh giá dựa trên nội dung THỰC SỰ thể hiện trên bản vẽ được cung cấp. Không suy đoán, không dùng kiến thức chung ngoài bản vẽ.
- Bản vẽ có thể không thể hiện hệ thống {ten_he_thong} (ví dụ công trình không có hạng mục này) — khi đó ghi "chưa thể hiện trên bản vẽ cung cấp" cho toàn bộ, không suy đoán là "không áp dụng".
- Không được bỏ sót bất kỳ id nào.

Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON:
{{
  "so_hieu_ban_ve": "số hiệu bản vẽ đọc từ khung tên, hoặc \\"Không xác định được số hiệu bản vẽ\\"",
  "items": [
    {{"id": 2, "noi_dung_thiet_ke": "...", "ket_luan": "dat" | "chua_dat" | "chua_the_hien" | "khong_ap_dung"}}
  ],
  "tong_ket": "1-2 câu tổng kết tình trạng chung của riêng hệ thống {ten_he_thong}",
  "kien_nghi": {{
    "I_chua_the_hien": ["câu kiến nghị theo khuôn PC07, kết bằng (Căn cứ Điều ..., Mục ... TCVN/QCVN ....)"],
    "II_chua_thong_nhat": [],
    "III_chua_phu_hop": ["câu kiến nghị tương tự cho các id chua_dat"],
    "IV_de_xuat_bo_sung": []
  }}
}}"""


SYSTEM_PROMPTS = {f["loai"]: _build_system_prompt(f["loai"], f["mdc_label"], f["ten_he_thong"]) for f in FORMS}
SYSTEM_PROMPT_VERSIONS = {loai: system_prompt_version(prompt) for loai, prompt in SYSTEM_PROMPTS.items()}

DenSuCoReaderError = AIReaderError

_EXPECTED_IDS = {f["loai"]: {r["id"] for r in mdc_filler.load_criteria_rows(f["loai"])} for f in FORMS}


def _validate_for(loai):
    def _validate(data: dict):
        return validate_reader_result(data, _EXPECTED_IDS[loai], ReaderResult)
    return _validate


# ---------------------------------------------------------------------------
# Muc 2 (rieng densucco): neu quy_mo co du du lieu de goi thang evaluate_mat_na()/
# evaluate_bien_tam_thap()/evaluate_loa() (phuong_tien.py) ra ket qua CHAC CHAN
# (khong phai warn/chua_du_du_lieu), noi them 1 doan "da xac dinh bang code" de
# GHI DE fallback "chua du thong tin quy mo" GOC cua 3 nhom _scope_dependent_block
# (id 28,29 / 15,19 / 24,25,26) — CHI khi thuc su xac dinh duoc, khong bao gio
# BAT BUOC quy_mo phai co (quy_mo=None -> khong override gi ca, giu nguyen
# fallback goc y het truoc day).
# ---------------------------------------------------------------------------
def _override_block(ids, ten_tieu_chi, r):
    ids_str = ", ".join(str(i) for i in ids)
    thuoc_dien = "CÓ" if r["result"] == "yes" else "KHÔNG"
    return f"""
GHI CHÚ QUY MÔ ĐÃ XÁC ĐỊNH CHO id={ids_str} ({ten_tieu_chi}): dựa trên dữ liệu quy mô công trình đã xác nhận (xem mục "QUY MÔ CÔNG TRÌNH ĐÃ XÁC NHẬN" bên dưới), công trình {thuoc_dien} thuộc diện bắt buộc trang bị {ten_tieu_chi} — căn cứ: {r['detail']} ({r['can_cu']}). KHÔNG dùng câu "{CHUA_DU_QUY_MO_TEXT}" cho (các) id này nữa, TRỪ KHI bản vẽ chứa thông tin MÂU THUẪN rõ ràng với kết luận này (khi đó ưu tiên thông tin THỰC TẾ trên bản vẽ).
- Nếu KHÔNG thuộc diện: "ket_luan": "dat", "noi_dung_thiet_ke" nêu rõ lý do không thuộc diện (dựa trên căn cứ trên).
- Nếu CÓ thuộc diện: vẫn phải tự đọc bản vẽ để đối chiếu chi tiết kỹ thuật NHƯ BÌNH THƯỜNG (Bước 1/Bước 2 ở trên) — dữ liệu quy mô chỉ xác nhận CÓ thuộc diện, không thay thế việc đọc bản vẽ.
"""


def _mat_na_ready(quy_mo):
    # evaluate_mat_na() chi phu thuoc "floors" khi occ=="khachsan" (con lai la
    # nhanh khong phu thuoc so lieu: karaoke luon "yes", con lai luon "na") -
    # chi can "floors" that su co khi occ=khachsan de tranh _num() mac dinh 0
    # tao ra ket luan "no" GIA (thieu du lieu, khong phai that su < 3 tang).
    if quy_mo.get("occ") == "khachsan":
        return quy_mo.get("floors") is not None
    return True


def _bien_tam_thap_ready(quy_mo):
    # evaluate_bien_tam_thap() co 2 nhanh doc lap (floors cho khach san, volume
    # cho khoi tich) - yeu cau CA HAI cung co mat de tranh _num() mac dinh 0 o
    # nhanh con lai lam sai lech ket luan "no" o 2 nhanh fallback cuoi ham.
    return quy_mo.get("floors") is not None and quy_mo.get("volume") is not None


def _loa_ready(_quy_mo):
    # evaluate_loa() tu bao hieu thieu du lieu qua "notes" (xem _mucdo2_overrides:
    # chi tin "no" khi khong co note nao) - khong can guard rieng o day.
    return True


_MUCDO2_TARGETS = (
    (evaluate_mat_na, _mat_na_ready, "binh_chua_chay", (28, 29), "mặt nạ lọc độc và mặt nạ phòng độc cách ly"),
    (evaluate_bien_tam_thap, _bien_tam_thap_ready, "den_su_co", (15, 19), "biển báo an toàn tầm thấp"),
    (evaluate_loa, _loa_ready, "den_su_co", (24, 25, 26), "hệ thống loa thông báo và hướng dẫn thoát nạn"),
)


def _mucdo2_overrides(quy_mo):
    blocks = {"binh_chua_chay": "", "den_su_co": ""}
    if not quy_mo:
        return blocks

    for fn, ready, loai, ids, ten_tieu_chi in _MUCDO2_TARGETS:
        if not ready(quy_mo):
            continue
        try:
            r = fn(quy_mo)
        except PhuongTienInputError:
            continue
        # "no" cua evaluate_loa() co the la san pham cua thieu du lieu (P/pplFloor
        # None) o cac nhanh TT2/TT4 - ham tu ghi chu vao "notes" khi do, nen chi
        # tin "no" khi KHONG co note nao (xem _loa_ready()).
        if r["result"] == "no" and r.get("notes"):
            continue
        if r["result"] in ("yes", "no", "na"):
            blocks[loai] += _override_block(ids, ten_tieu_chi, r)
    return blocks


def read_drawing(file_bytes: bytes, media_type: str, provider, quy_mo: dict = None) -> dict:
    """Gọi AI 2 lần (B12/B13) song song cho cùng 1 bản vẽ, mỗi lần validate qua
    Pydantic (kèm retry-repair riêng từng lần nếu sai), rồi gộp kết quả lại.

    quy_mo: dữ liệu quy mô công trình (hạng mục "Quy mô") của CÙNG phiên Bộ hồ
    sơ, nếu người dùng CÓ đính kèm — HOÀN TOÀN TUỲ CHỌN (None nếu không đính,
    hành vi giữ nguyên 100% như trước, kể cả 3 fallback "chưa đủ thông tin quy
    mô" gốc của _scope_dependent_block()).
    """
    context = quy_mo_store.format_quy_mo_context(quy_mo) if quy_mo else ""
    overrides = _mucdo2_overrides(quy_mo)

    def _call(form):
        prompt = SYSTEM_PROMPTS[form["loai"]] + overrides.get(form["loai"], "") + context
        return read_and_validate_drawing_json(
            file_bytes, media_type, provider, prompt, _validate_for(form["loai"]),
            prompt_version=SYSTEM_PROMPT_VERSIONS[form["loai"]],
        )

    results = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=len(FORMS)) as executor:
        future_to_form = {executor.submit(_call, f): f for f in FORMS}
        for future, form in future_to_form.items():
            try:
                results[form["loai"]] = future.result()
            except Exception as exc:
                errors[form["loai"]] = str(exc)

    if not results:
        raise AIReaderError("; ".join(errors.values()) or "Không rõ nguyên nhân.")

    combined_kien_nghi = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}
    tong_ket_parts = []
    forms_out = {}
    so_hieu_ban_ve = None
    for form in FORMS:
        loai = form["loai"]
        if loai in results:
            data = results[loai].model_dump()
            forms_out[loai] = {
                "label": form["ten_he_thong"],
                "mdc_label": form["mdc_label"],
                "items": data.get("items", []),
            }
            kn = data.get("kien_nghi") or {}
            for key in combined_kien_nghi:
                combined_kien_nghi[key].extend(kn.get(key) or [])
            if data.get("tong_ket"):
                tong_ket_parts.append(form["ten_he_thong"].capitalize() + ": " + data["tong_ket"])
            # Lấy so_hieu_ban_ve từ lần đọc ĐẦU TIÊN (theo thứ tự FORMS) có giá trị
            # thật (khác placeholder "không xác định") — 2 lần gọi đều đọc cùng 1
            # file nên số hiệu phải giống nhau, chỉ cần 1 nguồn đáng tin.
            if so_hieu_ban_ve is None and data.get("so_hieu_ban_ve") and data["so_hieu_ban_ve"] != KHONG_XAC_DINH_SO_HIEU:
                so_hieu_ban_ve = data["so_hieu_ban_ve"]
        else:
            forms_out[loai] = {
                "label": form["ten_he_thong"],
                "mdc_label": form["mdc_label"],
                "error": errors.get(loai),
            }
            tong_ket_parts.append(form["ten_he_thong"].capitalize() + ": lỗi khi phân tích — " + str(errors.get(loai)))

    return {
        "forms": forms_out,
        "tong_ket": " ".join(tong_ket_parts),
        "kien_nghi": combined_kien_nghi,
        "so_hieu_ban_ve": so_hieu_ban_ve or KHONG_XAC_DINH_SO_HIEU,
    }
