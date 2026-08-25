"""Quy mô Giai đoạn 1, Phần A.1 — khoá lại nội dung system prompt của
scan_quymo_reader.py ("Lượt 0", quét NHẸ, không chạy đủ checklist kỹ thuật
như quymo_reader.py). Không gọi AI thật."""

from app.services.scan_quymo_reader import SYSTEM_PROMPT


def test_prompt_asks_for_all_scan_fields_including_new_d2_fields():
    for key in ("occ", "floors", "totalArea", "hFire", "chieuCaoKeHang", "coBeXangDauNgoaiTroi"):
        assert f'"{key}"' in SYSTEM_PROMPT


def test_prompt_explicitly_allows_tim_thay_false():
    assert "tim_thay" in SYSTEM_PROMPT
    assert '"tim_thay": false' in SYSTEM_PROMPT


def test_prompt_does_not_run_full_checklist_like_baochay():
    """Luot 0 KHONG duoc co "BƯỚC 2" soan kien nghi nhu cac reader chinh -
    chi trich field, khong danh gia dat/chua_dat."""
    assert "kiến nghị" not in SYSTEM_PROMPT.lower()
    assert "ket_luan" not in SYSTEM_PROMPT.lower().replace("_", "")


def test_prompt_forbids_guessing_occ():
    assert "không tự đoán" in SYSTEM_PROMPT.lower() or "không suy đoán" in SYSTEM_PROMPT.lower()
