"""Batch 5A, sub-bước 3 — test route /api/topup/request và /api/topup/ledger
(phía user, cần đăng nhập). Route admin xác nhận/từ chối xem
test_admin_topup_routes.py."""

from app.models import TopupRequest
from app.services import credits


def _register_and_login(client, email="topuproute@pccc.local", password="matkhau123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    data = resp.get_json()
    return data["token"], data["user"]["id"]


def _configure_bank(app):
    app.config["BANK_ACCOUNT_NUMBER"] = "test-acc-no"
    app.config["BANK_ACCOUNT_NAME"] = "test-acc-name"
    app.config["BANK_NAME"] = "test-bank"
    app.config["BANK_QR_URL"] = "https://example-test-only.local/qr.png"


# ---------------------------------------------------------------------------
# POST /api/topup/request
# ---------------------------------------------------------------------------
def test_create_request_requires_login(client):
    resp = client.post("/api/topup/request")
    assert resp.status_code == 401


def test_create_request_returns_503_when_bank_not_configured(app, client):
    app.config["BANK_ACCOUNT_NUMBER"] = ""
    app.config["BANK_ACCOUNT_NAME"] = ""
    app.config["BANK_NAME"] = ""
    token, user_id = _register_and_login(client)
    resp = client.post("/api/topup/request", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503
    assert "error" in resp.get_json()
    assert TopupRequest.query.filter_by(user_id=user_id).count() == 0  # khong tao du khi bank chua cau hinh


def test_create_request_success_returns_bank_info_and_reference_code(app, client):
    _configure_bank(app)
    token, user_id = _register_and_login(client, email="topuproute2@pccc.local")
    resp = client.post("/api/topup/request", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["reference_code"].startswith("BHS-")
    assert data["amount_vnd"] == 100000
    assert data["credits_to_grant"] == 2
    assert data["status"] == "cho_chuyen_khoan"  # nhap - chua vao hang doi admin
    assert data["bank"]["account_number"] == "test-acc-no"
    assert data["bank"]["bank_name"] == "test-bank"


# ---------------------------------------------------------------------------
# POST /api/topup/<id>/confirm-transfer ("Tôi đã chuyển khoản")
# ---------------------------------------------------------------------------
def test_confirm_transfer_requires_login(client):
    resp = client.post("/api/topup/1/confirm-transfer")
    assert resp.status_code == 401


def test_confirm_transfer_moves_to_cho_xac_nhan_and_grants_nothing(app, client):
    _configure_bank(app)
    token, user_id = _register_and_login(client, email="topuproute5@pccc.local")
    create_resp = client.post("/api/topup/request", headers={"Authorization": f"Bearer {token}"})
    request_id = create_resp.get_json()["id"]

    resp = client.post(
        f"/api/topup/{request_id}/confirm-transfer", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "cho_xac_nhan"
    assert credits.credit_balance(user_id) == 0  # chi doi trang thai, khong tu cong Bo ho so


def test_confirm_transfer_other_users_request_returns_404(app, client):
    _configure_bank(app)
    token1, _ = _register_and_login(client, email="topuproute6a@pccc.local")
    create_resp = client.post("/api/topup/request", headers={"Authorization": f"Bearer {token1}"})
    request_id = create_resp.get_json()["id"]

    token2, _ = _register_and_login(client, email="topuproute6b@pccc.local")
    resp = client.post(
        f"/api/topup/{request_id}/confirm-transfer", headers={"Authorization": f"Bearer {token2}"}
    )
    assert resp.status_code == 404


def test_confirm_transfer_nonexistent_returns_404(client):
    token, _ = _register_and_login(client, email="topuproute7@pccc.local")
    resp = client.post("/api/topup/999999/confirm-transfer", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/topup/ledger
# ---------------------------------------------------------------------------
def test_ledger_requires_login(client):
    resp = client.get("/api/topup/ledger")
    assert resp.status_code == 401


def test_ledger_returns_balance_and_history_newest_first(app, client):
    token, user_id = _register_and_login(client, email="topuproute3@pccc.local")
    credits.grant_credits(user_id, 2, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="dot 1")
    credits.grant_credits(user_id, -1, credits.CREDIT_REASON_USAGE_DEDUCTION, note="dot 2")
    credits.grant_credits(user_id, 5, credits.CREDIT_REASON_TOPUP_CONFIRMED, note="dot 3")

    resp = client.get("/api/topup/ledger", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["bo_ho_so_con_lai"] == 6
    notes_in_order = [e["note"] for e in data["ledger"]]
    assert notes_in_order == ["dot 3", "dot 2", "dot 1"]  # moi nhat truoc


def test_ledger_only_shows_own_entries(app, client):
    token1, user1_id = _register_and_login(client, email="topuproute4a@pccc.local")
    token2, user2_id = _register_and_login(client, email="topuproute4b@pccc.local")
    credits.grant_credits(user1_id, 2, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="cua user1")
    credits.grant_credits(user2_id, 3, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="cua user2")

    resp = client.get("/api/topup/ledger", headers={"Authorization": f"Bearer {token1}"})
    data = resp.get_json()
    assert data["bo_ho_so_con_lai"] == 2
    assert all(e["note"] == "cua user1" for e in data["ledger"])
