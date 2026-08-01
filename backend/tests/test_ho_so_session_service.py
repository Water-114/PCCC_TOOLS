"""Batch 5A, sub-bước 2 — test trực tiếp app/services/ho_so_session.py (không
qua HTTP route): mở phiên trừ đúng 1 Bộ hồ sơ dù gọi nhiều hạng mục, hết Bộ hồ
sơ bị chặn, vượt 5 file/7 form bị chặn, hoàn đúng khi lỗi kỹ thuật giữa phiên,
phiên bị bỏ quên (timeout) tự đóng đúng khi mở phiên mới."""

from datetime import timedelta

import pytest

from app.extensions import db
from app.models import HoSoSession, User
from app.services import credits, ho_so_session


def _make_user(email="hoso@pccc.local", amount=5):
    user = User(email=email, role="user")
    user.set_password("matkhau123")
    db.session.add(user)
    db.session.commit()
    if amount:
        credits.grant_credits(user.id, amount, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="test setup")
    return user


# ---------------------------------------------------------------------------
# open_session
# ---------------------------------------------------------------------------
def test_open_session_deducts_exactly_1_credit(app):
    user = _make_user()
    session = ho_so_session.open_session(user.id)
    assert session.status == "open"
    assert credits.credit_balance(user.id) == 4


def test_open_session_multiple_hang_muc_calls_still_only_1_deduction(app):
    """Mo dung 1 phien, roi goi reserve_slot() nhieu lan (mo phong nhieu hang
    muc trong CUNG 1 phien) - van chi tru DUNG 1 Bo ho so tu luc mo, khong tru
    them theo tung lan goi hang muc."""
    user = _make_user()
    session = ho_so_session.open_session(user.id)
    ho_so_session.reserve_slot(session, 1, 1)  # bao chay
    ho_so_session.mark_success(session)
    ho_so_session.reserve_slot(session, 1, 1)  # dien PCCC
    ho_so_session.mark_success(session)
    ho_so_session.reserve_slot(session, 1, 3)  # chua chay nuoc (3 form)
    ho_so_session.mark_success(session)

    assert credits.credit_balance(user.id) == 4  # van chi tru 1, khong phai 3
    assert session.files_used == 3
    assert session.forms_used == 5
    assert session.success_count == 3


def test_open_session_idempotent_when_already_open(app):
    user = _make_user()
    session1 = ho_so_session.open_session(user.id)
    session2 = ho_so_session.open_session(user.id)  # gia lap double-click/2 tab
    assert session1.id == session2.id
    assert credits.credit_balance(user.id) == 4  # chi tru 1 lan


def test_open_session_raises_insufficient_credits_when_balance_zero(app):
    user = _make_user(amount=0)
    with pytest.raises(ho_so_session.InsufficientCredits):
        ho_so_session.open_session(user.id)
    assert HoSoSession.query.filter_by(user_id=user.id).count() == 0


def test_open_session_auto_closes_stale_session_and_opens_new_one(app):
    user = _make_user()
    old_session = ho_so_session.open_session(user.id)
    old_session.opened_at = ho_so_session._utcnow() - timedelta(minutes=ho_so_session.SESSION_TIMEOUT_MINUTES + 1)
    db.session.commit()

    new_session = ho_so_session.open_session(user.id)
    assert new_session.id != old_session.id

    db.session.refresh(old_session)
    assert old_session.status == "closed_refunded"  # khong co lan thanh cong nao -> hoan
    # Tru 1 luc mo phien cu, hoan 1 luc lazy-dong, tru 1 luc mo phien moi = -1 tu 5
    assert credits.credit_balance(user.id) == 4


# ---------------------------------------------------------------------------
# get_open_session_for_user
# ---------------------------------------------------------------------------
def test_get_open_session_for_user_not_found_for_wrong_owner(app):
    user1 = _make_user(email="u1@pccc.local")
    user2 = _make_user(email="u2@pccc.local")
    session = ho_so_session.open_session(user1.id)
    with pytest.raises(ho_so_session.SessionNotFound):
        ho_so_session.get_open_session_for_user(user2.id, session.id)


def test_get_open_session_for_user_not_found_for_nonexistent_id(app):
    user = _make_user()
    with pytest.raises(ho_so_session.SessionNotFound):
        ho_so_session.get_open_session_for_user(user.id, 999999)


