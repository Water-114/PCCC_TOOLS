"""Batch 4, sub-bước 2 — test circuit breaker đơn giản dùng chung cho mọi AI
provider (app/providers/resilience.py). Không liên quan tới retry-repair schema
(ai_reader_common.py) hay retry backoff nội bộ từng SDK — đây chỉ là lớp ngoài
cùng: sau N lần lỗi hạ tầng liên tiếp, tạm từ chối gọi thêm."""

import pytest

from app.providers import resilience


@pytest.fixture(autouse=True)
def _reset_breakers():
    resilience.reset_all_breakers_for_tests()
    yield
    resilience.reset_all_breakers_for_tests()


def _infra_error(exc):
    return isinstance(exc, ConnectionError)


def test_success_returns_value_and_resets_counter():
    result = resilience.guarded_call("p1", _infra_error, lambda: 42)
    assert result == 42


def test_non_infra_error_never_opens_breaker():
    def boom():
        raise ValueError("loi noi dung, khong phai ha tang")

    for _ in range(10):
        with pytest.raises(ValueError):
            resilience.guarded_call("p2", _infra_error, boom)
    # Van goi duoc binh thuong - khong bi CircuitBreakerOpen chan
    assert resilience.guarded_call("p2", _infra_error, lambda: "ok") == "ok"


def test_infra_errors_open_breaker_after_threshold():
    def boom():
        raise ConnectionError("mat ket noi")

    for _ in range(3):  # nguong mac dinh la 3
        with pytest.raises(ConnectionError):
            resilience.guarded_call("p3", _infra_error, boom)

    with pytest.raises(resilience.CircuitBreakerOpen):
        resilience.guarded_call("p3", _infra_error, lambda: "khong bao gio toi day")


def test_breaker_is_independent_per_provider_name():
    def boom():
        raise ConnectionError("mat ket noi")

    for _ in range(3):
        with pytest.raises(ConnectionError):
            resilience.guarded_call("providerA", _infra_error, boom)
    with pytest.raises(resilience.CircuitBreakerOpen):
        resilience.guarded_call("providerA", _infra_error, lambda: "x")

    # providerB hoan toan doc lap, chua tung loi -> van goi binh thuong
    assert resilience.guarded_call("providerB", _infra_error, lambda: "ok") == "ok"


def test_success_after_failures_resets_consecutive_count(monkeypatch):
    def boom():
        raise ConnectionError("mat ket noi")

    for _ in range(2):  # chua du nguong 3
        with pytest.raises(ConnectionError):
            resilience.guarded_call("p4", _infra_error, boom)

    assert resilience.guarded_call("p4", _infra_error, lambda: "ok") == "ok"  # thanh cong -> reset ve 0

    for _ in range(2):  # lai chi 2 loi lien tiep sau khi reset -> chua du mo breaker
        with pytest.raises(ConnectionError):
            resilience.guarded_call("p4", _infra_error, boom)
    assert resilience.guarded_call("p4", _infra_error, lambda: "van goi duoc") == "van goi duoc"


def test_breaker_half_opens_and_recovers_after_cooldown(monkeypatch):
    fake_now = [1000.0]
    monkeypatch.setattr(resilience.time, "monotonic", lambda: fake_now[0])

    def boom():
        raise ConnectionError("mat ket noi")

    for _ in range(3):
        with pytest.raises(ConnectionError):
            resilience.guarded_call("p5", _infra_error, boom)
    with pytest.raises(resilience.CircuitBreakerOpen):
        resilience.guarded_call("p5", _infra_error, lambda: "x")

    fake_now[0] += 61.0  # vuot qua cooldown mac dinh 60s
    # "Tham do" (half-open) thanh cong -> breaker dong lai
    assert resilience.guarded_call("p5", _infra_error, lambda: "hoi phuc roi") == "hoi phuc roi"
    assert resilience.guarded_call("p5", _infra_error, lambda: "van ok") == "van ok"


def test_circuit_breaker_open_message_mentions_provider_name():
    def boom():
        raise ConnectionError("mat ket noi")

    for _ in range(3):
        with pytest.raises(ConnectionError):
            resilience.guarded_call("gemini", _infra_error, boom)

    with pytest.raises(resilience.CircuitBreakerOpen, match="gemini"):
        resilience.guarded_call("gemini", _infra_error, lambda: "x")
