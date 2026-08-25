"""B15 (chữa cháy tự động giá kệ hàng, TCVN 14496:2025) — khoá lại nội dung
system prompt của gia_ke_hang_reader.py: đúng 74 id (khớp danh sách owner đã
trích sẵn từ B15_chua_chay_gia_ke_hang.docx, tự kiểm chứng lại qua
mdc_filler._extract_rows() thật), khối 2 nhánh loại trừ lẫn nhau ("mot_tang"/
"nhieu_tang"), các bảng số phụ (Bảng 2/4/5/6/7) không có sẵn trong nội dung
.docx (chỉ nhắc tên bảng) nên phải nhúng riêng trong system prompt, quy tắc
"cột áp -> Tính toán" cho id=45/60/78/80.

Không gọi AI thật — chỉ kiểm tra chuỗi system prompt sinh ra (test hồi quy cho
prompt engineering, giống test_botcodinh_reader_prompt_content.py)."""

from app.services import mdc_filler
from app.services.gia_ke_hang_reader import (
    SYSTEM_PROMPT,
    _EXPECTED_IDS,
    _MOT_TANG_IDS,
    _NHIEU_TANG_IDS,
)

_MOT_TANG_LIST = [38, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
_NHIEU_TANG_LIST = [
    53, 56, 57, 58, 59, 60, 62, 63, 64, 65, 66, 67, 68, 69, 70,
    73, 74, 75, 76, 77, 78, 79, 80, 82, 83, 84, 85, 86, 88, 89,
]
_COMMON_LIST = [
    1, 2, 5, 6, 7, 8, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22,
    23, 24, 25, 26, 28, 29, 30, 31, 32, 33, 34, 35, 36,
]
_ALL_EXPECTED_LIST = sorted(_COMMON_LIST + _MOT_TANG_LIST + _NHIEU_TANG_LIST)


def test_expected_ids_match_real_docx():
    rows = mdc_filler.load_criteria_rows("chua_chay_gia_ke_hang")
    assert [r["id"] for r in rows] == _ALL_EXPECTED_LIST
    assert len(_ALL_EXPECTED_LIST) == 74
    assert _EXPECTED_IDS == set(_ALL_EXPECTED_LIST)
    assert tuple(_MOT_TANG_IDS) == tuple(_MOT_TANG_LIST)
    assert tuple(_NHIEU_TANG_IDS) == tuple(_NHIEU_TANG_LIST)


def test_criteria_list_contains_all_74_ids():
    for i in _ALL_EXPECTED_LIST:
        assert f"id={i} |" in SYSTEM_PROMPT


def test_nhanh_block_present_with_exact_wording():
    assert '"x - Không áp dụng"' in SYSTEM_PROMPT
    assert 'Hệ 1 tầng đầu phun' in SYSTEM_PROMPT
    assert 'Hệ nhiều tầng đầu phun' in SYSTEM_PROMPT
    assert '"nhanh": "mot_tang" | "nhieu_tang"' in SYSTEM_PROMPT


def test_branch_selection_criteria_present():
    assert "5,5-12,5m" in SYSTEM_PROMPT
    assert "H ≤14m" in SYSTEM_PROMPT
    assert "đến 25m" in SYSTEM_PROMPT
    assert "chieuCaoKeHang" not in SYSTEM_PROMPT  # ten field noi bo, khong lo ra prompt - chi mo ta bang loi


def test_bang_2_psi_present():
    assert "Bảng 2" in SYSTEM_PROMPT
    assert "0,06" in SYSTEM_PROMPT


def test_bang_4_dau_phun_gia_do_present():
    assert "Bảng 4" in SYSTEM_PROMPT
    assert "Lỗ phun 12mm" in SYSTEM_PROMPT
    assert "Lỗ phun 15mm" in SYSTEM_PROMPT


def test_bang_5_chieu_dai_a_present():
    assert "Bảng 5" in SYSTEM_PROMPT
    assert "Dạng hộp bằng kim loại" in SYSTEM_PROMPT


def test_bang_6_cuong_do_phun_present_and_correct_values():
    """Bang 6 la diem de sai nhat (tra theo 2 chieu) - phai co du 3x3 gia tri."""
    assert "Bảng 6" in SYSTEM_PROMPT
    assert "Vật liệu dễ cháy thể rắn" in SYSTEM_PROMPT
    assert "Sản phẩm cao su" in SYSTEM_PROMPT
    assert "0,24" in SYSTEM_PROMPT and "0,36" in SYSTEM_PROMPT and "0,5" in SYSTEM_PROMPT
    assert "0,40" in SYSTEM_PROMPT and "0,60" in SYSTEM_PROMPT and "0,8" in SYSTEM_PROMPT


def test_bang_7_vat_lieu_tam_chan_present():
    assert "Bảng 7" in SYSTEM_PROMPT
    assert "Tấm thép" in SYSTEM_PROMPT
    assert "Tấm vật liệu từ xi măng" in SYSTEM_PROMPT


def test_cot_ap_khong_tu_tinh_note_present():
    assert "id=45, id=60, id=78, id=80" in SYSTEM_PROMPT
    assert "KHÔNG tự thực hiện chuỗi tính toán này" in SYSTEM_PROMPT


def test_khong_uoc_luong_khoang_cach_rule_present():
    from app.services.ai_reader_common import KHONG_UOC_LUONG_KHOANG_CACH
    assert SYSTEM_PROMPT.count(KHONG_UOC_LUONG_KHOANG_CACH.strip()[:40]) == 1


def test_toa_do_truc_khoang_cach_present_twice():
    assert SYSTEM_PROMPT.count("tại vị trí trục") == 2


def test_shared_checklist_reused_not_duplicated():
    from app.services.ai_reader_common import NHOM_II_MAU_THUAN_CHECKLIST
    assert SYSTEM_PROMPT.count(NHOM_II_MAU_THUAN_CHECKLIST.strip()[:40]) == 1


def test_no_khibotsolkhi_style_he_thong_classification():
    """B15 dung truong 'nhanh' (khong phai 'he_thong' nhu khibotsolkhi_reader.py)."""
    assert '"he_thong"' not in SYSTEM_PROMPT
    assert 'NẾU he_thong' not in SYSTEM_PROMPT
