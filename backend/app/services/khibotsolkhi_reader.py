"""AI đọc bản vẽ — hệ thống chữa cháy bằng khí/sol-khí (B8-B11).

Khác B12+B13 (densucco_reader.py, LUÔN cùng xuất hiện) hay B3+B5+B6
(ccnuoc_reader.py, cùng 1 hệ nước), B8-B11 là 4 LỰA CHỌN THAY THẾ NHAU cho
CÙNG 1 nhu cầu (1 khu vực bảo vệ chỉ dùng ĐÚNG 1 chất chữa cháy — không bao
giờ dùng cả CO2 lẫn Sol-khí lẫn khí hóa lỏng cho cùng 1 phòng). Theo đúng
pattern baochay_reader.py (AI tự phân loại "thuong"/"dia_chi" trước khi đối
chiếu) — mở rộng thành phân loại 4 nhánh:
- "khi_hoa_long" (B8)  — HFC-227ea/FM200 hoặc FK-5-1-12/Novec1230.
- "khi_nen"      (B9)  — khí trơ IG-100/IG-55/IG-541.
- "khi_co2"      (B10) — CO2 (TCVN 6101:1996 riêng, ngoài phạm vi TCVN 7161).
- "sol_khi"      (B11) — Sol-khí/aerosol (TCVN 13333:2021).

B7 (bọt cố định cho bể chứa xăng dầu NGOÀI TRỜI) CỐ Ý không nằm trong module
này — owner quyết định (2026-08-11, đợt sau khi làm xong 5 nhánh gộp) tách B7
thành 1 card/reader riêng ở đợt việc sau, vì B7 khác hẳn 4 mẫu còn lại (không
có khái niệm "phòng bảo vệ", dùng TCVN 5307:2009 hoàn toàn riêng). Mẫu
B7_bot_co_dinh.docx và registration trong mdc_filler.py vẫn giữ nguyên trong
repo để tái dùng khi viết module riêng cho B7.

Nguồn số liệu DUY NHẤT: 3 file reference của skill ra-mau-doi-chieu-pccc
(khi-hoa-long-khi-nen-cong-thuc.md, khi-co2-tcvn6101.md,
bang-2-hieu-qua-chua-chay.md) — không hardcode số liệu ngoài các file này.

Lưu ý về "Lựa chọn chất chữa cháy" (Bảng 2 QCVN 10:2025/BCA): đã kiểm tra TRỰC
TIẾP nội dung thật của cả 4 template — KHÔNG có id/dòng nào trong B8/B9/B10
đối chiếu trực diện "chất chữa cháy có phù hợp nhóm đám cháy khu vực bảo vệ
không" (khác mô tả trong 1 bản nháp yêu cầu trước đó) — vì vậy đưa Bảng 2 vào
làm NGỮ CẢNH CHUNG (áp dụng khi có căn cứ rõ ràng từ bản vẽ, không ép vào 1 id
cụ thể không tồn tại). Riêng B11 CÓ 2 id khớp đúng nội dung này (id=4 "Phân
loại đám cháy của khu vực bảo vệ", id=5 "Hạn chế của khu vực bảo vệ" — nội
dung quy định của chính id=5 đã liệt kê rõ Sol-khí không dùng cho nhóm nào) —
gắn Bảng 2 trực tiếp vào 2 id này.
"""

from . import mdc_filler, quy_mo_store
from .ai_reader_common import (
    KHONG_UOC_LUONG_KHOANG_CACH,
    NHOM_II_MAU_THUAN_CHECKLIST,
    AIReaderError,
    exclusive_alternative_block,
    read_and_validate_drawing_json,
    system_prompt_version,
)
from .ai_schema import KhiBotSolKhiReaderResult, validate_reader_result

HE_THONG_LIST = ("khi_hoa_long", "khi_nen", "khi_co2", "sol_khi")

