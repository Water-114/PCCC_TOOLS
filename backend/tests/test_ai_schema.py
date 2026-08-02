"""Batch 4, sub-bước 1 — golden test cho app/services/ai_schema.py: validate
cấu trúc JSON AI đọc bản vẽ trả về (đủ id đúng, enum ket_luan hợp lệ, giới hạn
độ dài noi_dung_thiet_ke, mặc định so_hieu_ban_ve)."""

import pytest

from app.services.ai_schema import (
    MAX_NOI_DUNG_LEN,
    KHONG_XAC_DINH_SO_HIEU,
    ChuaChayTuDongReaderResult,
    ReaderResult,
    SchemaValidationError,
    validate_reader_result,
)


def _valid_data(**overrides):
    data = {
        "items": [
            {"id": 1, "noi_dung_thiet_ke": "Có bố trí đầu báo khói.", "ket_luan": "dat"},
            {"id": 2, "noi_dung_thiet_ke": "Chưa thể hiện trên bản vẽ cung cấp", "ket_luan": "chua_the_hien"},
        ],
        "tong_ket": "Tổng kết ngắn.",
        "kien_nghi": {
            "I_chua_the_hien": ["Thể hiện rõ ... (Căn cứ Điều 1)"],
            "II_chua_thong_nhat": [],
            "III_chua_phu_hop": [],
            "IV_de_xuat_bo_sung": [],
        },
        "so_hieu_ban_ve": "BV-01",
    }
    data.update(overrides)
    return data


def test_valid_data_passes_and_returns_model():
    model = validate_reader_result(_valid_data(), expected_ids={1, 2})
    assert isinstance(model, ReaderResult)
    assert {item.id for item in model.items} == {1, 2}
    assert model.so_hieu_ban_ve == "BV-01"


def test_missing_id_rejected():
    with pytest.raises(SchemaValidationError, match="thiếu id"):
        validate_reader_result(_valid_data(), expected_ids={1, 2, 3})


def test_extra_id_rejected():
    with pytest.raises(SchemaValidationError, match="không tồn tại"):
        validate_reader_result(_valid_data(), expected_ids={1})


def test_invalid_ket_luan_enum_rejected():
    data = _valid_data()
    data["items"][0]["ket_luan"] = "khong_hop_le"
    with pytest.raises(SchemaValidationError):
        validate_reader_result(data, expected_ids={1, 2})


def test_noi_dung_thiet_ke_over_max_length_rejected():
    data = _valid_data()
    data["items"][0]["noi_dung_thiet_ke"] = "x" * (MAX_NOI_DUNG_LEN + 1)
    with pytest.raises(SchemaValidationError):
        validate_reader_result(data, expected_ids={1, 2})


def test_noi_dung_thiet_ke_at_max_length_accepted():
    data = _valid_data()
    data["items"][0]["noi_dung_thiet_ke"] = "x" * MAX_NOI_DUNG_LEN
    validate_reader_result(data, expected_ids={1, 2})  # khong raise


def test_missing_items_field_rejected():
    data = _valid_data()
    del data["items"]
    with pytest.raises(SchemaValidationError):
        validate_reader_result(data, expected_ids={1, 2})


def test_non_dict_input_rejected():
    with pytest.raises(SchemaValidationError):
        validate_reader_result(["not", "a", "dict"], expected_ids={1, 2})


def test_so_hieu_ban_ve_defaults_when_absent():
    data = _valid_data()
    del data["so_hieu_ban_ve"]
    model = validate_reader_result(data, expected_ids={1, 2})
    assert model.so_hieu_ban_ve == KHONG_XAC_DINH_SO_HIEU


def test_kien_nghi_missing_group_defaults_to_empty_list():
    data = _valid_data()
    del data["kien_nghi"]["IV_de_xuat_bo_sung"]
    model = validate_reader_result(data, expected_ids={1, 2})
    assert model.kien_nghi.IV_de_xuat_bo_sung == []


# ---------------------------------------------------------------------------
# ChuaChayTuDongReaderResult (B6, ccnuoc_reader.py) — chi dao nghiep vu cua
# owner: AI phai tu xac dinh cong trinh co thiet ke he sprinkler/drencher hay
# khong truoc khi doi chieu. Field bat buoc, KHONG co default.
# ---------------------------------------------------------------------------
def test_chua_chay_tu_dong_requires_co_thiet_ke_field():
    data = _valid_data()  # khong co "co_thiet_ke_tu_dong"
    with pytest.raises(SchemaValidationError):
        validate_reader_result(data, expected_ids={1, 2}, model_cls=ChuaChayTuDongReaderResult)


def test_chua_chay_tu_dong_accepts_true():
    data = _valid_data(co_thiet_ke_tu_dong=True)
    model = validate_reader_result(data, expected_ids={1, 2}, model_cls=ChuaChayTuDongReaderResult)
    assert model.co_thiet_ke_tu_dong is True


def test_chua_chay_tu_dong_accepts_false():
    data = _valid_data(co_thiet_ke_tu_dong=False)
    model = validate_reader_result(data, expected_ids={1, 2}, model_cls=ChuaChayTuDongReaderResult)
    assert model.co_thiet_ke_tu_dong is False
