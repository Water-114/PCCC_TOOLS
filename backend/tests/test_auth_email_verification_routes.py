"""Batch 5A, sub-bước 1 — test route /api/auth/send-verification-email và
/api/auth/verify-email: cấp đúng 2 Bộ hồ sơ lần đầu, không cấp lại lần 2, token
hết hạn/không hợp lệ bị từ chối rõ ràng. KHÔNG gửi email thật (mock mailer.send_email)."""

from datetime import timedelta
from unittest.mock import patch

from app.extensions import db
from app.models import EmailVerificationToken
from app.services import credits
from app.services.email_verification import _utcnow


def _register_and_login(client, email="verifyroute@pccc.local", password="matkhau123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    data = resp.get_json()
    return data["token"], data["user"]["id"]


def test_send_verification_email_requires_login(client):
    resp = client.post("/api/auth/send-verification-email")
    assert resp.status_code == 401


def test_send_verification_email_success_calls_mailer_with_token_link(client):
    token, _ = _register_and_login(client)
    with patch("app.routes.auth.mailer.send_email") as mock_send:
        resp = client.post("/api/auth/send-verification-email", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    mock_send.assert_called_once()
    to_email, subject, body = mock_send.call_args[0]
    assert to_email == "verifyroute@pccc.local"
    assert "verify-email=" in body


def test_send_verification_email_already_verified_returns_409(client):
    token, user_id = _register_and_login(client, email="verifyroute2@pccc.local")
    with patch("app.routes.auth.mailer.send_email") as mock_send:
        client.post("/api/auth/send-verification-email", headers={"Authorization": f"Bearer {token}"})
        body = mock_send.call_args[0][2]
    raw_token = body.split("verify-email=")[1].split("\n")[0].strip()
    client.post("/api/auth/verify-email", json={"token": raw_token})  # xac thuc xong

    with patch("app.routes.auth.mailer.send_email") as mock_send2:
        resp = client.post("/api/auth/send-verification-email", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409
    mock_send2.assert_not_called()


def test_verify_email_full_flow_grants_1_credit(client):
    token, user_id = _register_and_login(client, email="verifyroute3@pccc.local")
    with patch("app.routes.auth.mailer.send_email") as mock_send:
        client.post("/api/auth/send-verification-email", headers={"Authorization": f"Bearer {token}"})
        body = mock_send.call_args[0][2]
    raw_token = body.split("verify-email=")[1].split("\n")[0].strip()

    resp = client.post("/api/auth/verify-email", json={"token": raw_token})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["credits_granted"] == 1
    assert credits.credit_balance(user_id) == 1


def test_verify_email_second_time_does_not_grant_credits_again(client):
    token, user_id = _register_and_login(client, email="verifyroute4@pccc.local")
    with patch("app.routes.auth.mailer.send_email") as mock_send:
        client.post("/api/auth/send-verification-email", headers={"Authorization": f"Bearer {token}"})
        body1 = mock_send.call_args[0][2]
    raw_token1 = body1.split("verify-email=")[1].split("\n")[0].strip()
    client.post("/api/auth/verify-email", json={"token": raw_token1})
    assert credits.credit_balance(user_id) == 1

    # Da xac thuc roi -> gui lai email bi chan 409, khong the lay token moi de xac thuc lan 2
    with patch("app.routes.auth.mailer.send_email"):
        resp = client.post("/api/auth/send-verification-email", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409
    assert credits.credit_balance(user_id) == 1  # van dung 1


def test_verify_email_missing_token_returns_400(client):
    resp = client.post("/api/auth/verify-email", json={})
    assert resp.status_code == 400


def test_verify_email_invalid_token_returns_400(client):
    resp = client.post("/api/auth/verify-email", json={"token": "khong-ton-tai"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_verify_email_expired_token_returns_400_with_clear_message(client):
    token, user_id = _register_and_login(client, email="verifyroute5@pccc.local")
    with patch("app.routes.auth.mailer.send_email") as mock_send:
        client.post("/api/auth/send-verification-email", headers={"Authorization": f"Bearer {token}"})
        body = mock_send.call_args[0][2]
    raw_token = body.split("verify-email=")[1].split("\n")[0].strip()

    entry = EmailVerificationToken.query.filter_by(user_id=user_id).first()
    entry.expires_at = _utcnow() - timedelta(hours=1)
    db.session.commit()

    resp = client.post("/api/auth/verify-email", json={"token": raw_token})
    assert resp.status_code == 400
    assert "hết hạn" in resp.get_json()["error"]


def test_verify_email_reused_token_returns_400(client):
    token, user_id = _register_and_login(client, email="verifyroute6@pccc.local")
    with patch("app.routes.auth.mailer.send_email") as mock_send:
        client.post("/api/auth/send-verification-email", headers={"Authorization": f"Bearer {token}"})
        body = mock_send.call_args[0][2]
    raw_token = body.split("verify-email=")[1].split("\n")[0].strip()

    resp1 = client.post("/api/auth/verify-email", json={"token": raw_token})
    assert resp1.status_code == 200

    resp2 = client.post("/api/auth/verify-email", json={"token": raw_token})
    assert resp2.status_code == 400
    assert "đã được sử dụng" in resp2.get_json()["error"]
