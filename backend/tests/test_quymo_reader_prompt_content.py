"""Quy mô Giai đoạn 1, Phần D.2 — khoá lại việc quymo_reader.py (đọc ĐÚNG bản
vẽ kiến trúc) cũng trích được 2 field mới chieuCaoKeHang/coBeXangDauNgoaiTroi,
không chỉ scan_quymo_reader.py (Lượt 0)."""

from app.services.quymo_reader import SYSTEM_PROMPT


def test_prompt_includes_new_d2_fields():
    assert "chieuCaoKeHang" in SYSTEM_PROMPT
    assert "coBeXangDauNgoaiTroi" in SYSTEM_PROMPT


def test_prompt_still_requires_occ():
    assert '"occ" (BẮT BUỘC phải có giá trị)' in SYSTEM_PROMPT
