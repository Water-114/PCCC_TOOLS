"""Batch 5A mở rộng — gate kiểm tra cho route AI đọc bản vẽ B7-B11
(/api/aiho/read-khibot). Không gọi AI thật — mock app.routes.aiho.get_provider.

Route này dùng ĐÚNG _handle_read_request() dùng chung (quota/session/magic
bytes/UsageLog đã có test bao phủ qua test_aiho_read_routes.py) — trọng tâm ở
đây là hành vi RIÊNG của khibot: chọn đúng expected_ids theo he_thong AI trả
về, _build_khibot_mdc() chọn đúng loai/label MDC, và cả 5 he_thong đều hoạt
động qua đúng 1 route."""

import io
import json
from unittest.mock import patch

from app.models import UsageLog, User
from app.providers.base import GenerationResult, ProviderNotConfigured
from app.services import credits, mdc_filler

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
EMPTY_KIEN_NGHI = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}


def _register_login_and_grant(client, email="khibotread@pccc.local", password="matkhau123", amount=5):
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


def _upload(client, token, session_id, extra_form=None):
    form = {"files": (io.BytesIO(PNG_BYTES), "drawing.png"), "session_id": str(session_id)}
    if extra_form:
        form.update(extra_form)
    return client.post(
        "/api/aiho/read-khibot",
        data=form,
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


class FakeProvider:
    def __init__(self, name="fake", model="fake-model", fn=None, exc=None):
        self.name = name
        self.model = model
        self.fn = fn
        self.exc = exc

    def generate_with_documents(self, system_prompt, content_blocks):
        if self.exc is not None:
            raise self.exc
        return GenerationResult(text=self.fn(system_prompt))


def _payload_for(he_thong, so_hieu="KHI-01"):
    rows = mdc_filler.load_criteria_rows(he_thong)
    items = [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows]
    return json.dumps({
        "he_thong": he_thong,
        "ly_do_nhan_dien": "test",
        "so_hieu_ban_ve": so_hieu,
        "items": items,
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
    })


def _fake_provider_for(he_thong):
    return FakeProvider(fn=lambda system_prompt: _payload_for(he_thong))


# ---------------------------------------------------------------------------
# Ca 4 he thong deu hoat dong qua dung 1 route, forms_per_call=1 (B7 bot_co_dinh
# CO Y khong con trong pham vi module nay - owner tach rieng, lam sau)
# ---------------------------------------------------------------------------
def test_each_he_thong_returns_correct_mdc_file(client):
    for i, he_thong in enumerate(("khi_hoa_long", "khi_nen", "khi_co2", "sol_khi")):
        token, _ = _register_login_and_grant(client, email=f"khibotread{i}@pccc.local")
        session_id = _open_session(client, token)
        provider = _fake_provider_for(he_thong)
        with patch("app.routes.aiho.get_provider", return_value=provider):
            resp = _upload(client, token, session_id, extra_form={"outputs": "mdc"})
        assert resp.status_code == 200, resp.get_json()
        data = resp.get_json()
        assert data["he_thong"] == he_thong
        assert data["ho_so"]["forms_used"] == 1  # forms_per_call=1, khong phai 3/2 nhu ccnuoc/densucco

        mdc_files = data["mdc_docx_files"]
        assert len(mdc_files) == 1
        assert mdc_files[0]["loai"] == he_thong
        assert mdc_files[0].get("base64")
        expected_filename = mdc_filler.filename_for(he_thong)
        assert mdc_files[0]["filename"] == expected_filename


def test_validate_selects_expected_ids_matching_he_thong_not_fixed_set(client):
    """Neu AI tra ve he_thong='khi_co2' nhung items lai dung bo id cua 'sol_khi'
    (id set khac nhau ro ret giua 2 he), validate PHAI bao loi (khong am tham
    chap nhan sai bo id)."""
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)

    rows_wrong = mdc_filler.load_criteria_rows("sol_khi")  # id set cua he KHAC
    bad_payload = json.dumps({
        "he_thong": "khi_co2",
        "ly_do_nhan_dien": "test",
        "so_hieu_ban_ve": "X",
        "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows_wrong],
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
    })
    # retry-repair se goi AI 2 lan (lan 2 cung sai) -> cuoi cung la AIReaderError -> 502
    provider = FakeProvider(fn=lambda system_prompt: bad_payload)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 502


def test_no_api_key_returns_503(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = FakeProvider(exc=ProviderNotConfigured("Chưa cấu hình ANTHROPIC_API_KEY."))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 503


def test_provider_error_returns_502_and_logs_usage(client):
    token, _ = _register_login_and_grant(client, email="khibotreaderr@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(exc=TimeoutError("connection timed out to internal-host:443"))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 502
    assert "internal-host" not in resp.get_json()["error"]

    user = User.query.filter_by(email="khibotreaderr@pccc.local").first()
    logs = UsageLog.query.filter_by(user_id=user.id).all()
    assert len(logs) == 1 and logs[0].status == "error"


def test_success_writes_usage_log_and_marks_session_success(client):
    token, user_id = _register_login_and_grant(client, email="khibotreadok@pccc.local")
    session_id = _open_session(client, token)
    provider = _fake_provider_for("khi_hoa_long")
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 200

    logs = UsageLog.query.filter_by(user_id=user_id).all()
    assert len(logs) == 1 and logs[0].status == "success"
