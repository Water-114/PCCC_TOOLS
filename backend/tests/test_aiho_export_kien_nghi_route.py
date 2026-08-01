"""Batch 4, sub-bước 1 — test route POST /api/aiho/export-kien-nghi: nhận JSON
dữ liệu đã có sẵn (KHÔNG gọi AI, KHÔNG trừ quota), build .docx trả base64,
vẫn cần đăng nhập."""

import base64
import io

from docx import Document

from app.models import AIHO_API_NAME, count_usage_today


def _register_and_login(client, email="export1@pccc.local", password="matkhau123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    data = resp.get_json()
    return data["token"], data["user"]["id"]


def _valid_hang_muc():
    return {
        "hang_muc": [
            {
                "ten_he_thong": "Báo cháy tự động",
                "so_hieu_ban_ve": "BC-01",
                "kien_nghi": {
                    "I_chua_the_hien": ["Thể hiện rõ ... (Điều 1)."],
                    "II_chua_thong_nhat": [],
                    "III_chua_phu_hop": [],
                    "IV_de_xuat_bo_sung": [],
                },
            }
        ]
    }


def test_requires_login(client):
    resp = client.post("/api/aiho/export-kien-nghi", json=_valid_hang_muc())
    assert resp.status_code == 401


def test_missing_hang_muc_rejected_with_400(client):
    token, _ = _register_and_login(client)
    resp = client.post(
        "/api/aiho/export-kien-nghi",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_empty_hang_muc_list_rejected_with_400(client):
    token, _ = _register_and_login(client, email="export2@pccc.local")
    resp = client.post(
        "/api/aiho/export-kien-nghi",
        json={"hang_muc": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_non_dict_root_rejected_with_400(client):
    token, _ = _register_and_login(client, email="export3@pccc.local")
    resp = client.post(
        "/api/aiho/export-kien-nghi",
        json=[1, 2, 3],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_hang_muc_missing_ten_he_thong_rejected_with_400(client):
    token, _ = _register_and_login(client, email="export4@pccc.local")
    payload = {"hang_muc": [{"kien_nghi": {"I_chua_the_hien": []}}]}
    resp = client.post(
        "/api/aiho/export-kien-nghi",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_hang_muc_missing_kien_nghi_rejected_with_400(client):
    token, _ = _register_and_login(client, email="export5@pccc.local")
    payload = {"hang_muc": [{"ten_he_thong": "Điện PCCC"}]}
    resp = client.post(
        "/api/aiho/export-kien-nghi",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_valid_payload_returns_200_with_downloadable_docx(client):
    token, _ = _register_and_login(client, email="export6@pccc.local")
    resp = client.post(
        "/api/aiho/export-kien-nghi",
        json=_valid_hang_muc(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["filename"].endswith(".docx")
    docx_bytes = base64.b64decode(data["base64"])
    doc = Document(io.BytesIO(docx_bytes))
    texts = [p.text for p in doc.paragraphs]
    assert "KIẾN NGHỊ THIẾT KẾ - Báo cháy tự động" in texts


def test_export_does_not_consume_aiho_quota(client):
    token, user_id = _register_and_login(client, email="export7@pccc.local")
    before = count_usage_today(user_id, AIHO_API_NAME)
    resp = client.post(
        "/api/aiho/export-kien-nghi",
        json=_valid_hang_muc(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    after = count_usage_today(user_id, AIHO_API_NAME)
    assert after == before == 0
