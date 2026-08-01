"""Batch 5A, sub-bước 1 — test app/services/email_verification.py: cấp đúng 2
Bộ hồ sơ lúc xác thực lần đầu, không cấp lại lần 2, token hết hạn/đã dùng bị
từ chối rõ ràng, tài khoản cũ (chưa từng xác thực) không tự có Bộ hồ sơ."""

from datetime import timedelta

import pytest

from app.extensions import db
from app.models import EmailVerificationToken, User
from app.services import credits, email_verification
from app.services.email_verification import (
    EMAIL_VERIFICATION_CREDITS,
    InvalidVerificationToken,
    _utcnow,
    consume_email_verification_token,
    create_email_verification_token,
)


def _make_user(app, email="u@pccc.local"):
    user = User(email=email, role="user")
    user.set_password("matkhau123")
    db.session.add(user)
    db.session.commit()
    return user


def test_verify_grants_exactly_2_credits_on_first_success(app):
    user = _make_user(app)
    token = create_email_verification_token(user.id)

    verified_user, granted = consume_email_verification_token(token)

    assert granted is True
    assert verified_user.id == user.id
    assert verified_user.email_verified_at is not None
    assert credits.credit_balance(user.id) == EMAIL_VERIFICATION_CREDITS == 2


def test_verifying_again_with_new_token_does_not_grant_credits_twice(app):
    user = _make_user(app)
    token1 = create_email_verification_token(user.id)
    consume_email_verification_token(token1)
    assert credits.credit_balance(user.id) == 2

    # Gia lap nguoi dung tu xac thuc lai lan 2 (token moi, hop le, thuoc dung user)
    token2 = create_email_verification_token(user.id)
    verified_user, granted = consume_email_verification_token(token2)

    assert granted is False
    assert credits.credit_balance(user.id) == 2  # khong cap them, van dung 2


def test_expired_token_rejected_clearly(app):
    user = _make_user(app)
    token = create_email_verification_token(user.id)

    entry = EmailVerificationToken.query.filter_by(user_id=user.id).first()
    entry.expires_at = _utcnow() - timedelta(hours=1)
    db.session.commit()

    with pytest.raises(InvalidVerificationToken, match="hết hạn"):
        consume_email_verification_token(token)
    assert credits.credit_balance(user.id) == 0  # khong cap credit khi tu choi


def test_used_token_cannot_be_reused(app):
    user = _make_user(app)
    token = create_email_verification_token(user.id)

    consume_email_verification_token(token)
    with pytest.raises(InvalidVerificationToken, match="đã được sử dụng"):
        consume_email_verification_token(token)

    assert credits.credit_balance(user.id) == 2  # van dung 2, khong cap them lan tai su dung


def test_garbage_token_rejected(app):
    with pytest.raises(InvalidVerificationToken, match="không hợp lệ"):
        consume_email_verification_token("token-khong-ton-tai-trong-db")


def test_pre_existing_account_has_no_credits_until_it_verifies_itself(app):
    """Gia lap tai khoan da dang ky truoc Batch 5A (theo he thong luot/ngay cu),
    CHUA tung xac thuc email — khong co logic migrate/backfill nao cap Bo ho so
    cho tai khoan nay tu dong."""
    old_user = _make_user(app, email="tai-khoan-cu@pccc.local")

    assert old_user.email_verified_at is None
    assert credits.credit_balance(old_user.id) == 0

    # Chi khi TU xac thuc (giong nguoi dung moi hoan toan) moi co Bo ho so
    token = create_email_verification_token(old_user.id)
    verified_user, granted = consume_email_verification_token(token)
    assert granted is True
    assert credits.credit_balance(old_user.id) == 2


def test_creating_new_token_invalidates_previous_unused_token(app):
    user = _make_user(app)
    old_token = create_email_verification_token(user.id)
    new_token = create_email_verification_token(user.id)  # gia lap bam "gui lai"

    assert old_token != new_token
    with pytest.raises(InvalidVerificationToken):
        consume_email_verification_token(old_token)

    # Token moi nhat van dung binh thuong
    verified_user, granted = consume_email_verification_token(new_token)
    assert granted is True


def test_token_hash_not_stored_in_plaintext(app):
    user = _make_user(app)
    token = create_email_verification_token(user.id)
    entry = EmailVerificationToken.query.filter_by(user_id=user.id).first()
    assert entry.token_hash != token
    assert len(entry.token_hash) == 64  # sha256 hex digest