HE_THONG_META = {
    "khi_hoa_long": {"mdc_label": "MĐC B8", "ten": "chữa cháy bằng khí hóa lỏng (HFC-227ea/FK-5-1-12)"},
    "khi_nen": {"mdc_label": "MĐC B9", "ten": "chữa cháy bằng khí nén/khí trơ (IG-100/IG-55/IG-541)"},
    "khi_co2": {"mdc_label": "MĐC B10", "ten": "chữa cháy tự động bằng khí CO2"},
    "sol_khi": {"mdc_label": "MĐC B11", "ten": "chữa cháy bằng Sol-khí (aerosol)"},
}

_DAU_HIEU_NHAN_DIEN = {
    "khi_hoa_long": "phòng kín (kỹ thuật/điện/server/kho...), bình chứa khí ghi rõ HFC-227ea/FM200 hoặc FK-5-1-12/Novec1230, đầu phun trần, đường ống xả khí",
    "khi_nen": "phòng kín, bình chứa khí ghi rõ IG-100/Nitơ hoặc IG-55/Argonite hoặc IG-541/Inergen, áp suất bình rất cao (150-300 bar)",
    "khi_co2": "phòng kín, bình/hệ thống ghi rõ CO2/Cacbon dioxit, đầu phun áp suất cao/thấp, biển cảnh báo khí CO2",
    "sol_khi": "phòng kín, bình phun Sol-khí/aerosol, ghi chú nồng độ thiết kế g/m³, không có đường ống dẫn khí (bình phun trực tiếp tại chỗ, khác B8/B9/B10 vốn có hệ ống dẫn từ bình trung tâm)",
}


def _fmt_rows(rows):
    return "\n".join(
        f"id={r['id']} | [{r['doi_chieu']}] {r['quy_dinh']} (Căn cứ: {r['khoan_dieu']})"
        for r in rows
    )


# --- B8: 2 cap loai tru HFC-227ea (id 2,21) vs FK-5-1-12 (id 3,22) ---
_B8_BLOCK = exclusive_alternative_block(
    "id=2, id=21 và id=3, id=22 (loại khí hóa lỏng dùng thực tế)",
    [
        ((2, 21), "HFC-227ea (FM200)"),
        ((3, 22), "FK-5-1-12 (Novec 1230)"),
    ],
    ghi_chu=(
        'LƯU Ý QUAN TRỌNG cho id=22 ("Lượng khí FK-5-1-12"): nội dung quy định gốc của mẫu trích dẫn căn cứ '
        '"Đ 4.2 TCVN 7161-6:2021" — đây là LỖI ĐÁNH MÁY của file mẫu gốc (TCVN 7161-6 không tồn tại cho FK-5-1-12). '
        'Số hiệu ĐÚNG là TCVN 7161-5:2021. Khi viết "noi_dung_thiet_ke" hoặc câu kiến nghị liên quan tới id=22, '
        'PHẢI trích dẫn đúng TCVN 7161-5:2021 — KHÔNG lặp lại lỗi đánh máy TCVN 7161-6:2021 của mẫu gốc.'
    ),
)

