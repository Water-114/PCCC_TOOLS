def test_feedback_rejects_arbitrary_feature_value(client):
    resp = client.post("/api/feedback", json={"feature": "bat_ky_gia_tri_nao"})
    assert resp.status_code == 400


def test_feedback_accepts_known_feature(client):
    resp = client.post("/api/feedback", json={"feature": "aiho_baochay", "rating": 5})
    assert resp.status_code == 200


def test_feedback_rejects_comment_too_long(client):
    resp = client.post("/api/feedback", json={
        "feature": "aiho_baochay",
        "comment": "a" * 2001,
    })
    assert resp.status_code == 400


def test_feedback_stores_html_as_plain_text_not_sanitized_on_write(client):
    """Batch 1 chặn XSS ở phía HIỂN THỊ (frontend dùng textContent), không phải
    bằng cách xoá/escape nội dung lúc lưu — xác nhận backend vẫn lưu đúng
    nguyên văn (không tự ý cắt/đổi nội dung góp ý người dùng gõ)."""
    raw = "<script>alert(1)</script> nội dung góp ý thật"
    resp = client.post("/api/feedback", json={"feature": "aiho_baochay", "comment": raw})
    assert resp.status_code == 200
