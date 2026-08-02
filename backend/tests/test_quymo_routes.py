"""Batch 5A mở rộng ("Quy mô"/Form A) — gate kiểm tra cho 2 route mới:
POST /api/aiho/read-quymo (AI đọc bản vẽ kiến trúc) và POST /api/aiho/quymo-manual
(nhập tay, KHÔNG gọi AI, KHÔNG trừ quota/Bộ hồ sơ). Cả 2 đều phải lưu được dữ
liệu quy mô (quy_mo_store.get_quy_mo()) để 4 hạng mục khác tái dùng, và đều
xuất được Form A (.docx).

KHÔNG gọi AI thật — mock app.routes.aiho.get_provider hoàn toàn, giống
test_aiho_read_routes.py."""

import io
import json
from unittest.mock import patch

from docx import Document

from app.models import HoSoSession
from app.providers.base import GenerationResult
from app.services import credits, quy_mo_store

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _register_login_and_grant(client, email="quymoroute@pccc.local", password="matkhau123", amount=5):
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


class FakeProvider:
    def __init__(self, name="fake", model="fake-model", fn=None, exc=None):
        self.name = name
        self.model = model
        self.fn = fn
        self.exc = exc

    def generate_with_document(self, system_prompt, content_block):
        if self.exc is not None:
            raise self.exc
        return GenerationResult(text=self.fn(system_prompt))


def _quymo_ai_payload(occ="chungcu", floors=8, so_hieu="KT-01"):
    return json.dumps({
        "so_hieu_ban_ve": so_hieu,
        "quy_mo": {"occ": occ, "floors": floors, "totalArea": 3000, "hFire": 22},
        "bang_a2_bao_chay": "Khu vực kỹ thuật tầng hầm.",
        "bang_a4_bao_chay": quy_mo_store.KHONG_XAC_DINH_AI,
        "bang_a2_sprinkler": quy_mo_store.KHONG_XAC_DINH_AI,
        "bang_a4_sprinkler": quy_mo_store.KHONG_XAC_DINH_AI,
    })


def _upload_quymo(client, token, session_id, extra_form=None):
    form = {"file": (io.BytesIO(PNG_BYTES), "kientruc.png"), "session_id": str(session_id), "outputs": "mdc"}
    if extra_form:
        form.update(extra_form)
    return client.post(
        "/api/aiho/read-quymo",
        data=form,
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


# ---------------------------------------------------------------------------
# Route AI: /api/aiho/read-quymo
# ---------------------------------------------------------------------------
def test_read_quymo_success_saves_data_and_returns_mdc(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _quymo_ai_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_quymo(client, token, session_id)
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["quy_mo"]["occ"] == "chungcu"
    assert len(data["mdc_docx_files"]) == 1
    assert data["mdc_docx_files"][0]["loai"] == "quy_mo"
    assert "base64" in data["mdc_docx_files"][0]

    saved = quy_mo_store.get_quy_mo(session_id)
    assert saved["occ"] == "chungcu"
    assert saved["floors"] == 8


def test_read_quymo_generated_docx_has_mục_1_and_type1_rows_filled(client):
    token, _ = _register_login_and_grant(client, email="quymoroute2@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _quymo_ai_payload(occ="chungcu", floors=10))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_quymo(client, token, session_id)
    b64 = resp.get_json()["mdc_docx_files"][0]["base64"]
    import base64
    doc = Document(io.BytesIO(base64.b64decode(b64)))
    table = doc.tables[0]
    row3_text = table.rows[3].cells[2].text  # id=3 "So tang cac hang muc cong trinh"
    assert "10" in row3_text


def test_read_quymo_without_session_id_returns_400(client):
    token, _ = _register_login_and_grant(client, email="quymoroute3@pccc.local")
    provider = FakeProvider(fn=lambda sp: _quymo_ai_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider) as mock_get_provider:
        resp = client.post(
            "/api/aiho/read-quymo",
            data={"file": (io.BytesIO(PNG_BYTES), "kientruc.png")},
            headers={"Authorization": f"Bearer {token}"},
            content_type="multipart/form-data",
        )
    assert resp.status_code == 400
    mock_get_provider.assert_not_called()


def test_read_quymo_counts_1_file_and_1_form_in_session(client):
    token, _ = _register_login_and_grant(client, email="quymoroute4@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _quymo_ai_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        _upload_quymo(client, token, session_id)
    session = HoSoSession.query.get(session_id)
    assert session.files_used == 1
    assert session.forms_used == 1
    assert session.success_count == 1


# ---------------------------------------------------------------------------
# Route thu cong: /api/aiho/quymo-manual — KHONG goi AI, KHONG tru quota
# ---------------------------------------------------------------------------
def test_quymo_manual_success_saves_data_and_returns_mdc(client):
    token, _ = _register_login_and_grant(client, email="quymomanual1@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/quymo-manual",
        json={"session_id": session_id, "quy_mo": {"occ": "khachsan", "floors": 9, "volume": 6000}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["quy_mo"]["occ"] == "khachsan"
    assert len(data["mdc_docx_files"]) == 1

    saved = quy_mo_store.get_quy_mo(session_id)
    assert saved["occ"] == "khachsan"
    assert saved["floors"] == 9


def test_quymo_manual_does_not_consume_quota_or_forms(client):
    token, user_id = _register_login_and_grant(client, email="quymomanual2@pccc.local", amount=3)
    session_id = _open_session(client, token)
    balance_after_open = credits.credit_balance(user_id)

    resp = client.post(
        "/api/aiho/quymo-manual",
        json={"session_id": session_id, "quy_mo": {"occ": "chungcu", "floors": 5}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    session = HoSoSession.query.get(session_id)
    assert session.files_used == 0
    assert session.forms_used == 0
    assert credits.credit_balance(user_id) == balance_after_open  # khong doi them


def test_quymo_manual_invalid_occ_returns_400(client):
    token, _ = _register_login_and_grant(client, email="quymomanual3@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/quymo-manual",
        json={"session_id": session_id, "quy_mo": {"occ": "khong_ton_tai"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_quymo_manual_negative_number_returns_400(client):
    token, _ = _register_login_and_grant(client, email="quymomanual4@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/quymo-manual",
        json={"session_id": session_id, "quy_mo": {"occ": "chungcu", "floors": -2}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_quymo_manual_other_users_session_returns_404(client):
    token1, _ = _register_login_and_grant(client, email="quymomanual5a@pccc.local")
    other_session_id = _open_session(client, token1)

    token2, _ = _register_login_and_grant(client, email="quymomanual5b@pccc.local")
    resp = client.post(
        "/api/aiho/quymo-manual",
        json={"session_id": other_session_id, "quy_mo": {"occ": "chungcu"}},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 404


def test_quymo_manual_without_session_id_returns_400(client):
    token, _ = _register_login_and_grant(client, email="quymomanual6@pccc.local")
    resp = client.post(
        "/api/aiho/quymo-manual",
        json={"quy_mo": {"occ": "chungcu"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
