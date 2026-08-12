"""Khoá lại việc chèn TOA_DO_TRUC_KHOANG_CACH (ai_reader_common.py) vào system
prompt của ccnuoc_reader.py — CHỈ mẫu B6 (chua_chay_tu_dong, sprinkler/drencher)
có tiêu chí khoảng cách, B3 (tram_bom)/B5 (hong_nuoc) không có nên KHÔNG được
chèn (cùng điều kiện với KHONG_UOC_LUONG_KHOANG_CACH đã có)."""

from app.services.ccnuoc_reader import SYSTEM_PROMPTS


def test_toa_do_truc_khoang_cach_present_twice_only_in_chua_chay_tu_dong():
    assert SYSTEM_PROMPTS["chua_chay_tu_dong"].count("tại vị trí trục") == 2
    assert SYSTEM_PROMPTS["tram_bom"].count("tại vị trí trục") == 0
    assert SYSTEM_PROMPTS["hong_nuoc"].count("tại vị trí trục") == 0
