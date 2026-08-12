"""Khoá lại việc chèn TOA_DO_TRUC_KHOANG_CACH (ai_reader_common.py) vào system
prompt của baochay_reader.py — tọa độ trục kết cấu cho thiết bị vi phạm
khoảng cách, chèn ở CẢ 2 vị trí (noi_dung_thiet_ke lẫn câu kiến nghị)."""

from app.services.baochay_reader import SYSTEM_PROMPT


def test_toa_do_truc_khoang_cach_present_twice():
    """1 lan o Buoc 2 (noi_dung_thiet_ke, cot 3 bang MDC) va 1 lan o Buoc 3
    (cau kien nghi)."""
    assert SYSTEM_PROMPT.count("tại vị trí trục") == 2
