"""Batch 4 (mở rộng) — khoá lại nội dung 5 khối hướng dẫn đặc biệt trong system
prompt của densucco_reader.py (B12/B13), theo đúng chỉ đạo nghiệp vụ của owner
(không phải suy đoán — ngưỡng số lấy từ backend/app/services/phuong_tien.py):

1. B12 id 4,7,8,9,10,11 (mức nguy hiểm + tính bình) — yêu cầu nêu rõ nguồn xác
   định công năng, KHÔNG đổi ngưỡng/logic đối chiếu.
2. B12 id 14,15 (bình bột tự động treo) — tuỳ chọn, không "Bổ sung" khi vắng.
3. B12 id 28,29 (mặt nạ lọc độc) — thuộc diện theo evaluate_mat_na().
4. B13 id 15,19 (biển tầm thấp) — thuộc diện theo evaluate_den().
5. B13 id 24,25,26 (loa thông báo) — thuộc diện theo evaluate_loa().

Không gọi AI thật — chỉ kiểm tra chuỗi system prompt sinh ra có đúng nội dung
mong đợi hay không (test hồi quy cho prompt engineering, không phải hành vi
AI thật)."""

from app.services.densucco_reader import CHUA_DU_QUY_MO_TEXT, SYSTEM_PROMPTS
from app.services.phuong_tien import BINH_TBL, TT1_CONGCONG

BINH_PROMPT = SYSTEM_PROMPTS["binh_chua_chay"]
DEN_PROMPT = SYSTEM_PROMPTS["den_su_co"]


def test_muc_nguy_hiem_block_present_with_correct_ids():
    assert "YÊU CẦU RIÊNG CHO id=4, 7, 8, 9, 10, 11" in BINH_PROMPT
    assert "nêu rõ đã căn cứ ghi chú/thuyết minh/tên dự án nào trên bản vẽ" in BINH_PROMPT
    # Khong doi nguong/logic doi chieu hien co (BINH_TBL) - chi yeu cau minh bach nguon
    assert set(BINH_TBL.keys()) == {"thap", "tb", "cao"}


def test_binh_bot_treo_block_present_and_not_bo_sung_when_absent():
    assert "YÊU CẦU RIÊNG CHO id=14, 15" in BINH_PROMPT
    assert "TUỲ CHỌN" in BINH_PROMPT
    assert '"ket_luan": "dat" (KHÔNG phải "chua_the_hien")' in BINH_PROMPT
    assert "Không có thiết kế bình bột chữa cháy tự động loại treo" in BINH_PROMPT
    assert "KHÔNG tạo kiến nghị" in BINH_PROMPT


def test_mat_na_block_present_matches_evaluate_mat_na_thresholds():
    assert "YÊU CẦU RIÊNG CHO id=28, 29" in BINH_PROMPT
    # Dung ngung so tu evaluate_mat_na(): khach san >= 3 tang, karaoke khong phu thuoc quy mo
    assert "khách sạn/cơ sở lưu trú có số tầng ≥ 3" in BINH_PROMPT
    assert "karaoke/vũ trường (không phụ thuộc quy mô)" in BINH_PROMPT
    assert "evaluate_mat_na()" in BINH_PROMPT
    assert "Phụ lục F QCVN 10:2025/BCA" in BINH_PROMPT
    assert CHUA_DU_QUY_MO_TEXT in BINH_PROMPT
    assert "NHÓM IV" in BINH_PROMPT


def test_bien_tam_thap_block_present_matches_evaluate_den_thresholds():
    assert "YÊU CẦU RIÊNG CHO id=15, 19" in DEN_PROMPT
    # Dung ngung so tu evaluate_den(): khach san >=7 tang, HOAC khoi tich >=5000
    assert "khách sạn có số tầng ≥ 7" in DEN_PROMPT
    assert "khối tích công trình ≥ 5.000 m³" in DEN_PROMPT
    assert "hành lang thoát nạn dài hơn 10 m" in DEN_PROMPT
    assert "evaluate_den()" in DEN_PROMPT
    assert "Điều 5.2.3 TCVN 13456:2022" in DEN_PROMPT
    assert CHUA_DU_QUY_MO_TEXT in DEN_PROMPT


def test_loa_thong_bao_block_present_matches_evaluate_loa_thresholds():
    assert "YÊU CẦU RIÊNG CHO id=24, 25, 26" in DEN_PROMPT
    # Dung dieu kien tu evaluate_loa(): TT1 (>10 tang hoac >=2 tang ham),
    # TT2 (>=50 nguoi/tang), TT3 (>=18.000 m2 nha de xe kin),
    # TT4 (>=18.000 m2 VA >=300 nguoi/tang), TT6 (nha ga)
    assert "cao trên 10 tầng" in DEN_PROMPT
    assert "2 tầng hầm trở lên" in DEN_PROMPT
    assert "≥50 người/tầng" in DEN_PROMPT
    assert "ΣF ≥18.000 m²" in DEN_PROMPT
    assert "≥300 người/tầng đồng thời" in DEN_PROMPT
    assert "nhà ga hành khách — luôn thuộc diện" in DEN_PROMPT
    assert "evaluate_loa()" in DEN_PROMPT
    assert "Phụ lục G QCVN 10:2025/BCA" in DEN_PROMPT
    assert CHUA_DU_QUY_MO_TEXT in DEN_PROMPT


def test_tt1_congcong_set_referenced_matches_phuong_tien_source():
    """Xac nhan test nay tham chieu dung TT1_CONGCONG that trong phuong_tien.py
    (khong phai danh sach tu bia) - dam bao neu owner doi tap cong nang TT1 sau
    nay, test se nhac nho cap nhat lai prompt densucco tuong ung."""
    assert "chungcu" in TT1_CONGCONG
    assert "khachsan" in TT1_CONGCONG


def test_special_blocks_do_not_appear_in_wrong_prompt():
    """Block dac thu cua B12 khong duoc lot sang B13 va nguoc lai."""
    assert "YÊU CẦU RIÊNG CHO id=4, 7, 8, 9, 10, 11" not in DEN_PROMPT
    assert "YÊU CẦU RIÊNG CHO id=14, 15" not in DEN_PROMPT
    assert "YÊU CẦU RIÊNG CHO id=28, 29" not in DEN_PROMPT
    assert "YÊU CẦU RIÊNG CHO id=15, 19" not in BINH_PROMPT
    assert "YÊU CẦU RIÊNG CHO id=24, 25, 26" not in BINH_PROMPT