# --- B9: cong thuc id=15 chi co san mau IG-100, phai thay dung theo khi that ---
_B9_BLOCK = """YÊU CẦU RIÊNG CHO id=15 ("Lượng khí IG-100"): dòng mẫu gốc chỉ có sẵn công thức minh hoạ cho khí IG-100 (Nitơ 100%), nhưng công thức này áp dụng CHUNG cho cả 3 loại khí trơ — xác định ĐÚNG loại khí trơ bản vẽ thực tế dùng (IG-100/Nitơ, IG-55/Argonite, hoặc IG-541/Inergen) rồi dùng ĐÚNG hằng số k1/k2 và nồng độ thiết kế tương ứng bên dưới khi đối chiếu — TUYỆT ĐỐI KHÔNG áp nguyên công thức/nồng độ IG-100 nếu bản vẽ dùng IG-55 hoặc IG-541 (khác cả k1/k2 lẫn nồng độ thiết kế). Ghi rõ trong "noi_dung_thiet_ke" đã đối chiếu theo đúng loại khí nào.

Công thức chung: S = k1 + k2×T (thể tích riêng, m3/kg; T = nhiệt độ thiết kế °C). m = (V/S)×ln(100/(100−c)) (V = thể tích khu vực nguy hiểm m3; c = nồng độ thiết kế %).

| Khí trơ | TCVN | k1 | k2 | Nồng độ thiết kế — Heptan/loại B | — Bề mặt loại A | — Khu vực nguy hiểm cao hơn A |
|---|---|---|---|---|---|---|
| IG-100 (Nitơ 100%) | 7161-13:2024 | 0,7997 | 0,00293 | 43,7% | 40,3% | 41,5% |
| IG-55 "Argonite" (50%Ar/50%N2) | 7161-14:2024 | 0,6598 | 0,002416 | 47,5% | 40,3% | 45,1% |
| IG-541 "Inergen" (52%N2/40%Ar/8%CO2) | 7161-15:2024 | 0,65799 | 0,00239 | 43,9% | 39,9% | 41,7% |

Cách chọn cột nồng độ: khu vực chứa khí/chất lỏng dễ cháy (LPG, dung môi, kho công nghiệp...) → cột Heptan/loại B (cao hơn); khu vực lưu trữ tài liệu/thiết bị điện tử thông thường (kho hồ sơ, phòng server...) → cột Bề mặt loại A (thấp hơn). Nếu bản vẽ chọn cột thấp hơn cho khu vực chứa chất dễ cháy → thiếu an toàn, cần kiến nghị.
"""

# --- B10: cong thuc + bang 1 (rut gon) cho id=15, thoi gian xa/duy tri id=13,14 ---
_B10_BLOCK = """YÊU CẦU RIÊNG CHO id=13, id=14, id=15 (thời gian xả, thời gian duy trì, lượng khí CO2): dùng công thức và Bảng 1 (rút gọn) dưới đây — xác định ĐÚNG loại vật liệu/hạng mục khu vực bảo vệ trên bản vẽ để chọn đúng hàng, không suy đoán nếu bản vẽ không nêu rõ vật liệu/công năng khu vực bảo vệ (khi đó ghi "chưa thể hiện").

Công thức (Điều 15, id=15): m = KB × (0,2A + 0,7V) — m: khối lượng CO2 (kg); A = AV + 30×AOV (AV: tổng diện tích sàn+trần kể cả chỗ hở m²; AOV: tổng diện tích chỗ hở giả thiết mở khi cháy m²); V: thể tích khu vực bảo vệ (m3); KB: hệ số vật liệu theo bảng dưới.

| Vật liệu/hạng mục | KB | Nồng độ CO2 thiết kế | Thời gian duy trì |
|---|---|---|---|
| Xăng, Hexan, Heptan-n, dầu nhờn, Metan, điêzel | 1 | 34% | - |
| Buồng cáp và ống cáp | 1,4 | 47% | 10 phút |
| Vùng xử lý dữ liệu (phòng server) | 2,25 | 62% | 20 phút |
| Chỗ đặt máy tính | 1,5 | 47% | 10 phút |
| Buồng phân phối và tủ mở điện | 1,2 | 40% | 10 phút |
| Phát điện (kể cả hệ làm lạnh) | 2 | 58% | Cho tới khi dừng |
| Biến thế dầu | 2 | 58% | - |
| Vật liệu xenlulo, giấy | 2,25 | 62% | 20 phút |

*Bảng trên chỉ trích các hạng mục phổ biến trên bản vẽ PCCC nhà xưởng/tòa nhà — nếu vật liệu/hạng mục khu vực bảo vệ KHÔNG có trong bảng trên, ghi rõ "chưa thể hiện đủ căn cứ để đối chiếu — cần tra Bảng 1 đầy đủ TCVN 6101:1996 cho đúng loại vật liệu", không tự suy đoán hệ số.*

Thời gian xả (id=13, Bảng 2 TCVN 6101:1996): chữa cháy thể tích ≤60 giây; chữa cháy cục bộ 30-60 giây.
"""

