"""Quy mô Giai đoạn 1 — gate kiểm tra cho 3 route mới trong routes/aiho.py:
POST /api/aiho/scan-quymo (Lượt 0 — quét nhẹ 1 file, KHÔNG trừ Bộ hồ sơ, CÓ
trừ quota AI/ngày), POST /api/aiho/scan-quymo/finish (gộp + lưu hoặc chỉ
đánh dấu đã thử), POST /api/aiho/quymo-reverse-check (Phần E). KHÔNG gọi AI
thật — mock app.routes.aiho.get_provider."""

import io
import json
from unittest.mock import patch

from app.models import HoSoSession, UsageLog
from app.models import AIHO_API_NAME
from app.providers.base import GenerationResult
from app.services import credits, quy_mo_store

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _register_login_and_grant(client, email="scanquymo@pccc.local", password="matkhau123", amount=5):
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


def _scan_payload(tim_thay=True, occ=None, floors=None, so_hieu="BC-01"):
    quy_mo = None
    if tim_thay:
        quy_mo = {
            "occ": occ, "floors": floors, "basements": None, "semiBasements": None,
            "areaFloor": None, "totalArea": None, "volume": None, "hFire": None,
            "kids": None, "seats": None, "hazard": None, "garaKin": None, "garaKC12": None,
            "garaBcl": None, "garaCapS": None, "pplFloor": None, "extLevel": None,
            "hanhLangDaiNhat": None, "chieuCaoKeHang": None, "coBeXangDauNgoaiTroi": None,
        }
    return json.dumps({"so_hieu_ban_ve": so_hieu, "tim_thay": tim_thay, "quy_mo": quy_mo})


