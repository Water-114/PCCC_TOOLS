"""Test cho routes/admin.py — Batch 2: pagination + tránh N+1 cho /users và
/feedback, xác nhận used_today vẫn đúng khi tính gộp bằng 1 truy vấn group-by
thay vì gọi count_usage_today() riêng cho từng user."""

from app.extensions import db
from app.models import AIHO_API_NAME, Feedback, User, UsageLog
from app.services import credits


def _make_admin(email="admin@pccc.local", password="matkhau123"):
    user = User(email=email, role="admin")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _make_user(email, password="matkhau123"):
    user = User(email=email, role="user")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, email, password="matkhau123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.get_json()["token"]


def test_admin_users_requires_admin_role(app, client):
    with app.app_context():
        _make_user("thuong@pccc.local")
    token = _login(client, "thuong@pccc.local")
    resp = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_users_used_today_correct_across_multiple_users(app, client):
    """Xác nhận usage_counts group-by cho ra đúng used_today cho từng user,
    kể cả khi có nhiều user và chỉ một số user thực sự có lượt dùng hôm nay."""
    with app.app_context():
        admin = _make_admin()
        u1 = _make_user("u1@pccc.local")
        u2 = _make_user("u2@pccc.local")
        _make_user("u3@pccc.local")  # không có lượt dùng nào

        db.session.add(UsageLog(user_id=u1.id, api_name=AIHO_API_NAME, status="success"))
        db.session.add(UsageLog(user_id=u1.id, api_name=AIHO_API_NAME, status="success"))
        db.session.add(UsageLog(user_id=u2.id, api_name=AIHO_API_NAME, status="pending"))
        db.session.commit()
        admin_id, u1_id, u2_id = admin.id, u1.id, u2.id

    token = _login(client, "admin@pccc.local")
    resp = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    by_id = {u["id"]: u for u in data["users"]}
    assert by_id[u1_id]["used_today"] == 2
    assert by_id[u2_id]["used_today"] == 1
    assert by_id[admin_id]["used_today"] == 0


def test_admin_users_bo_ho_so_balance_and_usage_total(app, client):
    """Xác nhận bo_ho_so_con_lai (SUM delta, moi reason) va bo_ho_so_da_dung
    (COUNT dong reason=usage_deduction) tinh dung qua 2 truy van group-by,
    khong lech giua nhieu user."""
    with app.app_context():
        admin = _make_admin()
        u1 = _make_user("u1@pccc.local")
        u2 = _make_user("u2@pccc.local")
        _make_user("u3@pccc.local")  # chua co giao dich nao -> so du 0

        # u1: cap 2 (email_verification), dung 1 lan (usage_deduction) -> con 1
        credits.grant_credits(u1.id, 2, credits.CREDIT_REASON_EMAIL_VERIFICATION)
        credits.grant_credits(u1.id, -1, credits.CREDIT_REASON_USAGE_DEDUCTION)
        # u2: cap 5 (topup), dung 3 lan -> con 2, da dung (tong) = 3
        credits.grant_credits(u2.id, 5, credits.CREDIT_REASON_TOPUP_CONFIRMED)
        credits.grant_credits(u2.id, -1, credits.CREDIT_REASON_USAGE_DEDUCTION)
        credits.grant_credits(u2.id, -1, credits.CREDIT_REASON_USAGE_DEDUCTION)
        credits.grant_credits(u2.id, -1, credits.CREDIT_REASON_USAGE_DEDUCTION)
        admin_id, u1_id, u2_id = admin.id, u1.id, u2.id

    token = _login(client, "admin@pccc.local")
    resp = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    by_id = {u["id"]: u for u in data["users"]}

    assert by_id[u1_id]["bo_ho_so_con_lai"] == 1
    assert by_id[u1_id]["bo_ho_so_da_dung"] == 1

    assert by_id[u2_id]["bo_ho_so_con_lai"] == 2
    assert by_id[u2_id]["bo_ho_so_da_dung"] == 3

    assert by_id[admin_id]["bo_ho_so_con_lai"] == 0
    assert by_id[admin_id]["bo_ho_so_da_dung"] == 0


def test_admin_users_pagination_metadata(app, client):
    with app.app_context():
        _make_admin()
        for i in range(5):
            _make_user(f"page{i}@pccc.local")

    token = _login(client, "admin@pccc.local")
    resp = client.get("/api/admin/users?per_page=2&page=1", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["users"]) == 2
    assert data["per_page"] == 2
    assert data["total"] == 6  # admin + 5 user
    assert data["pages"] == 3


def test_admin_users_per_page_capped(app, client):
    with app.app_context():
        _make_admin()
    token = _login(client, "admin@pccc.local")
    resp = client.get("/api/admin/users?per_page=99999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["per_page"] == 300  # _MAX_PER_PAGE


def test_admin_feedback_returns_user_email_via_joinedload(app, client):
    with app.app_context():
        _make_admin()
        u1 = _make_user("fb1@pccc.local")
        db.session.add(Feedback(user_id=u1.id, feature="aiho_baochay", rating=5, comment="tot"))
        db.session.commit()

    token = _login(client, "admin@pccc.local")
    resp = client.get("/api/admin/feedback", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["feedback"][0]["user_email"] == "fb1@pccc.local"
    assert "total" in data and "pages" in data
