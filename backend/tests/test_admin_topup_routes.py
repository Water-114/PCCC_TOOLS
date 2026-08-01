"""Batch 5A, sub-bước 3 — test route admin xác nhận/từ chối yêu cầu nạp:
GET /api/admin/topup-requests, POST .../confirm, POST .../reject. Chỉ admin
gọi được (403 cho user thường), idempotent, danh sách mặc định chỉ hiện
'cho_xac_nhan' — đơn còn 'cho_chuyen_khoan' (user chưa bấm "Tôi đã chuyển
khoản") KHÔNG được admin thấy/thao tác được."""

from app.models import User
from app.services import credits, topup


def _make_admin(email="topupadmin2@pccc.local", password="matkhau123"):
    from app.extensions import db
    user = User(email=email, role="admin")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _register_and_login(client, email="topupuser2@pccc.local", password="matkhau123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    data = resp.get_json()
    return data["token"], data["user"]["id"]


def _login(client, email, password="matkhau123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.get_json()["token"]


def _make_pending_request(user_id):
    """Tao 1 yeu cau va dua thang toi 'cho_xac_nhan' (gia lap user da bam
    "Toi da chuyen khoan") - dung cho cac test tap trung vao hanh dong admin."""
    row = topup.create_topup_request(user_id)
    return topup.confirm_transfer(row.id, user_id)


# ---------------------------------------------------------------------------
# Quyen han - chi admin
# ---------------------------------------------------------------------------
def test_list_topup_requests_requires_admin(client):
    token, _ = _register_and_login(client, email="tur1@pccc.local")
    resp = client.get("/api/admin/topup-requests", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_confirm_requires_admin(client):
    token, user_id = _register_and_login(client, email="tur2@pccc.local")
    row = _make_pending_request(user_id)
    resp = client.post(
        f"/api/admin/topup-requests/{row.id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert credits.credit_balance(user_id) == 0  # khong cong gi ca


def test_reject_requires_admin(client):
    token, user_id = _register_and_login(client, email="tur3@pccc.local")
    row = _make_pending_request(user_id)
    resp = client.post(
        f"/api/admin/topup-requests/{row.id}/reject",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/admin/topup-requests
# ---------------------------------------------------------------------------
def test_list_default_only_shows_pending(client):
    admin = _make_admin()
    admin_token = _login(client, admin.email)
    _, user_id = _register_and_login(client, email="tur4@pccc.local")

    pending_row = _make_pending_request(user_id)
    confirmed_row = _make_pending_request(user_id)
    topup.confirm_topup_request(confirmed_row.id, admin.id)

    resp = client.get("/api/admin/topup-requests", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.get_json()["topup_requests"]]
    assert pending_row.id in ids
    assert confirmed_row.id not in ids


def test_list_default_excludes_draft_cho_chuyen_khoan(client):
    """Don vua tao (con 'cho_chuyen_khoan', user CHUA bam "Toi da chuyen
    khoan") khong duoc hien trong danh sach admin, ke ca khi xem status=all
    cung phai loc dung theo yeu cau — chi kiem tra default (cho_xac_nhan) o
    day, xem test rieng cho ?status=all ben duoi."""
    admin = _make_admin(email="topupadmin9@pccc.local")
    admin_token = _login(client, admin.email)
    _, user_id = _register_and_login(client, email="tur10@pccc.local")

    draft_row = topup.create_topup_request(user_id)  # con 'cho_chuyen_khoan'

    resp = client.get("/api/admin/topup-requests", headers={"Authorization": f"Bearer {admin_token}"})
    ids = [r["id"] for r in resp.get_json()["topup_requests"]]
    assert draft_row.id not in ids


def test_list_with_status_all_shows_everything_including_draft(client):
    admin = _make_admin(email="topupadmin3@pccc.local")
    admin_token = _login(client, admin.email)
    _, user_id = _register_and_login(client, email="tur5@pccc.local")

    draft_row = topup.create_topup_request(user_id)  # cho_chuyen_khoan
    pending_row = _make_pending_request(user_id)
    confirmed_row = _make_pending_request(user_id)
    topup.confirm_topup_request(confirmed_row.id, admin.id)

    resp = client.get(
        "/api/admin/topup-requests?status=all", headers={"Authorization": f"Bearer {admin_token}"}
    )
    ids = [r["id"] for r in resp.get_json()["topup_requests"]]
    assert draft_row.id in ids
    assert pending_row.id in ids
    assert confirmed_row.id in ids


# ---------------------------------------------------------------------------
# POST .../confirm
# ---------------------------------------------------------------------------
def test_admin_confirm_grants_exactly_5_and_updates_status(client):
    admin = _make_admin(email="topupadmin4@pccc.local")
    admin_token = _login(client, admin.email)
    _, user_id = _register_and_login(client, email="tur6@pccc.local")
    row = _make_pending_request(user_id)

    resp = client.post(
        f"/api/admin/topup-requests/{row.id}/confirm",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "da_xac_nhan"
    assert credits.credit_balance(user_id) == 5


def test_admin_confirm_twice_does_not_grant_twice(client):
    admin = _make_admin(email="topupadmin5@pccc.local")
    admin_token = _login(client, admin.email)
    _, user_id = _register_and_login(client, email="tur7@pccc.local")
    row = _make_pending_request(user_id)

    client.post(f"/api/admin/topup-requests/{row.id}/confirm", headers={"Authorization": f"Bearer {admin_token}"})
    assert credits.credit_balance(user_id) == 5

    resp2 = client.post(
        f"/api/admin/topup-requests/{row.id}/confirm",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp2.status_code == 200
    assert resp2.get_json()["status"] == "da_xac_nhan"
    assert credits.credit_balance(user_id) == 5  # khong cong lan 2


def test_admin_confirm_nonexistent_returns_404(client):
    admin = _make_admin(email="topupadmin6@pccc.local")
    admin_token = _login(client, admin.email)
    resp = client.post(
        "/api/admin/topup-requests/999999/confirm",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


def test_admin_confirm_still_draft_returns_400(client):
    """Don con 'cho_chuyen_khoan' (user chua bam "Toi da chuyen khoan") -
    admin KHONG the xac nhan truc tiep tu day."""
    admin = _make_admin(email="topupadmin10@pccc.local")
    admin_token = _login(client, admin.email)
    _, user_id = _register_and_login(client, email="tur11@pccc.local")
    row = topup.create_topup_request(user_id)  # cho_chuyen_khoan

    resp = client.post(
        f"/api/admin/topup-requests/{row.id}/confirm",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert credits.credit_balance(user_id) == 0


# ---------------------------------------------------------------------------
# POST .../reject
# ---------------------------------------------------------------------------
def test_admin_reject_grants_nothing(client):
    admin = _make_admin(email="topupadmin7@pccc.local")
    admin_token = _login(client, admin.email)
    _, user_id = _register_and_login(client, email="tur8@pccc.local")
    row = _make_pending_request(user_id)

    resp = client.post(
        f"/api/admin/topup-requests/{row.id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "tu_choi"
    assert credits.credit_balance(user_id) == 0


def test_admin_confirm_after_reject_returns_400(client):
    admin = _make_admin(email="topupadmin8@pccc.local")
    admin_token = _login(client, admin.email)
    _, user_id = _register_and_login(client, email="tur9@pccc.local")
    row = _make_pending_request(user_id)

    client.post(f"/api/admin/topup-requests/{row.id}/reject", headers={"Authorization": f"Bearer {admin_token}"})
    resp = client.post(
        f"/api/admin/topup-requests/{row.id}/confirm",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert credits.credit_balance(user_id) == 0
