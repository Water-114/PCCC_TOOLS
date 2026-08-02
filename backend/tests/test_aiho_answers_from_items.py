"""Test truc tiep routes/aiho.py::_answers_from_items() — anh xa ket_luan AI
(ai_schema.KetLuan) sang chuoi dien vao cot "Ket luan" cua MDC: "dat"->"Đạt",
"khong_ap_dung"->"" (rong, muc tuy chon khong thiet ke), con lai (chua_dat/
chua_the_hien)->"KN" (se duoc mdc_filler.fill_docx() to do, xem
test_mdc_filler.py)."""

from app.routes.aiho import _answers_from_items


def test_dat_maps_to_dat_text():
    out = _answers_from_items([{"id": 1, "noi_dung_thiet_ke": "x", "ket_luan": "dat"}])
    assert out[0]["ket_luan"] == "Đạt"


def test_khong_ap_dung_maps_to_empty_string():
    out = _answers_from_items([{"id": 1, "noi_dung_thiet_ke": "x", "ket_luan": "khong_ap_dung"}])
    assert out[0]["ket_luan"] == ""


def test_chua_dat_maps_to_kn():
    out = _answers_from_items([{"id": 1, "noi_dung_thiet_ke": "x", "ket_luan": "chua_dat"}])
    assert out[0]["ket_luan"] == "KN"


def test_chua_the_hien_maps_to_kn():
    out = _answers_from_items([{"id": 1, "noi_dung_thiet_ke": "x", "ket_luan": "chua_the_hien"}])
    assert out[0]["ket_luan"] == "KN"


def test_missing_or_unknown_ket_luan_defaults_to_kn():
    """Fail-safe: gia tri la hoac thieu -> KN (khong bao gio am tham thanh
    Dat/rong), tranh MDC hien sai neu co du lieu bat thuong lot qua Pydantic."""
    out = _answers_from_items([{"id": 1, "noi_dung_thiet_ke": "x", "ket_luan": None}])
    assert out[0]["ket_luan"] == "KN"


def test_invalid_id_skipped():
    out = _answers_from_items([{"id": "khong-phai-so", "noi_dung_thiet_ke": "x", "ket_luan": "dat"}])
    assert out == []


def test_preserves_id_and_noi_dung_thiet_ke():
    out = _answers_from_items([{"id": 7, "noi_dung_thiet_ke": "abc", "ket_luan": "dat"}])
    assert out[0]["id"] == 7
    assert out[0]["noi_dung_thiet_ke"] == "abc"
