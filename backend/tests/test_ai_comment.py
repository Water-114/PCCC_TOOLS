"""Test cho /api/ai/comment — Batch 1 thêm auth+quota (trước đây hoàn toàn mở).

QUAN TRỌNG: không được để bất kỳ test nào ở đây thực sự gọi tới Claude/Gemini
thật (tốn phí) — chỉ test các nhánh chặn sớm (401/429, không chạm tới
provider.generate()) và 1 nhánh thành công có mock provider giả lập hoàn toàn.
"""

from unittest.mock import patch


def _register_and_login(client, email="aicmt@pccc.local", password="matkhau123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.get_json()["token"]


def test_comment_requires_auth(client):
    resp = client.post("/api/ai/comment", json={"result": {"tong": {"the_tich_m3": 10}}})
    assert resp.status_code == 401


def test_comment_success_with_mocked_provider(client):
    """Provider hoàn toàn giả lập — không gọi mạng/API thật."""
    token = _register_and_login(client)

    class FakeProvider:
        name = "fake"
        def generate(self, prompt):
            return "Diễn giải giả lập, không gọi AI thật."

    with patch("app.routes.ai.get_provider", return_value=FakeProvider()):
        resp = client.post(
            "/api/ai/comment",
            json={"result": {"tong": {"the_tich_m3": 10}}},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["comment"] == "Diễn giải giả lập, không gọi AI thật."
    assert data["quota"]["used_today"] == 1


def test_comment_quota_exhausted_returns_429(client):
    token = _register_and_login(client, email="aicmt2@pccc.local")

    class FakeProvider:
        name = "fake"
        def generate(self, prompt):
            return "ok"

    with patch("app.routes.ai.get_provider", return_value=FakeProvider()):
        for _ in range(5):  # AIHO_DAILY_QUOTA mac dinh = 5
            client.post(
                "/api/ai/comment",
                json={"result": {"tong": {"the_tich_m3": 10}}},
                headers={"Authorization": f"Bearer {token}"},
            )
        resp = client.post(
            "/api/ai/comment",
            json={"result": {"tong": {"the_tich_m3": 10}}},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 429
