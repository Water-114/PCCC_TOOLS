from unittest.mock import patch


def test_health_returns_ok_when_database_reachable(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "database": "ok"}


def test_health_returns_503_when_database_unreachable(client):
    """Batch 2: /api/health phải thật sự kiểm tra kết nối database, không chỉ
    trả 'ok' tĩnh — giả lập lỗi kết nối và xác nhận trả 503."""
    with patch("app.db.session.execute", side_effect=Exception("connection lost")):
        resp = client.get("/api/health")
    assert resp.status_code == 503
    assert resp.get_json() == {"status": "error", "database": "error"}
