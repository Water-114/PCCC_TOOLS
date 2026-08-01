def test_register_rejects_invalid_email(client):
    resp = client.post("/api/auth/register", json={"email": "not-an-email", "password": "matkhau123"})
    assert resp.status_code == 400


def test_register_rejects_short_password(client):
    resp = client.post("/api/auth/register", json={"email": "user1@pccc.local", "password": "123"})
    assert resp.status_code == 400


def test_register_then_login_happy_path(client):
    resp = client.post("/api/auth/register", json={"email": "user2@pccc.local", "password": "matkhau123"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert data["user"]["email"] == "user2@pccc.local"

    resp2 = client.post("/api/auth/login", json={"email": "user2@pccc.local", "password": "matkhau123"})
    assert resp2.status_code == 200
    token = resp2.get_json()["token"]

    resp3 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp3.status_code == 200
    assert resp3.get_json()["user"]["email"] == "user2@pccc.local"


def test_register_duplicate_email_conflict(client):
    client.post("/api/auth/register", json={"email": "user3@pccc.local", "password": "matkhau123"})
    resp = client.post("/api/auth/register", json={"email": "user3@pccc.local", "password": "matkhau456"})
    assert resp.status_code == 409


def test_login_wrong_password_rejected(client):
    client.post("/api/auth/register", json={"email": "user4@pccc.local", "password": "matkhau123"})
    resp = client.post("/api/auth/login", json={"email": "user4@pccc.local", "password": "saipassword"})
    assert resp.status_code == 401