def test_get_open_session_for_user_not_open_after_close(app):
    user = _make_user()
    session = ho_so_session.open_session(user.id)
    ho_so_session.close_session(user.id, session.id)
    with pytest.raises(ho_so_session.SessionNotOpen):
        ho_so_session.get_open_session_for_user(user.id, session.id)


def test_get_open_session_for_user_stale_session_auto_closes_and_raises(app):
    user = _make_user()
    session = ho_so_session.open_session(user.id)
    session.opened_at = ho_so_session._utcnow() - timedelta(minutes=ho_so_session.SESSION_TIMEOUT_MINUTES + 1)
    db.session.commit()

    with pytest.raises(ho_so_session.SessionNotOpen, match="hết hạn"):
        ho_so_session.get_open_session_for_user(user.id, session.id)

    db.session.refresh(session)
    assert session.status == "closed_refunded"
    assert credits.credit_balance(user.id) == 5  # hoan lai vi khong co lan thanh cong nao


# ---------------------------------------------------------------------------
# reserve_slot - gioi han 5 file / 7 form
# ---------------------------------------------------------------------------
def test_reserve_slot_within_caps_increments_counters(app):
    user = _make_user()
    session = ho_so_session.open_session(user.id)
    ho_so_session.reserve_slot(session, 1, 3)
    assert session.files_used == 1
    assert session.forms_used == 3


def test_reserve_slot_exceeding_file_cap_raises_and_does_not_increment(app):
    user = _make_user()
    session = ho_so_session.open_session(user.id)
    session.files_used = 5  # da dat gioi han
    db.session.commit()
    with pytest.raises(ho_so_session.SessionCapExceeded, match="5 file"):
        ho_so_session.reserve_slot(session, 1, 1)
    assert session.files_used == 5  # khong tang them


def test_reserve_slot_exceeding_form_cap_raises_and_does_not_increment(app):
    user = _make_user()
    session = ho_so_session.open_session(user.id)
    session.forms_used = 6
    db.session.commit()
    with pytest.raises(ho_so_session.SessionCapExceeded, match="7 form"):
        ho_so_session.reserve_slot(session, 1, 3)  # 6+3=9 > 7
    assert session.forms_used == 6


def test_reserve_slot_exactly_at_cap_boundary_succeeds(app):
    user = _make_user()
    session = ho_so_session.open_session(user.id)
    session.files_used = 4
    session.forms_used = 6
    db.session.commit()
    ho_so_session.reserve_slot(session, 1, 1)  # dung bang 5 file, 7 form
    assert session.files_used == 5
    assert session.forms_used == 7


# ---------------------------------------------------------------------------
# close_session - hoan dung khi loi ky thuat, giu nguyen khi co thanh cong
# ---------------------------------------------------------------------------
def test_close_session_with_no_success_refunds(app):
    user = _make_user()
    session = ho_so_session.open_session(user.id)
    assert credits.credit_balance(user.id) == 4
    closed = ho_so_session.close_session(user.id, session.id)
    assert closed.status == "closed_refunded"
    assert credits.credit_balance(user.id) == 5


def test_close_session_with_success_keeps_deduction(app):
    user = _make_user()
    session = ho_so_session.open_session(user.id)
    ho_so_session.mark_success(session)
    closed = ho_so_session.close_session(user.id, session.id)
    assert closed.status == "closed_used"
    assert credits.credit_balance(user.id) == 4  # khong hoan


def test_close_session_is_idempotent(app):
    user = _make_user()
    session = ho_so_session.open_session(user.id)
    ho_so_session.close_session(user.id, session.id)
    assert credits.credit_balance(user.id) == 5

    closed_again = ho_so_session.close_session(user.id, session.id)
    assert closed_again.status == "closed_refunded"
    assert credits.credit_balance(user.id) == 5  # khong hoan lan 2


def test_close_session_not_found_for_wrong_owner(app):
    user1 = _make_user(email="c1@pccc.local")
    user2 = _make_user(email="c2@pccc.local")
    session = ho_so_session.open_session(user1.id)
    with pytest.raises(ho_so_session.SessionNotFound):
        ho_so_session.close_session(user2.id, session.id)
