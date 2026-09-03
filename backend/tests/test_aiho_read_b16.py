"""B16 (chữa cháy bằng bột) — gate kiểm tra cho route AI đọc bản vẽ
(/api/aiho/read-b16). Không gọi AI thật — mock app.routes.aiho.get_provider.

Cùng trọng tâm như test_aiho_read_b15.py: AI trả lời ĐỦ 33 id (id nhánh không
chọn = "khong_ap_dung") KHÔNG bị validate_reader_result() reject."""

import io
import json
from unittest.mock import patch

from app.models import UsageLog, User
from app.providers.base import GenerationResult, ProviderNotConfigured
from app.services import credits, mdc_filler

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
EMPTY_KIEN_NGHI = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}


def _register_login_and_grant(client, email="b16read@pccc.local", password="matkhau123", amount=5):
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
        "/api/aiho/read-b16",
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


_THE_TICH_IDS = {19, 20, 21, 22, 23, 24}
_BE_MAT_IDS = {27, 28, 29}


def _payload(nhanh="the_tich", so_hieu="B16-01"):
    rows = mdc_filler.load_criteria_rows("bot_chua_chay")
    other_ids = _BE_MAT_IDS if nhanh == "the_tich" else _THE_TICH_IDS
    items = []
    for r in rows:
        if r["id"] in other_ids:
            items.append({"id": r["id"], "noi_dung_thiet_ke": "x - Không áp dụng", "ket_luan": "khong_ap_dung"})
        else:
            items.append({"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"})
    return json.dumps({
        "nhanh": nhanh,
        "ly_do_nhan_dien": "bảo vệ toàn bộ phòng kín chứa máy phát điện" if nhanh == "the_tich" else "bảo vệ máy biến áp ngoài trời",
        "so_hieu_ban_ve": so_hieu,
        "items": items,
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
    })


def _fake_provider(nhanh="the_tich"):
    return FakeProvider(fn=lambda system_prompt: _payload(nhanh=nhanh))


def test_full_id_set_with_khong_ap_dung_branch_validates_ok():
    from app.services import bot_chua_chay_reader
    data = json.loads(_payload(nhanh="the_tich"))
    model = bot_chua_chay_reader._validate(data)
    assert len(model.items) == 33
    na_ids = {item.id for item in model.items if item.ket_luan == "khong_ap_dung"}
    assert na_ids == _BE_MAT_IDS


def test_returns_correct_mdc_file_and_nhanh_field(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = _fake_provider(nhanh="be_mat")
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id, extra_form={"outputs": "mdc"})
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["nhanh"] == "be_mat"
    assert data["ho_so"]["forms_used"] == 1  # forms_per_call=1

    mdc_files = data["mdc_docx_files"]
    assert len(mdc_files) == 1
    assert mdc_files[0]["loai"] == "bot_chua_chay"
    assert mdc_files[0].get("base64")
    assert mdc_files[0]["filename"] == mdc_filler.filename_for("bot_chua_chay")


def test_validate_rejects_wrong_id_set(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)

    rows_wrong = mdc_filler.load_criteria_rows("chua_chay_gia_ke_hang")  # id set cua form KHAC
    bad_payload = json.dumps({
        "nhanh": "the_tich",
        "so_hieu_ban_ve": "X",
        "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows_wrong],
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
    })
    provider = FakeProvider(fn=lambda system_prompt: bad_payload)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 502


def test_invalid_nhanh_value_rejected(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)

    rows = mdc_filler.load_criteria_rows("bot_chua_chay")
    bad_payload = json.dumps({
        "nhanh": "khong_hop_le",
        "so_hieu_ban_ve": "X",
        "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
    })
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
    token, _ = _register_login_and_grant(client, email="b16readerr@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(exc=TimeoutError("connection timed out to internal-host:443"))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 502
    assert "internal-host" not in resp.get_json()["error"]

    user = User.query.filter_by(email="b16readerr@pccc.local").first()
    logs = UsageLog.query.filter_by(user_id=user.id).all()
    assert len(logs) == 1 and logs[0].status == "error"


def test_success_writes_usage_log_and_marks_session_success(client):
    token, user_id = _register_login_and_grant(client, email="b16readok@pccc.local")
    session_id = _open_session(client, token)
    provider = _fake_provider()
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 200

    logs = UsageLog.query.filter_by(user_id=user_id).all()
    assert len(logs) == 1 and logs[0].status == "success"


def test_requires_login(client):
    resp = client.post(
        "/api/aiho/read-b16",
        data={"files": (io.BytesIO(PNG_BYTES), "drawing.png"), "session_id": "1"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 401
