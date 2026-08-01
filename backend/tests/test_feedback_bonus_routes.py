"""Batch 5A, sub-bước 5 — test end-to-end qua POST /api/feedback: response tra
ve dung 'bonus_granted', chi cong o dung gop y thu 5 (khong phai thu 1-4),
khong cong lap o thu 6, va gop y an danh khong lam sap route."""

from app.services import credits, ho_so_session


def _register_and_login(client, email="fbbonusroute@pccc.local", password="matkhau123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    data = resp.get_json()
    return data["token"], data["user"]["id"]


def _make_real_sessions(user_id, count):
    credits.grant_credits(user_id, count, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="test setup")
    for _ in range(count):
        session = ho_so_session.open_session(user_id)
        ho_so_session.mark_success(session)
        ho_so_session.close_session(user_id, session.id)


def test_bonus_granted_exactly_at_5th_feedback_not_before(app, client):
    token, user_id = _register_and_login(client)
    _make_real_sessions(user_id, 5)
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(1, 5):
        resp = client.post("/api/feedback", json={"feature": "aiho_bo_ho_so", "rating": 5}, headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["bonus_granted"] is False, f"feedback #{i} khong duoc cong som"

    resp5 = client.post("/api/feedback", json={"feature": "aiho_bo_ho_so", "rating": 5}, headers=headers)
    assert resp5.status_code == 200
    assert resp5.get_json()["bonus_granted"] is True

    balance = credits.credit_balance(user_id)
    assert balance == 1  # het 5 luc mo 5 phien that, cong lai 1 tu thuong


def test_bonus_not_double_granted_for_feedback_6(app, client):
    token, user_id = _register_and_login(client, email="fbbonusroute2@pccc.local")
    _make_real_sessions(user_id, 6)
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(5):
        client.post("/api/feedback", json={"feature": "aiho_bo_ho_so", "rating": 5}, headers=headers)

    resp6 = client.post("/api/feedback", json={"feature": "aiho_bo_ho_so", "rating": 5}, headers=headers)
    assert resp6.get_json()["bonus_granted"] is False


def test_anonymous_feedback_never_grants_bonus_and_does_not_error(client):
    resp = client.post("/api/feedback", json={"feature": "aiho_bo_ho_so", "rating": 5})
    assert resp.status_code == 200
    assert resp.get_json()["bonus_granted"] is False


def test_logged_in_user_without_enough_real_sessions_does_not_get_bonus(app, client):
    """Da dang nhap, gop y du 5 lan nhung KHONG mo phien that nao (vd chi dung
    luong demo) - khong bao gio du dieu kien."""
    token, user_id = _register_and_login(client, email="fbbonusroute3@pccc.local")
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(5):
        resp = client.post("/api/feedback", json={"feature": "aiho_bo_ho_so", "rating": 5}, headers=headers)
        assert resp.get_json()["bonus_granted"] is False
