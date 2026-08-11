"""Batch 5A mở rộng (B8-B11) — khoá lại nội dung system prompt của
khibotsolkhi_reader.py: đủ 4 nhánh phân loại, đúng id từng nhánh (khớp danh
sách owner đã trích sẵn từ 4 file .docx thật), 2 cặp/khối đặc thù (B8 loại khí,
B9 công thức theo khí trơ), 3 quy tắc mặc định áp dụng cho cả 4 nhánh, ghi chú
sửa lỗi đánh máy TCVN 7161-6→7161-5.

B7 (bọt cố định) CỐ Ý không còn trong module này (owner tách riêng, làm sau) —
mẫu B7_bot_co_dinh.docx + registration trong mdc_filler.py vẫn còn, chỉ không
có nhánh he_thong nào gọi tới nữa trong khibotsolkhi_reader.py.

Không gọi AI thật — chỉ kiểm tra chuỗi system prompt sinh ra (test hồi quy cho
prompt engineering, giống test_densucco_reader_prompt_content.py)."""

from app.services import mdc_filler
from app.services.khibotsolkhi_reader import HE_THONG_LIST, SYSTEM_PROMPT, _EXPECTED_IDS

EXPECTED_IDS_BY_HE_THONG = {
    "khi_hoa_long": [2, 3, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 19, 21, 22],
    "khi_nen": [3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 15, 16],
    "khi_co2": [3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16],
    "sol_khi": [4, 5, 6, 7, 9, 10, 11, 13, 15, 16, 17, 19, 20, 21, 22, 24, 25, 26, 27, 28, 29, 30],
}

# id 15 (bot_co_dinh, B7) — KHONG con reader nao goi toi nua, nhung registration
# trong mdc_filler.py van con nguyen (co y giu lai) — xac nhan van doc duoc.
_BOT_CO_DINH_EXPECTED_IDS = [2, 3, 5, 7, 8, 9, 11, 14, 15, 16, 17, 19, 21, 22, 23]


def test_all_4_loai_load_expected_ids_from_real_docx():
    for he_thong, expected in EXPECTED_IDS_BY_HE_THONG.items():
        rows = mdc_filler.load_criteria_rows(he_thong)
        assert [r["id"] for r in rows] == expected, he_thong


def test_bot_co_dinh_registration_still_works_in_mdc_filler_though_unused():
    """B7 CO Y khong con trong HE_THONG_LIST/khibotsolkhi_reader.py nua, nhung
    mdc_filler.py van giu registration (chua xoa) de tai dung khi lam reader
    rieng cho B7 sau nay - xac nhan registration do van hoat dong binh thuong."""
    rows = mdc_filler.load_criteria_rows("bot_co_dinh")
    assert [r["id"] for r in rows] == _BOT_CO_DINH_EXPECTED_IDS
    assert "bot_co_dinh" not in HE_THONG_LIST


def test_expected_ids_cache_matches_docx():
    for he_thong, expected in EXPECTED_IDS_BY_HE_THONG.items():
        assert _EXPECTED_IDS[he_thong] == set(expected), he_thong


def test_all_4_he_thong_listed_in_classification_step():
    for he_thong in HE_THONG_LIST:
        assert f'"{he_thong}"' in SYSTEM_PROMPT


def test_b8_gas_exclusive_pairs_present():
    assert "YÊU CẦU RIÊNG CHO id=2, id=21 và id=3, id=22" in SYSTEM_PROMPT
    assert "HFC-227ea (FM200)" in SYSTEM_PROMPT
    assert "FK-5-1-12 (Novec 1230)" in SYSTEM_PROMPT
    assert '"ket_luan": "khong_ap_dung"' in SYSTEM_PROMPT


def test_b8_typo_fix_note_present():
    """Skill da xac nhan file mau goc ghi nham 'TCVN 7161-6:2021' cho FK-5-1-12
    (dung phai la TCVN 7161-5:2021) - prompt PHAI huong dan AI dung dung so,
    khong lap lai loi danh may cua mau goc."""
    assert "TCVN 7161-6:2021" in SYSTEM_PROMPT  # nhac ten loi de AI biet tranh
    assert "LỖI ĐÁNH MÁY" in SYSTEM_PROMPT
    assert "TCVN 7161-5:2021" in SYSTEM_PROMPT  # so dung


def test_b9_formula_substitution_block_present_with_all_3_gases():
    assert 'YÊU CẦU RIÊNG CHO id=15 ("Lượng khí IG-100")' in SYSTEM_PROMPT
    assert "IG-100" in SYSTEM_PROMPT and "IG-55" in SYSTEM_PROMPT and "IG-541" in SYSTEM_PROMPT
    assert "0,7997" in SYSTEM_PROMPT  # k1 cua IG-100
    assert "0,6598" in SYSTEM_PROMPT  # k1 cua IG-55
    assert "0,65799" in SYSTEM_PROMPT  # k1 cua IG-541
    assert "43,7%" in SYSTEM_PROMPT  # nong do IG-100 Heptan


def test_b10_material_table_and_formula_present():
    assert "m = KB × (0,2A + 0,7V)" in SYSTEM_PROMPT
    assert "Vùng xử lý dữ liệu (phòng server)" in SYSTEM_PROMPT
    assert "62%" in SYSTEM_PROMPT


def test_b11_bang2_selection_tied_to_id_4_5():
    assert "YÊU CẦU RIÊNG CHO id=4, id=5" in SYSTEM_PROMPT
    assert "nhóm D" in SYSTEM_PROMPT
    assert "Bảng 2 QCVN 10:2025/BCA" in SYSTEM_PROMPT


def test_default_rules_present_for_b8_b11_context():
    assert "QUY TẮC MẶC ĐỊNH RIÊNG" in SYSTEM_PROMPT
    assert "khu vực thường không có người" in SYSTEM_PROMPT
    assert "kín 100%, không có lỗ hở" in SYSTEM_PROMPT


def test_shared_rules_reused_not_duplicated_per_branch():
    """NHOM_II_MAU_THUAN_CHECKLIST va KHONG_UOC_LUONG_KHOANG_CACH la constant
    dung chung toan he thong - chi xuat hien 1 lan trong prompt (o phan chung),
    khong lap lai theo tung nhanh he_thong (tranh prompt phinh to khong can
    thiet, giong cach merged_reader.py da lam)."""
    from app.services.ai_reader_common import KHONG_UOC_LUONG_KHOANG_CACH, NHOM_II_MAU_THUAN_CHECKLIST
    assert SYSTEM_PROMPT.count(NHOM_II_MAU_THUAN_CHECKLIST.strip()[:40]) == 1
    assert SYSTEM_PROMPT.count(KHONG_UOC_LUONG_KHOANG_CACH.strip()[:40]) == 1


def test_4_branches_each_have_own_criteria_list_header():
    for he_thong in HE_THONG_LIST:
        assert f'NẾU he_thong = "{he_thong}"' in SYSTEM_PROMPT
    assert len(HE_THONG_LIST) == 4
