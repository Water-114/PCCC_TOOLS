"""Batch 4, sub-bước 2 — test app/providers/claude_provider.py: timeout/retry
tường minh, phân loại lỗi hạ tầng cho circuit breaker, usage được surface ra
GenerationResult. KHÔNG gọi Claude thật (mock anthropic.Anthropic hoàn toàn)."""

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from app.providers.base import GenerationResult, ProviderNotConfigured
from app.providers.claude_provider import ClaudeProvider, _is_infra_error


def test_missing_api_key_raises_provider_not_configured():
    provider = ClaudeProvider(api_key="", model="claude-sonnet-5")
    with pytest.raises(ProviderNotConfigured):
        provider.generate_with_document("SYSTEM", {"type": "image", "source": {}})


@pytest.mark.parametrize("exc,expected", [
    (anthropic.APIConnectionError(request=MagicMock()), True),
    (anthropic.RateLimitError("rate limited", response=MagicMock(status_code=429), body=None), True),
    (anthropic.InternalServerError("server error", response=MagicMock(status_code=500), body=None), True),
    (anthropic.BadRequestError("bad request", response=MagicMock(status_code=400), body=None), False),
    (anthropic.AuthenticationError("auth", response=MagicMock(status_code=401), body=None), False),
    (ValueError("khong lien quan"), False),
])
def test_is_infra_error_classification(exc, expected):
    assert _is_infra_error(exc) is expected


def test_generate_with_document_uses_explicit_timeout_and_max_retries():
    provider = ClaudeProvider(api_key="fake-key", model="claude-sonnet-5")

    fake_message = MagicMock()
    fake_message.content = [MagicMock(type="text", text='{"ok": true}')]
    fake_message.usage = MagicMock(input_tokens=100, output_tokens=20)

    fake_stream_ctx = MagicMock()
    fake_stream_ctx.__enter__.return_value.get_final_message.return_value = fake_message

    with patch("anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.stream.return_value = fake_stream_ctx
        result = provider.generate_with_document("SYSTEM", {"type": "image", "source": {}})

    MockAnthropic.assert_called_once_with(api_key="fake-key", timeout=870.0, max_retries=1)
    assert isinstance(result, GenerationResult)
    assert result.text == '{"ok": true}'
    assert result.usage == {"input_tokens": 100, "output_tokens": 20}


def test_generate_with_document_propagates_infra_error_and_trips_breaker():
    from app.providers import resilience
    resilience.reset_all_breakers_for_tests()
    provider = ClaudeProvider(api_key="fake-key", model="claude-sonnet-5")

    with patch("anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.stream.side_effect = anthropic.APIConnectionError(request=MagicMock())
        for _ in range(3):
            with pytest.raises(anthropic.APIConnectionError):
                provider.generate_with_document("SYSTEM", {"type": "image", "source": {}})
        with pytest.raises(resilience.CircuitBreakerOpen):
            provider.generate_with_document("SYSTEM", {"type": "image", "source": {}})
    resilience.reset_all_breakers_for_tests()
