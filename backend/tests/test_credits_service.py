"""Batch 5A, sub-bước 1 — test app/services/credits.py: số dư luôn tính từ
SUM(delta) của ledger, build_ledger_entry không tự commit, grant_credits commit
riêng và tính đúng balance_after."""

from app.extensions import db
from app.models import User
from app.services import credits


def _make_user(email="credituser@pccc.local"):
    user = User(email=email, role="user")
    user.set_password("matkhau123")
    db.session.add(user)
    db.session.commit()
    return user


def test_balance_zero_for_user_with_no_ledger_entries(app):
    user = _make_user()
    assert credits.credit_balance(user.id) == 0


def test_grant_credits_updates_balance_and_returns_entry(app):
    user = _make_user()
    entry = credits.grant_credits(user.id, 2, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="test")
    assert entry.delta == 2
    assert entry.balance_after == 2
    assert entry.note == "test"
    assert credits.credit_balance(user.id) == 2


def test_balance_sums_positive_and_negative_deltas(app):
    user = _make_user()
    credits.grant_credits(user.id, 2, credits.CREDIT_REASON_EMAIL_VERIFICATION)
    credits.grant_credits(user.id, -1, credits.CREDIT_REASON_USAGE_DEDUCTION)
    credits.grant_credits(user.id, 5, credits.CREDIT_REASON_TOPUP_CONFIRMED)
    assert credits.credit_balance(user.id) == 6


def test_build_ledger_entry_does_not_commit_or_add(app):
    user = _make_user()
    entry = credits.build_ledger_entry(user.id, 2, credits.CREDIT_REASON_EMAIL_VERIFICATION)
    assert entry.balance_after == 2
    # Chua add/commit - so du van la 0 cho toi khi ai do tu them vao session
    assert credits.credit_balance(user.id) == 0


def test_balance_is_per_user_independent(app):
    u1 = _make_user("cu1@pccc.local")
    u2 = _make_user("cu2@pccc.local")
    credits.grant_credits(u1.id, 2, credits.CREDIT_REASON_EMAIL_VERIFICATION)
    assert credits.credit_balance(u1.id) == 2
    assert credits.credit_balance(u2.id) == 0
