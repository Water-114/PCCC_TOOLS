def test_login_rate_limited_after_threshold(client):
    """auth.py gioi han POST /api/auth/login o 10/phut/IP — goi qua nguong
    phai nhan 429, khong con la vector brute-force khong gioi han."""
    payload = {"email": "khongtontai@pccc.local", "password": "sai"}
    statuses = [client.post("/api/auth/login", json=payload).status_code for _ in range(11)]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


def test_register_rate_limited_after_threshold(client):
    """auth.py gioi han POST /api/auth/register o 5/gio/IP."""
    statuses = []
    for i in range(6):
        resp = client.post("/api/auth/register", json={
            "email": f"user{i}@pccc.local", "password": "matkhau123",
        })
        statuses.append(resp.status_code)
    assert statuses[:5] == [200] * 5
    assert statuses[5] == 429


def test_feedback_rate_limited_after_threshold(client):
    statuses = []
    for _ in range(11):
        resp = client.post("/api/feedback", json={"feature": "aiho_baochay"})
        statuses.append(resp.status_code)
    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429
