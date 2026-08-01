"""Batch 4, sub-bước 2 — test ghi log mỗi lần gọi AI (provider, model, phiên bản
system prompt, thời gian xử lý, usage) trong app/services/ai_reader_common.py.
Dùng logger chuẩn (không phải current_app.logger) — cố ý, vì ccnuoc_reader gọi
hàm này từ trong ThreadPoolExecutor, nơi app context của Flask không có sẵn."""

import json
import logging

from app.providers.base import GenerationResult
from app.providers.resilience import CircuitBreakerOpen
from app.services.ai_reader_common import (
    AIReaderError,
    read_drawing_json,
    system_prompt_version,
)

VALID_JSON = json.dumps({"ok": True})


class FakeProvider:
    name = "fake-provider"
    model = "fake-model-v1"

    def __init__(self, result_or_exc):
        self.result_or_exc = result_or_exc

    def generate_with_document(self, system_prompt, content_block):
        if isinstance(self.result_or_exc, Exception):
            raise self.result_or_exc
        return self.result_or_exc


def test_successful_call_logs_provider_model_version_elapsed_usage(caplog):
    provider = FakeProvider(GenerationResult(text=VALID_JSON, usage={"input_tokens": 10, "output_tokens": 5}))
    with caplog.at_level(logging.INFO, logger="app.services.ai_reader_common"):
        read_drawing_json(b"x", "image/png", provider, "SYSTEM PROMPT")

    assert len(caplog.records) == 1
    msg = caplog.records[0].getMessage()
    assert "provider=fake-provider" in msg
    assert "model=fake-model-v1" in msg
    assert "status=success" in msg
    assert "usage={'input_tokens': 10, 'output_tokens': 5}" in msg
    assert "elapsed_s=" in msg
    assert f"prompt_version={system_prompt_version('SYSTEM PROMPT')}" in msg


def test_json_error_still_logs_with_error_status(caplog):
    provider = FakeProvider(GenerationResult(text="khong phai json hop le {{{"))
    with caplog.at_level(logging.INFO, logger="app.services.ai_reader_common"):
        try:
            read_drawing_json(b"x", "image/png", provider, "SYSTEM PROMPT")
        except AIReaderError:
            pass

    assert len(caplog.records) == 1
    assert "status=json_error" in caplog.records[0].getMessage()


def test_infra_error_still_logs_with_error_status(caplog):
    provider = FakeProvider(ConnectionError("mat ket noi"))
    with caplog.at_level(logging.INFO, logger="app.services.ai_reader_common"):
        try:
            read_drawing_json(b"x", "image/png", provider, "SYSTEM PROMPT")
        except ConnectionError:
            pass

    assert len(caplog.records) == 1
    assert "status=error" in caplog.records[0].getMessage()


def test_circuit_breaker_open_logs_and_wraps_as_ai_reader_error(caplog):
    provider = FakeProvider(CircuitBreakerOpen("provider 'fake' dang loi lien tuc"))
    with caplog.at_level(logging.INFO, logger="app.services.ai_reader_common"):
        try:
            read_drawing_json(b"x", "image/png", provider, "SYSTEM PROMPT")
            assert False, "phai raise AIReaderError"
        except AIReaderError as exc:
            assert "dang loi lien tuc" in str(exc)

    assert len(caplog.records) == 1
    assert "status=circuit_open" in caplog.records[0].getMessage()


def test_explicit_prompt_version_used_instead_of_recomputing(caplog):
    provider = FakeProvider(GenerationResult(text=VALID_JSON))
    with caplog.at_level(logging.INFO, logger="app.services.ai_reader_common"):
        read_drawing_json(b"x", "image/png", provider, "SYSTEM PROMPT", prompt_version="custom-v7")

    assert "prompt_version=custom-v7" in caplog.records[0].getMessage()


def test_version_is_stable_hash_of_prompt_content():
    v1 = system_prompt_version("hello world")
    v2 = system_prompt_version("hello world")
    v3 = system_prompt_version("hello world!")
    assert v1 == v2
    assert v1 != v3
    assert len(v1) == 12
