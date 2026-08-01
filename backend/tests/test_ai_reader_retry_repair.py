"""Batch 4, sub-bước 1 — test cơ chế retry-repair đúng 1 lần khi AI trả JSON
không qua được validate Pydantic (app/services/ai_reader_common.py)."""

import json

import pytest

from app.services.ai_reader_common import AIReaderError, read_and_validate_drawing_json
from app.services.ai_schema import SchemaValidationError

VALID_JSON = json.dumps({
    "items": [{"id": 1, "noi_dung_thiet_ke": "ok", "ket_luan": "dat"}],
    "tong_ket": "ok",
    "kien_nghi": {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []},
    "so_hieu_ban_ve": "BV-01",
})

INVALID_JSON = json.dumps({
    "items": [{"id": 1, "noi_dung_thiet_ke": "ok", "ket_luan": "sai_enum"}],
    "tong_ket": "ok",
    "kien_nghi": {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []},
})


def _validate(data):
    from app.services.ai_schema import validate_reader_result
    return validate_reader_result(data, expected_ids={1})


class FakeProvider:
    name = "fake"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_with_document(self, system_prompt, content_block):
        self.calls.append(system_prompt)
        return self.responses.pop(0)


def test_first_attempt_valid_no_retry_needed():
    provider = FakeProvider([VALID_JSON])
    model = read_and_validate_drawing_json(b"fakebytes", "image/png", provider, "SYSTEM", _validate)
    assert model.items[0].id == 1
    assert len(provider.calls) == 1


def test_invalid_then_valid_retries_exactly_once_and_succeeds():
    provider = FakeProvider([INVALID_JSON, VALID_JSON])
    model = read_and_validate_drawing_json(b"fakebytes", "image/png", provider, "SYSTEM", _validate)
    assert model.so_hieu_ban_ve == "BV-01"
    assert len(provider.calls) == 2
    # Lan goi thu 2 (repair) phai keo dai system_prompt goc + thong bao loi cu the
    assert provider.calls[0] == "SYSTEM"
    assert provider.calls[1].startswith("SYSTEM")
    assert "SỬA LỖI" in provider.calls[1]


def test_invalid_twice_raises_clear_error_not_partial_result():
    provider = FakeProvider([INVALID_JSON, INVALID_JSON])
    with pytest.raises(AIReaderError):
        read_and_validate_drawing_json(b"fakebytes", "image/png", provider, "SYSTEM", _validate)
    assert len(provider.calls) == 2  # dung 1 lan retry, khong lap vo han


def test_validate_fn_receiving_schema_error_class():
    # dam bao validate_fn dung dung ngoai le SchemaValidationError de kich hoat retry
    calls = {"n": 0}

    def flaky_validate(data):
        calls["n"] += 1
        if calls["n"] == 1:
            raise SchemaValidationError("loi gia lap")
        return data

    provider = FakeProvider([VALID_JSON, VALID_JSON])
    result = read_and_validate_drawing_json(b"fakebytes", "image/png", provider, "SYSTEM", flaky_validate)
    assert result is not None
    assert calls["n"] == 2
