"""Circuit breaker đơn giản, dùng chung cho mọi AI provider — tránh dội liên
tục vào một provider đang lỗi hạ tầng liên tiếp (mất kết nối/timeout/5xx).

KHÁC với 2 lớp retry khác đã có trong hệ thống:
- Retry-repair (ai_reader_common.read_and_validate_drawing_json): retry khi
  JSON AI trả về sai schema — lỗi NỘI DUNG, không phải lỗi hạ tầng.
- Retry backoff cho lỗi mạng tạm thời: cấu hình NGAY TRONG từng SDK provider
  (anthropic Anthropic(max_retries=...), google genai HttpRetryOptions) vì mỗi
  SDK tự phân loại lỗi nào đáng retry (429/5xx/connection) theo cách riêng —
  không có 1 danh sách exception dùng chung được cho cả 2 SDK khác nhau.

Circuit breaker ở đây là lớp NGOÀI CÙNG: sau khi 1 lần gọi provider (đã tự
retry nội bộ theo SDK) vẫn thất bại vì lỗi hạ tầng, tính vào chuỗi thất bại
liên tiếp của provider đó; đủ ngưỡng thì tạm từ chối gọi thêm (fail-fast,
không tốn thời gian chờ timeout lần nữa) trong một khoảng nghỉ ngắn.

Trạng thái lưu trong bộ nhớ tiến trình (per-process, per-provider-name) — đơn
giản, đủ dùng cho quy mô hiện tại (không dùng Redis); mỗi worker gunicorn có
breaker riêng, không chia sẻ giữa các worker.
"""

import threading
import time


class CircuitBreakerOpen(Exception):
    """Circuit breaker đang MỞ (provider vừa lỗi hạ tầng liên tiếp gần đây) —
    tạm thời từ chối gọi thêm để không dội liên tục vào provider đang lỗi."""


class _CircuitBreaker:
    def __init__(self, failure_threshold: int, cooldown_seconds: float):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._opened_at = None

    def before_call(self, provider_name: str):
        with self._lock:
            if self._opened_at is None:
                return
            elapsed = time.monotonic() - self._opened_at
            if elapsed < self.cooldown_seconds:
                remaining = max(1, round(self.cooldown_seconds - elapsed))
                raise CircuitBreakerOpen(
                    f"Provider '{provider_name}' vừa lỗi kết nối {self._consecutive_failures} lần liên tiếp — "
                    f"tạm ngừng gọi thêm khoảng {remaining} giây để tránh dội liên tục, vui lòng thử lại sau."
                )
            # Het thoi gian nghi - cho 1 lan goi "tham do" (half-open) di qua;
            # neu van loi, record_failure() se mo lai ngay ben duoi.
            self._opened_at = None

    def record_success(self):
        with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None

    def record_failure(self):
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.failure_threshold and self._opened_at is None:
                self._opened_at = time.monotonic()


_DEFAULT_FAILURE_THRESHOLD = 3
_DEFAULT_COOLDOWN_SECONDS = 60.0

_breakers_lock = threading.Lock()
_breakers: dict[str, _CircuitBreaker] = {}


def _breaker_for(provider_name: str) -> _CircuitBreaker:
    with _breakers_lock:
        breaker = _breakers.get(provider_name)
        if breaker is None:
            breaker = _CircuitBreaker(_DEFAULT_FAILURE_THRESHOLD, _DEFAULT_COOLDOWN_SECONDS)
            _breakers[provider_name] = breaker
        return breaker


def guarded_call(provider_name: str, is_infra_error, fn):
    """Gọi fn() (không tham số — provider tự đóng gói qua closure). Trước khi
    gọi: kiểm tra breaker của provider_name, từ chối ngay (CircuitBreakerOpen)
    nếu đang "mở". Sau khi gọi: thành công -> reset breaker; thất bại VÀ
    is_infra_error(exc) đúng -> tính vào chuỗi thất bại liên tiếp (có thể mở
    breaker); các lỗi khác (vd JSON sai, provider chưa cấu hình) không ảnh
    hưởng breaker — không phải dấu hiệu "provider đang lỗi hạ tầng"."""
    breaker = _breaker_for(provider_name)
    breaker.before_call(provider_name)
    try:
        result = fn()
    except Exception as exc:
        if is_infra_error(exc):
            breaker.record_failure()
        raise
    else:
        breaker.record_success()
        return result


def reset_all_breakers_for_tests():
    """Chỉ dùng trong test — xoá sạch trạng thái breaker giữa các test case."""
    with _breakers_lock:
        _breakers.clear()
