"""Batch 5A, sub-bước 5 — test trực tiếp app/services/feedback_bonus.py: đúng
mốc thứ 5/10 mới cộng, không cộng lặp cho góp ý thứ 6/7, giới hạn theo số
phiên Bộ hồ sơ THẬT đã dùng (closed_used), chỉ tính feature='aiho_bo_ho_so'."""

from app.extensions import db
from app.models import CreditLedger, Feedback, HoSoSession, User
from app.services import credits, ho_so_session
from app.services.feedback_bonus import FEEDBACK_BONUS_FEATURE, maybe_grant_feedback_bonus


def _make_user(email="fbbonus@pccc.local"):
    user = User(email=email, role="user")
    user.set_password("matkhau123")
    db.session.add(user)
    db.session.commit()
    return user


def _add_feedback(user, count, feature=FEEDBACK_BONUS_FEATURE):
    for _ in range(count):
        db.session.add(Feedback(user_id=user.id, feature=feature))
    db.session.commit()


def _make_real_sessions(user, count):
    """Mo + mark_success + dong dung `count` phien 'closed_used' that - can cap
    du Bo ho so truoc (moi phien tru 1)."""
    credits.grant_credits(user.id, count, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="test setup")
    for _ in range(count):
        session = ho_so_session.open_session(user.id)
        ho_so_session.mark_success(session)
        ho_so_session.close_session(user.id, session.id)


def _bonus_entries(user):
    return CreditLedger.query.filter_by(user_id=user.id, reason=credits.CREDIT_REASON_FEEDBACK_BONUS).all()


def test_no_bonus_before_5_eligible(app):
    user = _make_user()
    _add_feedback(user, 4)
    _make_real_sessions(user, 4)
    assert maybe_grant_feedback_bonus(user.id) is False
    assert _bonus_entries(user) == []


def test_bonus_granted_at_exactly_5(app):
    user = _make_user()
    _add_feedback(user, 5)
    _make_real_sessions(user, 5)
    balance_before = credits.credit_balance(user.id)
    assert maybe_grant_feedback_bonus(user.id) is True
    assert len(_bonus_entries(user)) == 1
    assert credits.credit_balance(user.id) == balance_before + 1


def test_no_double_grant_for_feedback_6_and_7(app):
    user = _make_user()
    _add_feedback(user, 5)
    _make_real_sessions(user, 7)
    assert maybe_grant_feedback_bonus(user.id) is True  # dat moc 5

    _add_feedback(user, 1)  # gop y thu 6
    assert maybe_grant_feedback_bonus(user.id) is False
    _add_feedback(user, 1)  # gop y thu 7
    assert maybe_grant_feedback_bonus(user.id) is False
    assert len(_bonus_entries(user)) == 1


def test_second_milestone_at_10(app):
    user = _make_user()
    _add_feedback(user, 5)
    _make_real_sessions(user, 10)
    assert maybe_grant_feedback_bonus(user.id) is True  # moc 5

    _add_feedback(user, 5)  # tong 10
    assert maybe_grant_feedback_bonus(user.id) is True  # moc 10
    assert len(_bonus_entries(user)) == 2


def test_capped_by_real_sessions_when_fewer_than_feedback(app):
    """Nhieu gop y (10) nhung it phien that (3) - eligible = min(10, 3) = 3, chua du moc 5."""
    user = _make_user()
    _add_feedback(user, 10)
    _make_real_sessions(user, 3)
    assert maybe_grant_feedback_bonus(user.id) is False
    assert _bonus_entries(user) == []


def test_capped_by_feedback_when_fewer_than_real_sessions(app):
    """Nhieu phien that (10) nhung it gop y (3) - eligible = min(3, 10) = 3, chua du moc 5."""
    user = _make_user()
    _add_feedback(user, 3)
    _make_real_sessions(user, 10)
    assert maybe_grant_feedback_bonus(user.id) is False
    assert _bonus_entries(user) == []


def test_demo_only_feedback_with_zero_real_sessions_never_grants(app):
    """Luong demo thuan (khong mo phien nao that) - du gop y bao nhieu lan cung
    khong bao gio du dieu kien (eligible luon = 0)."""
    user = _make_user()
    _add_feedback(user, 20)
    assert HoSoSession.query.filter_by(user_id=user.id).count() == 0
    assert maybe_grant_feedback_bonus(user.id) is False
    assert _bonus_entries(user) == []


def test_feedback_with_other_feature_value_not_counted(app):
    """Gop y voi feature khac 'aiho_bo_ho_so' (nhan cu, xem routes/feedback.py)
    khong duoc tinh vao so gop y hoan thanh."""
    user = _make_user()
    _add_feedback(user, 5, feature="aiho_baochay")
    _make_real_sessions(user, 5)
    assert maybe_grant_feedback_bonus(user.id) is False
    assert _bonus_entries(user) == []
