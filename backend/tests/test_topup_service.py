"""Batch 5A, sub-bước 3 — test trực tiếp app/services/topup.py: state machine
3 trạng thái (cho_chuyen_khoan -> cho_xac_nhan -> da_xac_nhan/tu_choi), mã
giao dịch unique, xác nhận cộng đúng 5, idempotent, từ chối không cộng gì,
chặn chuyển trạng thái không hợp lệ."""

import pytest

from app.extensions import db
from app.models import User
from app.services import credits, topup


def _make_user(email="topup@pccc.local"):
    user = User(email=email, role="user")
    user.set_password("matkhau123")
    db.session.add(user)
    db.session.commit()
    return user


def _make_admin(email="topupadmin@pccc.local"):
    user = User(email=email, role="admin")
    user.set_password("matkhau123")
    db.session.add(user)
    db.session.commit()
    return user


def _make_pending_request(user_id):
    """Tao 1 yeu cau va dua thang toi 'cho_xac_nhan' (gia lap user da bam
    "Toi da chuyen khoan") - dung cho cac test tap trung vao hanh dong admin."""
    row = topup.create_topup_request(user_id)
    return topup.confirm_transfer(row.id, user_id)


# ---------------------------------------------------------------------------
# bank_transfer_info
# ---------------------------------------------------------------------------
def test_bank_transfer_info_raises_when_not_configured(app):
    with app.app_context():
        app.config["BANK_ACCOUNT_NUMBER"] = ""
        app.config["BANK_ACCOUNT_NAME"] = ""
        app.config["BANK_NAME"] = ""
        with pytest.raises(topup.BankInfoNotConfigured):
            topup.bank_transfer_info()


def test_bank_transfer_info_raises_when_partially_configured(app):
    with app.app_context():
        app.config["BANK_ACCOUNT_NUMBER"] = "x"
        app.config["BANK_ACCOUNT_NAME"] = ""
        app.config["BANK_NAME"] = "x"
        with pytest.raises(topup.BankInfoNotConfigured):
            topup.bank_transfer_info()


def test_bank_transfer_info_returns_dict_when_configured(app):
    with app.app_context():
        app.config["BANK_ACCOUNT_NUMBER"] = "test-acc-no"
        app.config["BANK_ACCOUNT_NAME"] = "test-acc-name"
        app.config["BANK_NAME"] = "test-bank"
        app.config["BANK_QR_URL"] = ""
        info = topup.bank_transfer_info()
    assert info == {
        "account_number": "test-acc-no",
        "account_name": "test-acc-name",
        "bank_name": "test-bank",
        "qr_url": None,
    }


# ---------------------------------------------------------------------------
# create_topup_request - trang thai khoi tao 'cho_chuyen_khoan' (nhap)
# ---------------------------------------------------------------------------
def test_create_topup_request_defaults_to_cho_chuyen_khoan(app):
    user = _make_user()
    row = topup.create_topup_request(user.id)
    assert row.status == "cho_chuyen_khoan"
    assert row.amount_vnd == 100000
    assert row.credits_to_grant == 5
    assert row.reference_code.startswith("BHS-")


def test_create_topup_request_reference_codes_are_unique(app):
    user = _make_user()
    codes = {topup.create_topup_request(user.id).reference_code for _ in range(10)}
    assert len(codes) == 10


# ---------------------------------------------------------------------------
# confirm_transfer (user: nut "Toi da chuyen khoan")
# ---------------------------------------------------------------------------
def test_confirm_transfer_moves_to_cho_xac_nhan(app):
    user = _make_user()
    row = topup.create_topup_request(user.id)
    confirmed = topup.confirm_transfer(row.id, user.id)
    assert confirmed.status == "cho_xac_nhan"


def test_confirm_transfer_does_not_grant_credits(app):
    user = _make_user()
    row = topup.create_topup_request(user.id)
    topup.confirm_transfer(row.id, user.id)
    assert credits.credit_balance(user.id) == 0  # chi doi trang thai, khong cong gi


def test_confirm_transfer_wrong_owner_raises_not_found(app):
    user1 = _make_user(email="ct1@pccc.local")
    user2 = _make_user(email="ct2@pccc.local")
    row = topup.create_topup_request(user1.id)
    with pytest.raises(topup.TopupRequestNotFound):
        topup.confirm_transfer(row.id, user2.id)


def test_confirm_transfer_is_idempotent_after_already_confirmed(app):
    user = _make_user()
    row = topup.create_topup_request(user.id)
    topup.confirm_transfer(row.id, user.id)
    again = topup.confirm_transfer(row.id, user.id)
    assert again.status == "cho_xac_nhan"


