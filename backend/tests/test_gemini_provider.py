"""Batch 4, sub-bước 2 — test app/providers/gemini_provider.py sau khi chuyển
từ SDK legacy (google-generativeai, đã bị Google khai tử 2025-11-30) sang SDK
chính thức hiện tại (google-genai). Regression: hành vi output không đổi (vẫn
trả về JSON text để ai_reader_common parse), chỉ đổi cách gọi bên dưới. KHÔNG
gọi Gemini thật (mock google.genai.Client hoàn toàn)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from google.genai import errors

from app.providers.base import GenerationResult, ProviderNotConfigured
from app.providers.gemini_provider import GeminiProvider, _is_infra_error


def _fake_client_error(code):
    response = MagicMock()
    response.status_code = code
    return errors.ClientError(code, {"error": {"message": "x"}}, response=response)


def _fake_server_error(code=500):
    response = MagicMock()
    response.status_code = code
    return errors.ServerError(code, {"error": {"message": "x"}}, response=response)


def test_missing_api_key_raises_provider_not_configured_generate():
    provider = GeminiProvider(api_key="", model="gemini-2.0-flash")
    with pytest.raises(ProviderNotConfigured):
        provider.generate("hello")


def test_missing_api_key_raises_provider_not_configured_document():
    provider = GeminiProvider(api_key="", model="gemini-2.0-flash")
    with pytest.raises(ProviderNotConfigured):
        provider.generate_with_document("SYSTEM", {"type": "image", "source": {"media_type": "image/png", "data": "AA=="}})


@pytest.mark.parametrize("exc,expected", [
    (httpx.ConnectTimeout("timeout"), True),
    (httpx.ConnectError("connect failed"), True),
    (_fake_server_error(500), True),
    (_fake_server_error(503), True),
    (_fake_client_error(429), True),
    (_fake_client_error(400), False),
    (_fake_client_error(401), False),
    (ValueError("khong lien quan"), False),
])
def test_is_infra_error_classification(exc, expected):
    assert _is_infra_error(exc) is expected


def test_generate_with_document_uses_explicit_timeout_and_retry_options():
    provider = GeminiProvider(api_key="fake-key", model="gemini-2.0-flash")

    fake_response = MagicMock()
    fake_response.text = '{"ok": true}'
    fake_response.usage_metadata.prompt_token_count = 200
    fake_response.usage_metadata.candidates_token_count = 30

    with patch("google.genai.Client") as MockClient:
        MockClient.return_value.models.generate_content.return_value = fake_response
        result = provider.generate_with_document(
            "SYSTEM",
            {"type": "image", "source": {"media_type": "image/png", "data": "AA=="}},
        )

    assert MockClient.call_count == 1
    _, kwargs = MockClient.call_args
    assert kwargs["api_key"] == "fake-key"
    http_options = kwargs["http_options"]
    assert http_options.timeout == 300_000
    assert http_options.retry_options.attempts == 2

    assert isinstance(result, GenerationResult)
    assert result.text == '{"ok": true}'
    assert result.usage == {"input_tokens": 200, "output_tokens": 30}


def test_generate_with_document_passes_system_instruction_and_model():
    provider = GeminiProvider(api_key="fake-key", model="gemini-2.0-flash")

    fake_response = MagicMock()
    fake_response.text = "{}"
    fake_response.usage_metadata = None

    with patch("google.genai.Client") as MockClient:
        MockClient.return_value.models.generate_content.return_value = fake_response
        result = provider.generate_with_document(
            "MY SYSTEM PROMPT",
            {"type": "image", "source": {"media_type": "image/png", "data": "AA=="}},
        )

    _, call_kwargs = MockClient.return_value.models.generate_content.call_args
    assert call_kwargs["model"] == "gemini-2.0-flash"
    assert call_kwargs["config"].system_instruction == "MY SYSTEM PROMPT"
    assert result.usage is None  # provider khong tra duoc usage_metadata -> None, khong bia so


def test_generate_returns_plain_text_unlike_generate_with_document():
    provider = GeminiProvider(api_key="fake-key", model="gemini-2.0-flash")
    fake_response = MagicMock()
    fake_response.text = "plain text answer"

    with patch("google.genai.Client") as MockClient:
        MockClient.return_value.models.generate_content.return_value = fake_response
        result = provider.generate("hello")

    assert result == "plain text answer"  # generate() khong doi hop dong tra ve str thuong


def test_generate_with_document_propagates_infra_error_and_trips_breaker():
    from app.providers import resilience
    resilience.reset_all_breakers_for_tests()
    provider = GeminiProvider(api_key="fake-key", model="gemini-2.0-flash")

    with patch("google.genai.Client") as MockClient:
        MockClient.return_value.models.generate_content.side_effect = httpx.ConnectError("mat ket noi")
        for _ in range(3):
            with pytest.raises(httpx.ConnectError):
                provider.generate_with_document(
                    "SYSTEM", {"type": "image", "source": {"media_type": "image/png", "data": "AA=="}}
                )
        with pytest.raises(resilience.CircuitBreakerOpen):
            provider.generate_with_document(
                "SYSTEM", {"type": "image", "source": {"media_type": "image/png", "data": "AA=="}}
            )
    resilience.reset_all_breakers_for_tests()
