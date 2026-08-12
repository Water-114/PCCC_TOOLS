"""Số dư "Bộ hồ sơ" — không có cột số dư riêng, LUÔN tính từ SUM(delta) của
credit_ledger để tránh 2 nguồn dữ liệu lệch nhau.

Các loại giao dịch (CREDIT_REASON_*) đều đang có luồng thật tạo ra:
- EMAIL_VERIFICATION: cấp 1 Bộ hồ sơ dùng thử lúc xác thực email lần đầu
  (services/email_verification.py).
- USAGE_DEDUCTION: trừ 1 Bộ hồ sơ lúc mở phiên đọc bản vẽ (services/ho_so_session.py).
- REFUND_TECHNICAL_ERROR: hoàn lại lúc lỗi kỹ thuật (không phải lỗi người dùng).
- TOPUP_CONFIRMED: cộng 2 Bộ hồ sơ khi admin xác nhận đã nhận chuyển khoản
  100.000đ (services/topup.py).
- FEEDBACK_BONUS: cộng 1 Bộ hồ sơ mỗi khi đủ 5 góp ý hoàn thành
  (services/feedback_bonus.py).
- ADMIN_ADJUSTMENT: admin điều chỉnh thủ công (routes/admin.py).
"""

from ..extensions import db
from ..models import CreditLedger

CREDIT_REASON_EMAIL_VERIFICATION = "email_verification"
CREDIT_REASON_USAGE_DEDUCTION = "usage_deduction"
CREDIT_REASON_REFUND_TECHNICAL_ERROR = "refund_technical_error"
CREDIT_REASON_TOPUP_CONFIRMED = "topup_confirmed"
CREDIT_REASON_FEEDBACK_BONUS = "feedback_bonus"
CREDIT_REASON_ADMIN_ADJUSTMENT = "admin_adjustment"


def credit_balance(user_id: int) -> int:
    total = db.session.query(db.func.coalesce(db.func.sum(CreditLedger.delta), 0)).filter(
        CreditLedger.user_id == user_id
    ).scalar()
    return int(total)


def build_ledger_entry(user_id: int, delta: int, reason: str, note: str = None) -> CreditLedger:
    """Dựng 1 dòng ledger nhưng KHÔNG tự add/commit — dùng khi cần gộp chung 1
    transaction với thay đổi khác (vd đánh dấu email_verified_at cùng lúc cấp
    credit, xem services/email_verification.py) để tránh cửa sổ "đã đánh dấu
    nhưng chưa kịp cấp" nếu có lỗi giữa chừng."""
    current = credit_balance(user_id)
    return CreditLedger(user_id=user_id, delta=delta, reason=reason, balance_after=current + delta, note=note)


def grant_credits(user_id: int, delta: int, reason: str, note: str = None) -> CreditLedger:
    """Ghi 1 giao dịch độc lập, tự commit riêng — dùng cho các luồng không cần
    gộp transaction với thay đổi khác (vd admin xác nhận nạp tiền ở sub-bước sau)."""
    entry = build_ledger_entry(user_id, delta, reason, note)
    db.session.add(entry)
    db.session.commit()
    return entry
