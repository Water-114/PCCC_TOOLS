"""Vá lỗi: hạng mục đọc bản vẽ (AIHO) chưa từng ghi UsageLog, khiến thống kê
admin ("Tổng lượt gọi API", "Lượt gọi hôm nay", "Đã dùng/hạn mức hôm nay")
luôn hiện 0, và AIHO_DAILY_QUOTA (5 lần/ngày) chưa từng được áp dụng thật.

Test cho _handle_read_request() (routes/aiho.py) sau khi vá:
- Mỗi lượt gọi AI thật (thành công/lỗi) ghi đúng 1 dòng UsageLog api_name=aiho_analysis.
- ProviderNotConfigured (chưa cấu hình key) KHÔNG tính là 1 lượt dùng (giống hệt
  /api/ai/comment) — chưa thực sự gọi AI nào.
- Đủ 5 lượt thật trong ngày (đúng AIHO_DAILY_QUOTA) -> lượt thứ 6 bị chặn 429,
  KHÔNG gọi tới provider (mock get_provider không được gọi ở lượt bị chặn).
- Admin (/api/admin/users, /api/admin/stats) thấy đúng số liệu thay vì 0.
- /api/aiho/quymo-manual (nhập tay, không gọi AI) KHÔNG ghi UsageLog, không bị
  chặn bởi hạn mức này dù gọi quá 5 lần/ngày.
"""

import io
import json
from unittest.mock import patch

from app.extensions import db
from app.models import AIHO_API_NAME, User, UsageLog
from app.providers.base import GenerationResult, ProviderNotConfigured
from app.services import credits, mdc_filler

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
EMPTY_KIEN_NGHI = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}


def _register_login_and_grant(client, email, password="matkhau123", amount=5):
    client.post("/api/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    data = resp.get_json()
    token, user_id = data["token"], data["user"]["id"]
    if amount:
        credits.grant_credits(user_id, amount, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="test setup")
    return token, user_id


def _make_admin(email="admin_usagelog@pccc.local", password="matkhau123"):
    user = User(email=email, role="admin")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


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


def _dienpccc_payload():
    rows = mdc_filler.load_criteria_rows("dien_pccc")
    return json.dumps({
        "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
        "so_hieu_ban_ve": "E-01",
    })


def _upload(client, token, session_id):
    return client.post(
        "/api/aiho/read-dienpccc",
        data={"file": (io.BytesIO(PNG_BYTES), "drawing.png"), "session_id": str(session_id)},
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


# ---------------------------------------------------------------------------
# UsageLog duoc ghi dung cho tung loai ket qua
# ---------------------------------------------------------------------------
def test_successful_call_writes_exactly_one_success_usage_log(client):
    token, user_id = _register_login_and_grant(client, "usagelog_ok@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 200

    logs = UsageLog.query.filter_by(user_id=user_id, api_name=AIHO_API_NAME).all()
    assert len(logs) == 1
    assert logs[0].status == "success"


def test_provider_error_call_writes_error_usage_log(client):
    token, user_id = _register_login_and_grant(client, "usagelog_err@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(exc=TimeoutError("connection timed out"))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 502

    logs = UsageLog.query.filter_by(user_id=user_id, api_name=AIHO_API_NAME).all()
    assert len(logs) == 1
    assert logs[0].status == "error"


def test_provider_not_configured_does_not_write_usage_log(client):
    """Chua cau hinh API key -> chua thuc su goi AI nao -> KHONG tinh la 1 luot
    dung (giong het /api/ai/comment) - khac voi loi trong luc GOI AI that."""
    token, user_id = _register_login_and_grant(client, "usagelog_noapikey@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(exc=ProviderNotConfigured("Chưa cấu hình ANTHROPIC_API_KEY."))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 503

    logs = UsageLog.query.filter_by(user_id=user_id, api_name=AIHO_API_NAME).all()
    assert len(logs) == 0


# ---------------------------------------------------------------------------
# Han muc AIHO_DAILY_QUOTA (5 lan/ngay) duoc ap dung that
# ---------------------------------------------------------------------------
def test_sixth_call_in_one_day_is_blocked_with_429(client):
    token, user_id = _register_login_and_grant(client, "usagelog_quota@pccc.local", amount=10)
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())

    with patch("app.routes.aiho.get_provider", return_value=provider) as mock_get_provider:
        for i in range(5):
            resp = _upload(client, token, session_id)
            assert resp.status_code == 200, f"lan {i + 1} phai thanh cong"

        mock_get_provider.reset_mock()
        resp6 = _upload(client, token, session_id)
        assert resp6.status_code == 429
        assert "hạn mức" in resp6.get_json()["error"]
        mock_get_provider.assert_not_called()  # khong duoc goi toi AI o lan bi chan

    logs = UsageLog.query.filter_by(user_id=user_id, api_name=AIHO_API_NAME, status="success").all()
    assert len(logs) == 5  # lan thu 6 khong ghi them log nao


def test_error_calls_also_count_toward_daily_quota(client):
    """count_usage_today() tinh ca 'error' - lam du 5 lan LOI trong ngay cung
    phai bi chan lan thu 6, khong chi rieng lan thanh cong."""
    token, user_id = _register_login_and_grant(client, "usagelog_quota_err@pccc.local", amount=10)
    session_id = _open_session(client, token)
    provider = FakeProvider(exc=TimeoutError("timeout"))

    with patch("app.routes.aiho.get_provider", return_value=provider):
        for i in range(5):
            resp = _upload(client, token, session_id)
            assert resp.status_code == 502, f"lan {i + 1} phai loi 502"

        resp6 = _upload(client, token, session_id)
        assert resp6.status_code == 429


# ---------------------------------------------------------------------------
# Admin thay dung so lieu thay vi 0
# ---------------------------------------------------------------------------
def test_admin_sees_real_usage_numbers_not_zero(client):
    _make_admin()
    admin_login = client.post("/api/auth/login", json={"email": "admin_usagelog@pccc.local", "password": "matkhau123"})
    admin_token = admin_login.get_json()["token"]

    token, user_id = _register_login_and_grant(client, "usagelog_admin_target@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 200

    stats_resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert stats_resp.status_code == 200
    stats = stats_resp.get_json()
    assert stats["total_calls"] >= 1
    assert stats["calls_today"] >= 1

    users_resp = client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert users_resp.status_code == 200
    by_id = {u["id"]: u for u in users_resp.get_json()["users"]}
    assert by_id[user_id]["used_today"] == 1


# ---------------------------------------------------------------------------
# quymo-manual (nhap tay) KHONG ghi UsageLog, KHONG bi chan boi han muc nay
# ---------------------------------------------------------------------------
def test_quymo_manual_does_not_write_usage_log_or_hit_quota(client):
    token, user_id = _register_login_and_grant(client, "usagelog_manual@pccc.local", amount=10)
    session_id = _open_session(client, token)

    for _ in range(6):  # nhieu hon 5 (han muc AI/ngay) - van khong bi chan
        resp = client.post(
            "/api/aiho/quymo-manual",
            json={"session_id": session_id, "quy_mo": {"occ": "chungcu", "floors": 5}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    logs = UsageLog.query.filter_by(user_id=user_id, api_name=AIHO_API_NAME).all()
    assert len(logs) == 0