def test_confirm_transfer_is_idempotent_after_admin_already_decided(app):
    """Goi lai confirm_transfer sau khi admin da xu ly xong khong duoc lam gi
    (khong lui trang thai ve cho_xac_nhan)."""
    user = _make_user()
    admin = _make_admin()
    row = _make_pending_request(user.id)
    topup.confirm_topup_request(row.id, admin.id)

    again = topup.confirm_transfer(row.id, user.id)
    assert again.status == "da_xac_nhan"  # khong bi doi nguoc lai


def test_confirm_transfer_nonexistent_raises_not_found(app):
    user = _make_user()
    with pytest.raises(topup.TopupRequestNotFound):
        topup.confirm_transfer(999999, user.id)


# ---------------------------------------------------------------------------
# confirm_topup_request (admin) - chi hop le tu 'cho_xac_nhan'
# ---------------------------------------------------------------------------
def test_confirm_grants_exactly_5_credits(app):
    user = _make_user()
    admin = _make_admin()
    row = _make_pending_request(user.id)
    assert credits.credit_balance(user.id) == 0

    confirmed = topup.confirm_topup_request(row.id, admin.id)
    assert confirmed.status == "da_xac_nhan"
    assert confirmed.reviewed_by_admin_id == admin.id
    assert confirmed.reviewed_at is not None
    assert credits.credit_balance(user.id) == 5


def test_confirm_twice_does_not_grant_twice(app):
    user = _make_user()
    admin = _make_admin()
    row = _make_pending_request(user.id)

    topup.confirm_topup_request(row.id, admin.id)
    assert credits.credit_balance(user.id) == 5

    again = topup.confirm_topup_request(row.id, admin.id)
    assert again.status == "da_xac_nhan"
    assert credits.credit_balance(user.id) == 5  # khong cong lan 2


def test_confirm_still_in_cho_chuyen_khoan_raises(app):
    """User CHUA bam 'Toi da chuyen khoan' - admin khong the xac nhan."""
    user = _make_user()
    admin = _make_admin()
    row = topup.create_topup_request(user.id)  # con o cho_chuyen_khoan

    with pytest.raises(topup.InvalidTopupStatusTransition):
        topup.confirm_topup_request(row.id, admin.id)
    assert credits.credit_balance(user.id) == 0


def test_confirm_a_rejected_request_raises(app):
    user = _make_user()
    admin = _make_admin()
    row = _make_pending_request(user.id)
    topup.reject_topup_request(row.id, admin.id)

    with pytest.raises(topup.InvalidTopupStatusTransition):
        topup.confirm_topup_request(row.id, admin.id)
    assert credits.credit_balance(user.id) == 0


def test_confirm_nonexistent_request_raises_not_found(app):
    admin = _make_admin()
    with pytest.raises(topup.TopupRequestNotFound):
        topup.confirm_topup_request(999999, admin.id)


# ---------------------------------------------------------------------------
# reject_topup_request (admin) - chi hop le tu 'cho_xac_nhan'
# ---------------------------------------------------------------------------
def test_reject_grants_nothing(app):
    user = _make_user()
    admin = _make_admin()
    row = _make_pending_request(user.id)

    rejected = topup.reject_topup_request(row.id, admin.id)
    assert rejected.status == "tu_choi"
    assert rejected.reviewed_by_admin_id == admin.id
    assert credits.credit_balance(user.id) == 0


def test_reject_twice_is_idempotent(app):
    user = _make_user()
    admin = _make_admin()
    row = _make_pending_request(user.id)

    topup.reject_topup_request(row.id, admin.id)
    again = topup.reject_topup_request(row.id, admin.id)
    assert again.status == "tu_choi"
    assert credits.credit_balance(user.id) == 0


def test_reject_still_in_cho_chuyen_khoan_raises(app):
    user = _make_user()
    admin = _make_admin()
    row = topup.create_topup_request(user.id)  # con o cho_chuyen_khoan

    with pytest.raises(topup.InvalidTopupStatusTransition):
        topup.reject_topup_request(row.id, admin.id)


def test_reject_a_confirmed_request_raises(app):
    user = _make_user()
    admin = _make_admin()
    row = _make_pending_request(user.id)
    topup.confirm_topup_request(row.id, admin.id)

    with pytest.raises(topup.InvalidTopupStatusTransition):
        topup.reject_topup_request(row.id, admin.id)
    assert credits.credit_balance(user.id) == 5  # van giu nguyen, khong bi dao nguoc


def test_reject_nonexistent_request_raises_not_found(app):
    admin = _make_admin()
    with pytest.raises(topup.TopupRequestNotFound):
        topup.reject_topup_request(999999, admin.id)