def _upload_scan(client, token, session_id, filename="baochay.png"):
    form = {"file": (io.BytesIO(PNG_BYTES), filename), "session_id": str(session_id)}
    return client.post(
        "/api/aiho/scan-quymo",
        data=form,
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


# ---------------------------------------------------------------------------
# POST /api/aiho/scan-quymo
# ---------------------------------------------------------------------------
def test_scan_quymo_tim_thay_true_returns_quy_mo(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _scan_payload(tim_thay=True, occ="chungcu", floors=8))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_scan(client, token, session_id)
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["tim_thay"] is True
    assert data["quy_mo"]["occ"] == "chungcu"
    assert data["quy_mo"]["floors"] == 8


def test_scan_quymo_tim_thay_false_returns_null_quy_mo(client):
    token, _ = _register_login_and_grant(client, email="scanquymo2@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _scan_payload(tim_thay=False))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_scan(client, token, session_id)
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["tim_thay"] is False
    assert data["quy_mo"] is None


def test_scan_quymo_does_not_reserve_ho_so_slot(client):
    """Luot 0 KHONG duoc cong vao files_used/forms_used cua phien (khac han
    _handle_read_request dung cho 7 route con lai)."""
    token, _ = _register_login_and_grant(client, email="scanquymo3@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _scan_payload(tim_thay=True, occ="chungcu"))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        _upload_scan(client, token, session_id)
    session = HoSoSession.query.get(session_id)
    assert session.files_used == 0
    assert session.forms_used == 0


def test_scan_quymo_counts_daily_ai_quota(client):
    """Luot 0 CO tru han muc 'luot goi AI/ngay' (dung chung count_usage_today/
    AIHO_API_NAME voi 7 route con lai)."""
    token, user_id = _register_login_and_grant(client, email="scanquymo4@pccc.local")
    session_id = _open_session(client, token)
    before = UsageLog.query.filter_by(user_id=user_id, api_name=AIHO_API_NAME).count()
    provider = FakeProvider(fn=lambda sp: _scan_payload(tim_thay=True, occ="chungcu"))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_scan(client, token, session_id)
    assert resp.status_code == 200
    after = UsageLog.query.filter_by(user_id=user_id, api_name=AIHO_API_NAME).count()
    assert after == before + 1
    logs = UsageLog.query.filter_by(user_id=user_id, api_name=AIHO_API_NAME).all()
    assert logs[-1].status == "success"


def test_scan_quymo_blocked_when_quota_exhausted(client):
    token, user_id = _register_login_and_grant(client, email="scanquymo5@pccc.local")
    session_id = _open_session(client, token)
    from app.models import User
    user = User.query.get(user_id)
    user.daily_quota = 0
    from app.extensions import db
    db.session.commit()

    provider = FakeProvider(fn=lambda sp: _scan_payload(tim_thay=True, occ="chungcu"))
    with patch("app.routes.aiho.get_provider", return_value=provider) as mock_provider:
        resp = _upload_scan(client, token, session_id)
    assert resp.status_code == 429
    mock_provider.assert_not_called()


def test_scan_quymo_file_too_large_returns_400(client):
    token, _ = _register_login_and_grant(client, email="scanquymo6@pccc.local")
    session_id = _open_session(client, token)
    from app.routes.aiho import SINGLE_MAX_BYTES_IMAGE
    big_bytes = PNG_BYTES + b"\x00" * (SINGLE_MAX_BYTES_IMAGE + 1)
    resp = client.post(
        "/api/aiho/scan-quymo",
        data={"file": (io.BytesIO(big_bytes), "big.png"), "session_id": str(session_id)},
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "7" in resp.get_json()["error"]


def test_scan_quymo_without_session_id_returns_400(client):
    token, _ = _register_login_and_grant(client, email="scanquymo7@pccc.local")
    resp = client.post(
        "/api/aiho/scan-quymo",
        data={"file": (io.BytesIO(PNG_BYTES), "x.png")},
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_scan_quymo_requires_login(client):
    resp = client.post("/api/aiho/scan-quymo", data={})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/aiho/scan-quymo/finish
# ---------------------------------------------------------------------------
def test_scan_finish_saves_when_found(client):
    token, _ = _register_login_and_grant(client, email="scanfinish1@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/scan-quymo/finish",
        json={
            "session_id": session_id,
            "results": [
                {"slot": "baochay", "label": "Báo cháy tự động", "tim_thay": True, "quy_mo": {"occ": "chungcu", "floors": 8}},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["saved"]["occ"] == "chungcu"
    assert data["conflicts"] == []
    assert data["found_count"] == 1

    saved = quy_mo_store.get_quy_mo(session_id)
    assert saved["occ"] == "chungcu"
    assert saved["floors"] == 8

    session = HoSoSession.query.get(session_id)
    assert session.quy_mo_scan_attempted_at is not None


def test_scan_finish_marks_attempted_but_no_row_when_nothing_found(client):
    """Phan C — khong tim thay gi o ca 2 file: KHONG tao HoSoSessionQuyMo (giu
    get_quy_mo() tra None), CHI danh dau quy_mo_scan_attempted_at."""
    token, _ = _register_login_and_grant(client, email="scanfinish2@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/scan-quymo/finish",
        json={
            "session_id": session_id,
            "results": [
                {"slot": "baochay", "label": "Báo cháy tự động", "tim_thay": False, "quy_mo": None},
                {"slot": "ccnuoc", "label": "Chữa cháy bằng nước", "tim_thay": False, "quy_mo": None},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["saved"] is None
    assert data["found_count"] == 0

    assert quy_mo_store.get_quy_mo(session_id) is None
    session = HoSoSession.query.get(session_id)
    assert session.quy_mo_scan_attempted_at is not None


def test_scan_finish_reports_conflicts(client):
    token, _ = _register_login_and_grant(client, email="scanfinish3@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/scan-quymo/finish",
        json={
            "session_id": session_id,
            "results": [
                {"slot": "baochay", "label": "Báo cháy tự động", "tim_thay": True, "quy_mo": {"occ": "chungcu", "floors": 8, "totalArea": 3000}},
                {"slot": "ccnuoc", "label": "Chữa cháy bằng nước", "tim_thay": True, "quy_mo": {"floors": 10}},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert len(data["conflicts"]) == 1
    assert data["conflicts"][0]["field"] == "floors"
    assert data["saved"]["floors"] == 8  # baochay day du hon duoc uu tien


def test_scan_finish_other_users_session_returns_404(client):
    token1, _ = _register_login_and_grant(client, email="scanfinish4a@pccc.local")
    other_session_id = _open_session(client, token1)
    token2, _ = _register_login_and_grant(client, email="scanfinish4b@pccc.local")
    resp = client.post(
        "/api/aiho/scan-quymo/finish",
        json={"session_id": other_session_id, "results": [{"slot": "baochay", "label": "x", "tim_thay": False, "quy_mo": None}]},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/aiho/quymo-reverse-check
# ---------------------------------------------------------------------------
def test_reverse_check_no_quy_mo_returns_empty(client):
    token, _ = _register_login_and_grant(client, email="reversecheck1@pccc.local")
    session_id = _open_session(client, token)
    resp = client.post(
        "/api/aiho/quymo-reverse-check",
        json={"session_id": session_id, "slots_with_data": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["has_quy_mo"] is False
    assert data["warnings"] == []


def test_reverse_check_warns_missing_system(client):
    token, _ = _register_login_and_grant(client, email="reversecheck2@pccc.local")
    session_id = _open_session(client, token)
    client.post(
        "/api/aiho/quymo-manual",
        json={"session_id": session_id, "quy_mo": {"occ": "chungcu", "floors": 10, "totalArea": 2000}},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.post(
        "/api/aiho/quymo-reverse-check",
        json={"session_id": session_id, "slots_with_data": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["has_quy_mo"] is True
    slots_warned = {w["slot"] for w in data["warnings"]}
    assert "baochay" in slots_warned
    assert all(w.get("can_cu") for w in data["warnings"])


def test_reverse_check_no_warning_when_all_attached(client):
    token, _ = _register_login_and_grant(client, email="reversecheck3@pccc.local")
    session_id = _open_session(client, token)
    client.post(
        "/api/aiho/quymo-manual",
        json={"session_id": session_id, "quy_mo": {"occ": "chungcu", "floors": 10, "totalArea": 2000}},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.post(
        "/api/aiho/quymo-reverse-check",
        json={"session_id": session_id, "slots_with_data": ["baochay", "ccnuoc", "densucco", "dienpccc", "botcodinh"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["warnings"] == []