# --- B11: gan Bang 2 QCVN 10:2025/BCA vao dung id=4/id=5 (noi dung quy_dinh cua
# chinh 2 id nay da ban ve phan loai dam chay/han che su dung) ---
_B11_BLOCK = """YÊU CẦU RIÊNG CHO id=4, id=5 (phân loại đám cháy khu vực bảo vệ, hạn chế sử dụng): đối chiếu công năng/vật liệu/thiết bị khu vực bảo vệ với Bảng 2 QCVN 10:2025/BCA (hiệu quả chất chữa cháy) dưới đây — Sol-khí hiệu quả với đám cháy nhóm A (chất rắn), B (chất lỏng), C (chất khí), E (thiết bị điện) nhưng KHÔNG phù hợp đám cháy nhóm D (kim loại/kim loại kiềm — vd nhôm, magiê, natri, kali...). Nếu khu vực bảo vệ trên bản vẽ có công năng/vật liệu thuộc nhóm D (xưởng gia công kim loại nhẹ, kho hóa chất kim loại kiềm...) mà vẫn thiết kế Sol-khí: đây là "chua_dat", kiến nghị xếp nhóm III, nêu rõ Sol-khí không phù hợp đám cháy nhóm D (Căn cứ Bảng 2 QCVN 10:2025/BCA). Nếu bản vẽ không nêu rõ vật liệu/công năng khu vực bảo vệ: không suy đoán, "chua_the_hien" như bình thường.
"""

_SPECIAL_BLOCKS = {
    "khi_hoa_long": _B8_BLOCK,
    "khi_nen": _B9_BLOCK,
    "khi_co2": _B10_BLOCK,
    "sol_khi": _B11_BLOCK,
}

# 3 quy tac mac dinh rieng nhom B8-B11 (KHONG ap dung B7 - khong co khai niem
# "phong bao ve", va B7 gio khong con trong module nay nua) - owner chot
# 2026-08-11, xem mapping-he-thong-form.md muc "Quy tac mac dinh rieng". Day la
# NGOAI LE co chu dich so voi nguyen tac chung "thieu la noi thieu, khong gia
# dinh" - CHI ap dung dung 2 quy tac 1-2 duoi day, quy tac 3 van giu nguyen tac
# chung (khong mac dinh). Ap dung cho MOI he con lai trong module nay (khong
# can dieu kien loai tru nua vi bot_co_dinh da bi bo khoi HE_THONG_LIST).
_B8_B11_DEFAULT_RULES = """QUY TẮC MẶC ĐỊNH RIÊNG cho hệ thống này (B8-B11 — khu vực bảo vệ dạng phòng kín, KHÔNG áp dụng cho B7):
1. Tính thường xuyên có người: nếu khu vực bảo vệ là phòng kỹ thuật/điện/server/phòng máy (nơi hầu như không có người lui tới thường xuyên) VÀ bản vẽ không ghi rõ: mặc định coi là "khu vực thường không có người" — KHÔNG tạo kiến nghị cho nội dung này dù bản vẽ không ghi rõ.
2. Kết cấu bao che kín khí: nếu bản vẽ/thuyết minh không có thông tin về độ kín/lỗ hở của khu vực bảo vệ: mặc định coi là "kín 100%, không có lỗ hở" — KHÔNG tạo kiến nghị cho nội dung này dù bản vẽ không ghi rõ.
3. MỌI nội dung khác còn thiếu (ví dụ: khoảng cách an toàn tối thiểu từ bình phun tới người/vật liệu dễ cháy...): áp dụng nguyên tắc chung bình thường — ghi "chưa thể hiện trên bản vẽ cung cấp" và đưa vào kiến nghị nhóm I, KHÔNG mặc định như quy tắc 1-2 ở trên.
"""


