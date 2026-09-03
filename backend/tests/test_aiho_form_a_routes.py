"""Form A gốc (A14/A15) — gate kiểm tra cho route mới:
POST/GET /api/aiho/pham-vi-de-nghi, POST/GET/DELETE /api/aiho/ha-tang-hien-huu,
POST /api/aiho/export-form-a. KHÔNG gọi AI, KHÔNG trừ quota/Bộ hồ sơ — giống
hệt /quymo-manual, /hang-muc (test_aiho_hang_muc_routes.py)."""

from app.models import HoSoSession
from app.services import credits


def _register_login_and_grant(client, email="formaroute@pccc.local", password="matkhau123", amount=5):
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


# ---------------------------------------------------------------------------
# /pham-vi-de-nghi
# ---------------------------------------------------------------------------
def test_pham_vi_de_nghi_default_none_when_not_saved(client):
    token, _ = _register_login_and_grant(client, email="pv1@pccc.local")
    session_id = _open_session(client, token)
    resp = client.get(f"/api/aiho/pham-vi-de-nghi?session_id={session_id}", headers=_headers(token))
    assert resp.status_code == 200
    assert resp.get_json()["pham_vi_de_nghi"] is None


def test_pham_vi_de_nghi_save_and_get(client):
    token, _ = _register_login_and_grant(client, email="pv2@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/pham-vi-de-nghi",
        json={"session_id": session_id, "pham_vi_de_nghi": ["baochay", "hong_nuoc"]},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["pham_vi_de_nghi"] == ["baochay", "hong_nuoc"]

    resp2 = client.get(f"/api/aiho/pham-vi-de-nghi?session_id={session_id}", headers=_headers(token))
    assert resp2.get_json()["pham_vi_de_nghi"] == ["baochay", "hong_nuoc"]


def test_pham_vi_de_nghi_invalid_key_returns_400(client):
    token, _ = _register_login_and_grant(client, email="pv3@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/pham-vi-de-nghi",
        json={"session_id": session_id, "pham_vi_de_nghi": ["khong_ton_tai"]},
        headers=_headers(token),
    )
    assert resp.status_code == 400


def test_pham_vi_de_nghi_does_not_consume_quota_or_forms(client):
    token, user_id = _register_login_and_grant(client, email="pv4@pccc.local", amount=3)
    session_id = _open_session(client, token)
    balance_after_open = credits.credit_balance(user_id)
    resp = client.post(
        "/api/aiho/pham-vi-de-nghi",
        json={"session_id": session_id, "pham_vi_de_nghi": ["baochay"]},
        headers=_headers(token),
    )
    assert resp.status_code == 200
    session = HoSoSession.query.get(session_id)
    assert session.files_used == 0
    assert session.forms_used == 0
    assert credits.credit_balance(user_id) == balance_after_open


# ---------------------------------------------------------------------------
# /ha-tang-hien-huu
# ---------------------------------------------------------------------------
def _ha_tang_payload(session_id, ten_he_thong="tram_bom"):
    return {
        "session_id": session_id,
        "ten_he_thong": ten_he_thong,
        "gcn_so": "490/TD-PCCC",
        "gcn_ngay": "15/01/2015",
        "gcn_bo_sung_so": "621/TD-PCCC-P2",
        "gcn_bo_sung_ngay": "20/06/2016",
        "nghiem_thu_so": "273/CSPCCC-P2",
        "nghiem_thu_ngay": "15/09/2016",
    }


def test_create_ha_tang_hien_huu_and_list(client):
    token, _ = _register_login_and_grant(client, email="ht1@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post("/api/aiho/ha-tang-hien-huu", json=_ha_tang_payload(session_id), headers=_headers(token))
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["ten_he_thong"] == "tram_bom"
    assert resp.get_json()["gcn_so"] == "490/TD-PCCC"

    listed = client.get(f"/api/aiho/ha-tang-hien-huu?session_id={session_id}", headers=_headers(token))
    items = listed.get_json()["items"]
    assert len(items) == 1
    assert items[0]["ten_he_thong"] == "tram_bom"


def test_create_ha_tang_hien_huu_multiple_per_session(client):
    token, _ = _register_login_and_grant(client, email="ht2@pccc.local")
    session_id = _open_session(client, token)
    for ten in ("tram_bom", "dienpccc"):
        resp = client.post("/api/aiho/ha-tang-hien-huu", json=_ha_tang_payload(session_id, ten), headers=_headers(token))
        assert resp.status_code == 200

    listed = client.get(f"/api/aiho/ha-tang-hien-huu?session_id={session_id}", headers=_headers(token))
    items = listed.get_json()["items"]
    assert len(items) == 2
    assert {it["ten_he_thong"] for it in items} == {"tram_bom", "dienpccc"}


def test_create_ha_tang_hien_huu_missing_gcn_so_returns_400(client):
    token, _ = _register_login_and_grant(client, email="ht3@pccc.local")
    session_id = _open_session(client, token)
    payload = _ha_tang_payload(session_id)
    payload["gcn_so"] = ""
    resp = client.post("/api/aiho/ha-tang-hien-huu", json=payload, headers=_headers(token))
    assert resp.status_code == 400


def test_create_ha_tang_hien_huu_invalid_he_thong_key_returns_400(client):
    token, _ = _register_login_and_grant(client, email="ht4@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/ha-tang-hien-huu", json=_ha_tang_payload(session_id, "khong_ton_tai"), headers=_headers(token)
    )
    assert resp.status_code == 400


def test_delete_ha_tang_hien_huu(client):
    token, _ = _register_login_and_grant(client, email="ht5@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post("/api/aiho/ha-tang-hien-huu", json=_ha_tang_payload(session_id), headers=_headers(token))
    ha_tang_id = resp.get_json()["id"]

    resp2 = client.delete(f"/api/aiho/ha-tang-hien-huu/{ha_tang_id}", json={"session_id": session_id}, headers=_headers(token))
    assert resp2.status_code == 200
    assert resp2.get_json()["deleted"] is True

    listed = client.get(f"/api/aiho/ha-tang-hien-huu?session_id={session_id}", headers=_headers(token))
    assert listed.get_json()["items"] == []


def test_delete_ha_tang_hien_huu_other_users_returns_404(client):
    token1, _ = _register_login_and_grant(client, email="ht6a@pccc.local")
    session1 = _open_session(client, token1)
    resp = client.post("/api/aiho/ha-tang-hien-huu", json=_ha_tang_payload(session1), headers=_headers(token1))
    ha_tang_id = resp.get_json()["id"]

    token2, _ = _register_login_and_grant(client, email="ht6b@pccc.local")
    session2 = _open_session(client, token2)
    resp2 = client.delete(f"/api/aiho/ha-tang-hien-huu/{ha_tang_id}", json={"session_id": session2}, headers=_headers(token2))
    assert resp2.status_code == 404


def test_ha_tang_hien_huu_does_not_consume_quota_or_forms(client):
    token, user_id = _register_login_and_grant(client, email="ht7@pccc.local", amount=3)
    session_id = _open_session(client, token)
    balance_after_open = credits.credit_balance(user_id)
    resp = client.post("/api/aiho/ha-tang-hien-huu", json=_ha_tang_payload(session_id), headers=_headers(token))
    assert resp.status_code == 200
    session = HoSoSession.query.get(session_id)
    assert session.files_used == 0
    assert session.forms_used == 0
    assert credits.credit_balance(user_id) == balance_after_open


def test_ha_tang_requires_login(client):
    resp = client.post("/api/aiho/ha-tang-hien-huu", json=_ha_tang_payload(1))
    assert resp.status_code == 401
    resp = client.get("/api/aiho/ha-tang-hien-huu?session_id=1")
    assert resp.status_code == 401
    resp = client.delete("/api/aiho/ha-tang-hien-huu/1", json={"session_id": 1})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /export-form-a
# ---------------------------------------------------------------------------
def test_export_form_a_success_a14(client):
    token, _ = _register_login_and_grant(client, email="ef1@pccc.local")
    session_id = _open_session(client, token)
    client.post(
        "/api/aiho/quymo-manual",
        json={"session_id": session_id, "quy_mo": {"occ": "sanxuat", "totalArea": 5000, "floors": 1}},
        headers=_headers(token),
    )
    resp = client.post(
        "/api/aiho/export-form-a",
        json={"session_id": session_id, "loai_hinh": "A14", "b_form_results": {}},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["filename"]
    assert data["base64"]


def test_export_form_a_success_a15_without_quy_mo(client):
    """Khong dinh Quy mo (tuy chon) - combiner van phai chay duoc, chi la
    cac dong rule se ra 'chua du du lieu' (KN) thay vi +/rong."""
    token, _ = _register_login_and_grant(client, email="ef2@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/export-form-a",
        json={"session_id": session_id, "loai_hinh": "A15"},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.get_json()


def test_export_form_a_invalid_loai_hinh_returns_400(client):
    token, _ = _register_login_and_grant(client, email="ef3@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/export-form-a",
        json={"session_id": session_id, "loai_hinh": "A99"},
        headers=_headers(token),
    )
    assert resp.status_code == 400


def test_export_form_a_does_not_consume_quota_or_forms(client):
    token, user_id = _register_login_and_grant(client, email="ef4@pccc.local", amount=3)
    session_id = _open_session(client, token)
    balance_after_open = credits.credit_balance(user_id)
    resp = client.post(
        "/api/aiho/export-form-a",
        json={"session_id": session_id, "loai_hinh": "A14"},
        headers=_headers(token),
    )
    assert resp.status_code == 200
    session = HoSoSession.query.get(session_id)
    assert session.files_used == 0
    assert session.forms_used == 0
    assert credits.credit_balance(user_id) == balance_after_open


def test_export_form_a_custom_filename_with_ten_du_an(client):
    token, _ = _register_login_and_grant(client, email="ef5@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/export-form-a",
        json={"session_id": session_id, "loai_hinh": "A14", "ten_du_an": "PHAN BON AGRI", "ten_hang_muc": "Nha xuong"},
        headers=_headers(token),
    )
    assert resp.status_code == 200
    filename = resp.get_json()["filename"]
    assert "PHAN_BON_AGRI" in filename
    assert "Nha_xuong" in filename


def test_export_form_a_other_users_session_returns_404(client):
    token1, _ = _register_login_and_grant(client, email="ef6a@pccc.local")
    other_session = _open_session(client, token1)
    token2, _ = _register_login_and_grant(client, email="ef6b@pccc.local")
    resp = client.post(
        "/api/aiho/export-form-a",
        json={"session_id": other_session, "loai_hinh": "A14"},
        headers=_headers(token2),
    )
    assert resp.status_code == 404


def test_export_form_a_requires_login(client):
    resp = client.post("/api/aiho/export-form-a", json={"session_id": 1, "loai_hinh": "A14"})
    assert resp.status_code == 401


def test_export_form_a_works_after_session_closed(client):
    """Frontend dong phien (session/close) TRUOC khi hien nut 'Xuat Form A
    goc' (finishUp() dong phien trong luc render ket qua, nguoi dung co the
    bam nut xuat rat lau sau do) - export-form-a KHONG duoc doi hoi phien
    'open' nhu cac route ghi du lieu khac, chi can dung chu so huu."""
    token, _ = _register_login_and_grant(client, email="ef7@pccc.local")
    session_id = _open_session(client, token)
    close_resp = client.post("/api/aiho/session/close", json={"session_id": session_id}, headers=_headers(token))
    assert close_resp.status_code == 200

    resp = client.post(
        "/api/aiho/export-form-a",
        json={"session_id": session_id, "loai_hinh": "A14"},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.get_json()
