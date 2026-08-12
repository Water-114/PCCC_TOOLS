"""Xác thực email: sinh token một lần có hạn sử dụng, xác nhận token cấp đúng
1 Bộ hồ sơ dùng thử cho tài khoản xác thực lần đầu (EMAIL_VERIFICATION_CREDITS
— giảm từ 2 xuống 1, xem commit "Giam Bo ho so mien phi dang ky tu 2 xuong 1").
Tài khoản đã đăng ký trước khi có tính năng này (chưa từng xác thực) KHÔNG tự
có Bộ hồ sơ — phải tự xác thực lại y như người dùng mới, không có logic
migrate/backfill riêng.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from ..extensions import db
from ..models import EmailVerificationToken
from . import credits

TOKEN_TTL_HOURS = 24
EMAIL_VERIFICATION_CREDITS = 1


class InvalidVerificationToken(Exception):
    pass


def _utcnow():
    return datetime.now(timezone.utc)


def _as_aware_utc(dt):
    # SQLite (dev/test) khong luu duoc tzinfo qua DateTime(timezone=True) - doc
    # lai luon la naive datetime, du luc ghi la aware (Postgres production thi
    # van giu dung tzinfo). Coi naive la UTC (dung 100% vi _utcnow() luon la
    # nguon duy nhat ghi cot nay) truoc khi so sanh, tranh TypeError "can't
    # compare offset-naive and offset-aware datetimes".
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_email_verification_token(user_id: int) -> str:
    """Sinh + lưu 1 token xác thực mới, trả về TOKEN THÔ (chỉ trả về đúng 1 lần
    ở đây để nhét vào link email — KHÔNG lưu bản rõ vào DB, chỉ lưu hash). Huỷ
    trước mọi token CHƯA dùng cũ của user này (bấm "gửi lại" thì link cũ hết
    hiệu lực ngay, tránh nhiều link cùng sống song song gây rối)."""
    EmailVerificationToken.query.filter_by(user_id=user_id, used_at=None).delete()

    raw_token = secrets.token_urlsafe(32)
    db.session.add(EmailVerificationToken(
        user_id=user_id,
        token_hash=_hash_token(raw_token),
        expires_at=_utcnow() + timedelta(hours=TOKEN_TTL_HOURS),
    ))
    db.session.commit()
    return raw_token


def consume_email_verification_token(raw_token: str):
    """Trả về (user, da_cap_moi: bool). Raise InvalidVerificationToken nếu token
    không tồn tại/đã dùng/hết hạn. Đánh dấu used_at NGAY khi token hợp lệ được
    tìm thấy — dù bước cấp credit sau đó có gì bất thường, token này cũng không
    thể tái sử dụng được nữa (cùng 1 transaction/commit với việc cấp credit)."""
    token_hash = _hash_token(raw_token)
    entry = EmailVerificationToken.query.filter_by(token_hash=token_hash).first()
    if entry is None:
        raise InvalidVerificationToken("Token xác thực không hợp lệ.")
    if entry.used_at is not None:
        raise InvalidVerificationToken("Token này đã được sử dụng — vui lòng yêu cầu gửi lại email xác thực nếu cần.")
    if _as_aware_utc(entry.expires_at) < _utcnow():
        raise InvalidVerificationToken("Token đã hết hạn — vui lòng yêu cầu gửi lại email xác thực.")

    entry.used_at = _utcnow()
    user = entry.user
    granted = False
    if user.email_verified_at is None:
        user.email_verified_at = _utcnow()
        granted = True
        db.session.add(credits.build_ledger_entry(
            user.id, EMAIL_VERIFICATION_CREDITS, credits.CREDIT_REASON_EMAIL_VERIFICATION,
            note="Xác thực email lần đầu",
        ))
    db.session.commit()
    return user, granted