def _build_system_prompt():
    dau_hieu_list = "\n".join(f'- "{k}" ({HE_THONG_META[k]["ten"]}): {v}' for k, v in _DAU_HIEU_NHAN_DIEN.items())

    he_thong_blocks = []
    for he_thong in HE_THONG_LIST:
        meta = HE_THONG_META[he_thong]
        rows = mdc_filler.load_criteria_rows(he_thong)
        special = _SPECIAL_BLOCKS.get(he_thong, "")
        he_thong_blocks.append(f"""--- NẾU he_thong = "{he_thong}" ({meta['mdc_label']} — {meta['ten']}) ---
{_B8_B11_DEFAULT_RULES}{special}
DANH SÁCH TIÊU CHÍ ({meta['mdc_label']}):
{_fmt_rows(rows)}""")

    return f"""Bạn là kỹ sư PCCC rà soát bản vẽ hệ thống chữa cháy bằng khí/sol-khí, đối chiếu với 1 trong 4 mẫu đối chiếu MĐC B8-B11. 4 hệ thống này THAY THẾ LẪN NHAU cho cùng 1 nhu cầu bảo vệ — 1 bản vẽ/1 khu vực bảo vệ chỉ dùng ĐÚNG 1 trong 4 hệ, không bao giờ dùng đồng thời nhiều hệ cho cùng 1 khu vực.

YÊU CẦU THÊM: Đọc SỐ HIỆU BẢN VẼ ghi trong khung tên (title block) của chính bản vẽ này. Nếu khung tên không có, không rõ, hoặc bản vẽ không thể hiện số hiệu: ghi ĐÚNG NGUYÊN VĂN "Không xác định được số hiệu bản vẽ" ở trường "so_hieu_ban_ve" — TUYỆT ĐỐI không suy đoán.

BƯỚC 1 — Xác định bản vẽ được cung cấp thuộc ĐÚNG 1 trong 4 hệ thống sau, căn cứ dấu hiệu nhận diện cụ thể trên bản vẽ (không suy đoán từ loại công trình):
{dau_hieu_list}
Nêu rõ dấu hiệu nhận biết đã dùng trong "ly_do_nhan_dien".

BƯỚC 2 — CHỈ đối chiếu bản vẽ với danh sách tiêu chí thuộc ĐÚNG hệ thống đã xác định ở Bước 1 (KHÔNG trả lời cho danh sách của 3 hệ còn lại). Mỗi dòng tiêu chí có sẵn "id" — khi trả lời PHẢI giữ nguyên đúng id đó, và phải trả lời ĐỦ cho TẤT CẢ id thuộc hệ đã xác định, không bỏ sót. Với mỗi id, trả về:
- "noi_dung_thiet_ke": nội dung điền vào cột "Nội dung thiết kế" — ngắn gọn, đúng mạch đối chiếu (dùng gạch đầu dòng "-" nếu nhiều ý), nêu số liệu cụ thể NHÌN THẤY trên bản vẽ. Nếu bản vẽ không thể hiện đủ thông tin: ghi đúng "Chưa thể hiện trên bản vẽ cung cấp".
- "ket_luan": "dat" | "chua_dat" | "chua_the_hien" | "khong_ap_dung" (CHỈ dùng "khong_ap_dung" cho đúng các id có hướng dẫn riêng bên dưới chỉ định rõ — KHÔNG tự ý dùng cho id khác).

{chr(10).join(he_thong_blocks)}

BƯỚC 3 — Với MỖI id có "ket_luan" là "chua_dat" hoặc "chua_the_hien" ở Bước 2, soạn thêm một câu kiến nghị theo đúng văn phong công văn PC07:
- Mở đầu bằng động từ mệnh lệnh phù hợp: "Thể hiện rõ ..." (chua_the_hien), "Bổ sung ..." (thiếu chi tiết/thiết bị/bản vẽ), hoặc "Thuyết minh rõ ..." (cần giải trình).
- Một câu mạch lạc, nêu rõ đối tượng cụ thể trên bản vẽ + số liệu định lượng của tiêu chuẩn (lấy từ đúng nội dung quy định của id tương ứng).
- Kết câu bằng phần căn cứ trong ngoặc đơn, lấy ĐÚNG Khoản/Điều đã ghi ở id đó — không tự bịa số Điều khác (riêng id=22 của B8, xem lưu ý sửa lỗi đánh máy ở trên).
- Xếp mỗi kiến nghị vào đúng 1 trong 4 nhóm sau:
  - "chua_the_hien": nhóm I (nội dung chưa thể hiện trên bản vẽ).
  - "chua_dat": nhóm III (nội dung đã thể hiện nhưng vi phạm giá trị/quy định của tiêu chuẩn).
  - Nhóm II (chưa thống nhất giữa nhiều nguồn số liệu) và nhóm IV (đề xuất bổ sung hồ sơ/bản vẽ mới) CHỈ dùng khi có căn cứ rõ ràng từ chính bản vẽ này; nếu không có căn cứ, để mảng rỗng — KHÔNG cố tạo kiến nghị cho đủ 4 nhóm.
{NHOM_II_MAU_THUAN_CHECKLIST}
- id có "ket_luan" là "khong_ap_dung": KHÔNG tạo kiến nghị nào.
- Nếu mọi id đều "dat" hoặc "khong_ap_dung", để cả 4 mảng đều rỗng.

NGUYÊN TẮC BẮT BUỘC:
- Chỉ đánh giá dựa trên nội dung THỰC SỰ thể hiện trên bản vẽ được cung cấp. Không suy đoán, không dùng kiến thức chung ngoài bản vẽ.
- Không được bỏ sót bất kỳ id nào thuộc hệ thống đã xác định.
{KHONG_UOC_LUONG_KHOANG_CACH}

Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON:
{{
  "he_thong": "khi_hoa_long" | "khi_nen" | "khi_co2" | "sol_khi",
  "ly_do_nhan_dien": "câu ngắn giải thích vì sao xác định hệ này",
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

KhiBotSolKhiReaderError = AIReaderError

_EXPECTED_IDS = {he_thong: {r["id"] for r in mdc_filler.load_criteria_rows(he_thong)} for he_thong in HE_THONG_LIST}


def _validate(data: dict):
    he_thong = data.get("he_thong")
    expected_ids = _EXPECTED_IDS.get(he_thong, _EXPECTED_IDS["khi_hoa_long"])
    return validate_reader_result(data, expected_ids, KhiBotSolKhiReaderResult)


def read_drawing(file_bytes: bytes, media_type: str, provider, quy_mo: dict = None) -> dict:
    """Gửi bản vẽ (ảnh hoặc PDF) kèm tiêu chí tới AI provider, validate qua Pydantic
    (kèm retry-repair 1 lần nếu sai), trả về dict.

    quy_mo: dữ liệu quy mô công trình (hạng mục "Quy mô") của CÙNG phiên Bộ hồ
    sơ, nếu người dùng CÓ đính kèm — HOÀN TOÀN TUỲ CHỌN (None nếu không đính,
    hành vi giữ nguyên 100% như trước, kể cả 3 fallback "chưa đủ thông tin quy
    mô" gốc của _scope_dependent_block()).
    """
    system_prompt = SYSTEM_PROMPT + quy_mo_store.format_quy_mo_context(quy_mo) if quy_mo else SYSTEM_PROMPT
    model = read_and_validate_drawing_json(
        file_bytes, media_type, provider, system_prompt, _validate, prompt_version=SYSTEM_PROMPT_VERSION
    )
    return model.model_dump()
