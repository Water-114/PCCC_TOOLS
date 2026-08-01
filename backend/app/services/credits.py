"""Số dư "Bộ hồ sơ" (Batch 5A) — không có cột số dư riêng, LUÔN tính từ
SUM(delta) của credit_ledger để tránh 2 nguồn dữ liệu lệch nhau.

Sub-bước 1 chỉ tạo được giao dịch loại CREDIT_REASON_EMAIL_VERIFICATION (cấp 2
lúc xác thực email lần đầu) — các loại còn lại khai báo sẵn hằng số để dùng
đúng tên khi làm các sub-bước sau (trừ lúc dùng AI, hoàn lúc lỗi kỹ thuật, cộng
lúc admin xác nhận nạp tiền, thưởng góp ý đủ 5 Bộ hồ sơ) — CHƯA có luồng nào
tạo ra giao dịch các loại đó ở sub-bước này.
"""

from ..extensions import db
from ..models import CreditLedger

CREDIT_REASON_EMAIL_VERIFICATION = "email_verification"
CREDIT_REASON_USAGE_DEDUCTION = "usage_deduction"
CREDIT_REASON_REFUND_TECHNICAL_ERROR = "refund_technical_error"
CREDIT_REASON_TOPUP_CONFIRMED = "topup_confirmed"
CREDIT_REASON_FEEDBACK_BONUS = "feedback_bonus"


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
