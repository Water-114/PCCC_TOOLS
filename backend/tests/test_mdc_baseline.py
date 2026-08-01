"""Ghi nhận baseline 'số tiêu chí MĐC' theo yêu cầu Batch 0 — không gọi AI,
không tốn phí, chỉ đọc trực tiếp số dòng từ 6 file mẫu MĐC .docx hiện có.

Nếu ai đó sửa file mẫu trong backend/app/services/mdc_templates/ làm lệch
số dòng tiêu chí, test này sẽ báo động ngay (mốc hồi quy).
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app.services import mdc_filler

EXPECTED_ROW_COUNTS = {
    "thuong": 47,
    "dia_chi": 45,
    "dien_pccc": 17,
    "tram_bom": 25,
    "hong_nuoc": 16,
    "chua_chay_tu_dong": 48,
}


@pytest.mark.parametrize("loai,expected_count", EXPECTED_ROW_COUNTS.items())
def test_mdc_criteria_row_count_baseline(loai, expected_count):
    rows = mdc_filler.load_criteria_rows(loai)
    assert len(rows) == expected_count
