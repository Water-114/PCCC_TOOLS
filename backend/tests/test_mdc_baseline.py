"""Ghi nhận baseline 'số tiêu chí MĐC' theo yêu cầu Batch 0 — không gọi AI,
không tốn phí, chỉ đọc trực tiếp số dòng từ file mẫu MĐC .docx hiện có.

Nếu ai đó sửa file mẫu trong backend/app/services/mdc_templates/ làm lệch
số dòng tiêu chí, test này sẽ báo động ngay (mốc hồi quy).

binh_chua_chay (B12) = 20, KHÔNG phải 24 như lần đầu đăng ký file mẫu — phát
hiện thật khi test AI thật trên production (2026-08-02): file mẫu B12 có 4
dòng tiêu đề nhóm bị merge NGUYÊN CẢ HÀNG (6 cột) thay vì chỉ merge đúng 1 cột
nhãn, khiến _extract_rows() hiểu nhầm là tiêu chí thật (cột "quy_dinh" không
rỗng vì bị merge chung nội dung tiêu đề) — AI phải trả lời cho tiêu chí giả
này, ghi đè nội dung tiêu đề gốc bằng "Đạt". Đã sửa mdc_filler._extract_rows()
thêm điều kiện lọc: bỏ dòng khi doi_chieu == quy_dinh == khoan_dieu (dấu hiệu
chắc chắn của hàng bị merge sai, không thể là tiêu chí thật vì tiêu chí thật
luôn có nội dung quy định khác với tên đối chiếu). Test này khoá lại đúng số
20 để không tái phát nếu ai sửa lại _extract_rows() hoặc thay file mẫu.
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
    "binh_chua_chay": 20,
    "den_su_co": 18,
}


def test_binh_chua_chay_skips_merged_header_rows_not_just_empty_ones():
    """Regression rieng cho loi merged-row (xem docstring dau file) - dam bao
    khong con dong nao trong rows co doi_chieu == quy_dinh == khoan_dieu
    (dau hieu hang bi merge sai bi lot qua bo loc)."""
    rows = mdc_filler.load_criteria_rows("binh_chua_chay")
    for row in rows:
        assert not (row["doi_chieu"] == row["quy_dinh"] == row["khoan_dieu"]), (
            f"Dong id={row['id']} co ve la header bi merge sai lot qua bo loc: {row}"
        )


@pytest.mark.parametrize("loai,expected_count", EXPECTED_ROW_COUNTS.items())
def test_mdc_criteria_row_count_baseline(loai, expected_count):
    rows = mdc_filler.load_criteria_rows(loai)
    assert len(rows) == expected_count
