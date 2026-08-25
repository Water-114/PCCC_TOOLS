"""Dự án nhiều công trình (Đợt 2a) — gate kiểm tra cho 4 route mới:
POST/GET/PUT/DELETE /api/aiho/hang-muc — khai báo + xem trước quy mô TỪNG
công trình/khối trong 1 dự án PCCC. KHÔNG gọi AI, KHÔNG trừ quota/Bộ hồ sơ —
giống hệt /quymo-manual (test_quymo_routes.py).

LƯU Ý THUẬT NGỮ: "hạng mục" ở đây nghĩa là 1 CÔNG TRÌNH (Xưởng A, Kho B...),
KHÁC "hạng mục" = 1 loại hệ thống PCCC ở AIHO Bước 1 — xem models.HoSoSessionHangMuc."""

from app.models import HoSoSession
from app.services import credits


def _register_login_and_grant(client, email="hangmucroute@pccc.local", password="matkhau123", amount=5):
    client.post("/api/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    data = resp.get_json()
    token, user_id = data["token"], data["user"]["id"]
    if amount:
        credits.grant_credits(user_id, amount, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="test setup")
    return token, user_id


def _open_session(client, token):
    resp = client.post("/api/aiho/session/open", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["session_id"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_hang_muc_returns_thuoc_dien_preview(client):
    token, _ = _register_login_and_grant(client, email="hangmuc1@pccc.local")
    session_id = _open_session(client, token)

    resp = client.post(
        "/api/aiho/hang-muc",
        json={"session_id": session_id, "ten_hang_muc": "Xưởng A", "quy_mo": {"occ": "sanxuat", "totalArea": 15108, "pplFloor": 350}},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["ten_hang_muc"] == "Xưởng A"
    assert data["fields"]["totalArea"] == 15108
    assert "hang_muc_id" in data

    # id=45 (loa thong bao): 15.108m2 < nguong 18.000m2 -> KHONG thuoc dien
    # (dung diem loi thuc te owner da gap: khong duoc nham "dat" chi vi rule
    # chay xong - phai la "khong_ap_dung", xem quy_mo_store._RULE_TO_THUOC_DIEN_KET_LUAN)
    loa_item = next(it for it in data["thuoc_dien_items"] if it["id"] == 45)
    assert loa_item["ket_luan"] == "khong_ap_dung"


def test_create_hang_muc_above_threshold_marks_loa_thuoc_dien(client):
    token, _ = _register_login_and_grant(client, email="hangmuc2@pccc.local")
    session_id = _open_session(client, token)

    resp = client.post(
        "/api/aiho/hang-muc",
        json={"session_id": session_id, "ten_hang_muc": "Kho B", "quy_mo": {"occ": "sanxuat", "totalArea": 20000, "pplFloor": 350}},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    loa_item = next(it for it in data["thuoc_dien_items"] if it["id"] == 45)
    assert loa_item["ket_luan"] == "dat"


def test_create_hang_muc_does_not_consume_quota_or_forms(client):
    token, user_id = _register_login_and_grant(client, email="hangmuc3@pccc.local", amount=3)
    session_id = _open_session(client, token)
    balance_after_open = credits.credit_balance(user_id)

    resp = client.post(
        "/api/aiho/hang-muc",
        json={"session_id": session_id, "ten_hang_muc": "Xưởng A", "quy_mo": {"occ": "chungcu", "floors": 5}},
        headers=_headers(token),
    )
    assert resp.status_code == 200

    session = HoSoSession.query.get(session_id)
    assert session.files_used == 0
    assert session.forms_used == 0
    assert credits.credit_balance(user_id) == balance_after_open


def test_create_hang_muc_missing_ten_hang_muc_returns_400(client):
    token, _ = _register_login_and_grant(client, email="hangmuc4@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/hang-muc",
        json={"session_id": session_id, "ten_hang_muc": "   ", "quy_mo": {"occ": "chungcu"}},
        headers=_headers(token),
    )
    assert resp.status_code == 400


def test_create_hang_muc_invalid_occ_returns_400(client):
    token, _ = _register_login_and_grant(client, email="hangmuc5@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/hang-muc",
        json={"session_id": session_id, "ten_hang_muc": "Xưởng A", "quy_mo": {"occ": "khong_ton_tai"}},
        headers=_headers(token),
    )
    assert resp.status_code == 400


def test_create_hang_muc_negative_number_returns_400(client):
    token, _ = _register_login_and_grant(client, email="hangmuc6@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/hang-muc",
        json={"session_id": session_id, "ten_hang_muc": "Xưởng A", "quy_mo": {"occ": "chungcu", "floors": -2}},
        headers=_headers(token),
    )
    assert resp.status_code == 400


def test_create_hang_muc_without_session_id_returns_400(client):
    token, _ = _register_login_and_grant(client, email="hangmuc7@pccc.local")
    resp = client.post(
        "/api/aiho/hang-muc",
        json={"ten_hang_muc": "Xưởng A", "quy_mo": {"occ": "chungcu"}},
        headers=_headers(token),
    )
    assert resp.status_code == 400


def test_create_hang_muc_other_users_session_returns_404(client):
    token1, _ = _register_login_and_grant(client, email="hangmuc8a@pccc.local")
    other_session_id = _open_session(client, token1)

    token2, _ = _register_login_and_grant(client, email="hangmuc8b@pccc.local")
    resp = client.post(
        "/api/aiho/hang-muc",
        json={"session_id": other_session_id, "ten_hang_muc": "Xưởng A", "quy_mo": {"occ": "chungcu"}},
        headers=_headers(token2),
    )
    assert resp.status_code == 404


def test_list_hang_muc_returns_multiple_in_creation_order(client):
    token, _ = _register_login_and_grant(client, email="hangmuc9@pccc.local")
    session_id = _open_session(client, token)

    for ten in ("Xưởng A", "Kho B", "Kho C"):
        resp = client.post(
            "/api/aiho/hang-muc",
            json={"session_id": session_id, "ten_hang_muc": ten, "quy_mo": {"occ": "chungcu", "floors": 5}},
            headers=_headers(token),
        )
        assert resp.status_code == 200

    resp = client.get(f"/api/aiho/hang-muc?session_id={session_id}", headers=_headers(token))
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    assert [it["ten_hang_muc"] for it in items] == ["Xưởng A", "Kho B", "Kho C"]


def test_list_hang_muc_other_users_session_returns_404(client):
    token1, _ = _register_login_and_grant(client, email="hangmuc10a@pccc.local")
    other_session_id = _open_session(client, token1)

    token2, _ = _register_login_and_grant(client, email="hangmuc10b@pccc.local")
    resp = client.get(f"/api/aiho/hang-muc?session_id={other_session_id}", headers=_headers(token2))
    assert resp.status_code == 404


def test_update_hang_muc_changes_ten_and_quy_mo(client):
    token, _ = _register_login_and_grant(client, email="hangmuc11@pccc.local")
    session_id = _open_session(client, token)

    resp = client.post(
        "/api/aiho/hang-muc",
        json={"session_id": session_id, "ten_hang_muc": "Xưởng A", "quy_mo": {"occ": "chungcu", "floors": 5}},
        headers=_headers(token),
    )
    hang_muc_id = resp.get_json()["hang_muc_id"]

    resp2 = client.put(
        f"/api/aiho/hang-muc/{hang_muc_id}",
        json={"session_id": session_id, "ten_hang_muc": "Xưởng A (sửa)", "quy_mo": {"occ": "sanxuat", "totalArea": 20000, "pplFloor": 350}},
        headers=_headers(token),
    )
    assert resp2.status_code == 200, resp2.get_json()
    data = resp2.get_json()
    assert data["ten_hang_muc"] == "Xưởng A (sửa)"
    assert data["fields"]["occ"] == "sanxuat"
    assert data["fields"]["totalArea"] == 20000

    listed = client.get(f"/api/aiho/hang-muc?session_id={session_id}", headers=_headers(token)).get_json()["items"]
    assert len(listed) == 1
    assert listed[0]["ten_hang_muc"] == "Xưởng A (sửa)"


def test_update_hang_muc_cannot_edit_other_users_hang_muc(client):
    token1, _ = _register_login_and_grant(client, email="hangmuc12a@pccc.local")
    session1 = _open_session(client, token1)
    resp = client.post(
        "/api/aiho/hang-muc",
        json={"session_id": session1, "ten_hang_muc": "Xưởng A", "quy_mo": {"occ": "chungcu"}},
        headers=_headers(token1),
    )
    hang_muc_id = resp.get_json()["hang_muc_id"]

    token2, _ = _register_login_and_grant(client, email="hangmuc12b@pccc.local")
    session2 = _open_session(client, token2)
    resp2 = client.put(
        f"/api/aiho/hang-muc/{hang_muc_id}",
        json={"session_id": session2, "ten_hang_muc": "Bị sửa trộm", "quy_mo": {"occ": "chungcu"}},
        headers=_headers(token2),
    )
    assert resp2.status_code == 404

    # xac nhan cong trinh cua user1 KHONG bi doi
    listed = client.get(f"/api/aiho/hang-muc?session_id={session1}", headers=_headers(token1)).get_json()["items"]
    assert listed[0]["ten_hang_muc"] == "Xưởng A"


def test_update_hang_muc_missing_ten_returns_400(client):
    token, _ = _register_login_and_grant(client, email="hangmuc13@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/hang-muc",
        json={"session_id": session_id, "ten_hang_muc": "Xưởng A", "quy_mo": {"occ": "chungcu"}},
        headers=_headers(token),
    )
    hang_muc_id = resp.get_json()["hang_muc_id"]

    resp2 = client.put(
        f"/api/aiho/hang-muc/{hang_muc_id}",
        json={"session_id": session_id, "ten_hang_muc": "", "quy_mo": {"occ": "chungcu"}},
        headers=_headers(token),
    )
    assert resp2.status_code == 400


def test_delete_hang_muc_removes_from_list(client):
    token, _ = _register_login_and_grant(client, email="hangmuc14@pccc.local")
    session_id = _open_session(client, token)

    resp = client.post(
        "/api/aiho/hang-muc",
        json={"session_id": session_id, "ten_hang_muc": "Xưởng A", "quy_mo": {"occ": "chungcu"}},
        headers=_headers(token),
    )
    hang_muc_id = resp.get_json()["hang_muc_id"]

    resp2 = client.delete(
        f"/api/aiho/hang-muc/{hang_muc_id}",
        json={"session_id": session_id},
        headers=_headers(token),
    )
    assert resp2.status_code == 200
    assert resp2.get_json()["deleted"] is True

    listed = client.get(f"/api/aiho/hang-muc?session_id={session_id}", headers=_headers(token)).get_json()["items"]
    assert listed == []


def test_delete_hang_muc_cannot_delete_other_users_hang_muc(client):
    token1, _ = _register_login_and_grant(client, email="hangmuc15a@pccc.local")
    session1 = _open_session(client, token1)
    resp = client.post(
        "/api/aiho/hang-muc",
        json={"session_id": session1, "ten_hang_muc": "Xưởng A", "quy_mo": {"occ": "chungcu"}},
        headers=_headers(token1),
    )
    hang_muc_id = resp.get_json()["hang_muc_id"]

    token2, _ = _register_login_and_grant(client, email="hangmuc15b@pccc.local")
    session2 = _open_session(client, token2)
    resp2 = client.delete(
        f"/api/aiho/hang-muc/{hang_muc_id}",
        json={"session_id": session2},
        headers=_headers(token2),
    )
    assert resp2.status_code == 404

    listed = client.get(f"/api/aiho/hang-muc?session_id={session1}", headers=_headers(token1)).get_json()["items"]
    assert len(listed) == 1


def test_delete_hang_muc_nonexistent_id_returns_404(client):
    token, _ = _register_login_and_grant(client, email="hangmuc16@pccc.local")
    session_id = _open_session(client, token)
    resp = client.delete(
        "/api/aiho/hang-muc/999999",
        json={"session_id": session_id},
        headers=_headers(token),
    )
    assert resp.status_code == 404


def test_multiple_hang_muc_per_session_allowed(client):
    """Khac HoSoSessionQuyMo (unique session_id) - 1 phien duoc phep co
    NHIEU ban ghi HoSoSessionHangMuc."""
    token, _ = _register_login_and_grant(client, email="hangmuc17@pccc.local")
    session_id = _open_session(client, token)

    ids = []
    for ten in ("Xưởng A", "Kho B"):
        resp = client.post(
            "/api/aiho/hang-muc",
            json={"session_id": session_id, "ten_hang_muc": ten, "quy_mo": {"occ": "chungcu"}},
            headers=_headers(token),
        )
        ids.append(resp.get_json()["hang_muc_id"])

    assert len(set(ids)) == 2  # 2 ban ghi rieng biet, khong ghi de nhau


def test_requires_login(client):
    resp = client.post("/api/aiho/hang-muc", json={"session_id": 1, "ten_hang_muc": "X", "quy_mo": {"occ": "chungcu"}})
    assert resp.status_code == 401
    resp = client.get("/api/aiho/hang-muc?session_id=1")
    assert resp.status_code == 401
    resp = client.put("/api/aiho/hang-muc/1", json={"session_id": 1, "ten_hang_muc": "X", "quy_mo": {"occ": "chungcu"}})
    assert resp.status_code == 401
    resp = client.delete("/api/aiho/hang-muc/1", json={"session_id": 1})
    assert resp.status_code == 401
