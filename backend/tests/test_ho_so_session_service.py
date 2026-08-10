"""Batch 5A, sub-bước 2 — test trực tiếp app/services/ho_so_session.py (không
qua HTTP route): mở phiên trừ đúng 1 Bộ hồ sơ dù gọi nhiều hạng mục, hết Bộ hồ
sơ bị chặn, vượt 5 file/7 form bị chặn, hoàn đúng khi lỗi kỹ thuật giữa phiên,
phiên bị bỏ quên (timeout) tự đóng đúng khi mở phiên mới."""

from datetime import timedelta

import pytest
from sqlalchemy.orm.attributes import set_committed_value

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
# reserve_slot - chung minh het "lost update" khi doc-roi-ghi (ban cu), bang
# cach mo phong dung kich ban gay loi that o production: "request A" tang
# truoc va commit that su len 5/5, "request B" thi VAN CON GIU 1 GIA TRI PYTHON
# CU cho object HoSoSession no dang giu (doc/refresh TU TRUOC khi A kip chay -
# hoan toan hop ly voi 2 request Flask khac nhau, moi request co bien `session`
# rieng trong bo nho, tai thoi diem code cua no bat dau chay khong the biet
# request kia vua commit gi).
#
# VE VIEC KHONG DUNG threading that: engine test dung SQLite ":memory:" voi
# StaticPool (1 connection sqlite3 DUY NHAT dung chung cho CA APP - xac nhan
# rieng: type(db.engine.pool).__name__ == "StaticPool") - nhieu THREAD he dieu
# hanh cung dung 1 connection sqlite3 nhu vay se nem loi KY THUAT CUA DRIVER
# ("cannot start a transaction within a transaction", da tu kiem chung bang
# script rieng) thay vi mo phong dung 1 race dang co that (nhieu KET NOI doc
# lap nhu tren Postgres production, moi request 1 connection rieng tu pool) -
# dung threading o day se flaky vi 1 ly do KHAC han cai dang can kiem tra.
#
# Thay vao do, test nay chung minh THANG vao dung tinh chat can co: sau khi
# sua, quyet dinh chan/cho cua reserve_slot() KHONG doc `session.files_used`
# (bien Python cua object duoc truyen vao) de quyet dinh nua - no chi dung
# `session.id` de dung trong WHERE, con dieu kien "con cho hay khong" nam
# trong chinh cau SQL, doc gia tri COT tai thoi diem UPDATE THUC THI. Vi vay,
# du object `session` dang giu 1 gia tri .files_used SAI/CU trong bo nho
# (mo phong bang cach tu gan lai, KHONG commit), ket qua van phai DUNG theo
# DB - day chinh la co che giup an toan tren Postgres that (moi ket noi/
# transaction doc lap, UPDATE luon doc dung gia tri cot moi nhat).
# ---------------------------------------------------------------------------
def test_reserve_slot_uses_current_db_value_not_stale_python_object(app):
    user = _make_user()
    session = ho_so_session.open_session(user.id)
    session.files_used = 3  # con dung 2 slot truoc khi cham gioi han 5
    db.session.commit()

    # "Request A" chay truoc, thanh cong: dung not 2 slot con lai -> DB THAT SU
    # da len dung 5/5 (xac nhan qua object `session` - reserve_slot() da
    # refresh() no o cuoi ham).
    ho_so_session.reserve_slot(session, 2, 0)
    assert session.files_used == 5

    # Mo phong "request B": 1 bien Python khac (thuc te se la 1 object HoSoSession
    # rieng cua request do) van dang GIU GIA TRI CU no tung doc TRUOC khi A kip
    # chay/commit - dung set_committed_value() (API cong khai cua SQLAlchemy,
    # danh rieng cho truong hop nay: "set gia tri KHONG tao lich su thay doi" -
    # xem docs sqlalchemy.orm.attributes) de mo phong DUNG 1 attribute doc duoc
    # tu truoc, KHONG bien no thanh 1 thay doi "dirty" (neu chi gan bang `=`
    # binh thuong, autoflush se tu ghi de gia tri gia nay xuong DB THAT truoc
    # khi UPDATE nguyen tu kip chay, lam sai lech chinh cai dang kiem tra).
    set_committed_value(session, "files_used", 3)

    with pytest.raises(ho_so_session.SessionCapExceeded, match="5 file"):
        ho_so_session.reserve_slot(session, 1, 0)

    # Neu con doc-roi-ghi (ban cu): code se tin session.files_used dang la 3,
    # tinh 3+1=4 <= 5 nen KHONG chan, roi GHI DE DB tu 5 xuong 4 - mat dung
    # 1 slot A vua tang that su (lost update, dem SAI so voi thuc te da dung).
    # Xac nhan gia tri THAT trong DB (doc lai tu dau, khong qua object cu) van
    # dung la 5 - khong bi ghi de xuong 4 (mat) hay len 6 (vuot gioi han).
    final = HoSoSession.query.get(session.id)
    assert final.files_used == 5


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
