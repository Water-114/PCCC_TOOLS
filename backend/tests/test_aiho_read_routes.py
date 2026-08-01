"""Batch 4 + Batch 5A sub-bước 2 — gate kiểm tra cho các route AI đọc bản vẽ
thật (/api/aiho/read-baochay, read-dienpccc, read-ccnuoc): không có API key,
provider timeout, hết Bộ hồ sơ, partial result chữa cháy nước — CỘNG các gate
riêng của mô hình "phiên Bộ hồ sơ" (session_id thiếu/sai/không thuộc user/đã
đóng, vượt giới hạn 5 file/7 form).

KHÔNG gọi AI thật — mock app.routes.aiho.get_provider hoàn toàn."""

import io
import json
from unittest.mock import patch

from app.models import HoSoSession
from app.providers.base import GenerationResult, ProviderNotConfigured
from app.providers.resilience import CircuitBreakerOpen
from app.services import credits, mdc_filler

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

EMPTY_KIEN_NGHI = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}


def _register_login_and_grant(client, email="aihoread@pccc.local", password="matkhau123", amount=5):
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


def _upload(client, token, session_id, path="/api/aiho/read-dienpccc", filename="drawing.png", extra_form=None):
    form = {"file": (io.BytesIO(PNG_BYTES), filename), "session_id": str(session_id)}
    if extra_form:
        form.update(extra_form)
    return client.post(
        path,
        data=form,
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


def _dienpccc_payload():
    rows = mdc_filler.load_criteria_rows("dien_pccc")
    return json.dumps({
        "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
        "so_hieu_ban_ve": "E-01",
    })


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


# ---------------------------------------------------------------------------
# Khong co API key (ProviderNotConfigured)
# ---------------------------------------------------------------------------
def test_no_api_key_returns_503_with_clean_message(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = FakeProvider(exc=ProviderNotConfigured("Chưa cấu hình ANTHROPIC_API_KEY."))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 503
    assert "ANTHROPIC_API_KEY" in resp.get_json()["error"]


def test_provider_not_configured_still_counts_files_used_in_session(client):
    """Hanh vi ke thua tinh than Batch 1 (truoc day: van tinh 1 luot da dung du
    loi) - o day: van tang files_used trong phien du AI that bai, vi reserve_slot
    chay TRUOC khi goi AI va KHONG rollback khi that bai (xem ho_so_session.py)."""
    token, user_id = _register_login_and_grant(client, email="aihoread1b@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(exc=ProviderNotConfigured("chua cau hinh"))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        _upload(client, token, session_id)

    session = HoSoSession.query.get(session_id)
    assert session.files_used == 1
    assert session.success_count == 0


# ---------------------------------------------------------------------------
# Provider timeout / loi ha tang - khong duoc lo chi tiet exception ra client
# ---------------------------------------------------------------------------
def test_provider_timeout_returns_502_without_leaking_internals(client):
    token, _ = _register_login_and_grant(client, email="aihoread2@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(exc=TimeoutError("connection timed out after 300s to internal-host:443"))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 502
    error = resp.get_json()["error"]
    assert "internal-host" not in error  # khong lo chi tiet ha tang that
    assert "thử lại sau" in error


def test_circuit_breaker_open_returns_502_with_breaker_message(client):
    token, _ = _register_login_and_grant(client, email="aihoread3@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(exc=CircuitBreakerOpen("Provider 'fake' vừa lỗi kết nối 3 lần liên tiếp — tạm ngừng gọi thêm khoảng 60 giây."))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 502
    assert "tạm ngừng gọi thêm" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# Het Bo ho so (thay cho quota lam-lai-moi-ngay cu)
# ---------------------------------------------------------------------------
def test_session_open_returns_429_when_insufficient_credits(client):
    token, user_id = _register_login_and_grant(client, email="aihoread4@pccc.local", amount=0)
    resp = client.post("/api/aiho/session/open", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 429
    data = resp.get_json()
    assert "Đã dùng hết" in data["error"]
    assert data["bo_ho_so_con_lai"] == 0


def test_read_without_session_id_returns_400(client):
    token, _ = _register_login_and_grant(client, email="aihoread4b@pccc.local")
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider) as mock_get_provider:
        resp = client.post(
            "/api/aiho/read-dienpccc",
            data={"file": (io.BytesIO(PNG_BYTES), "drawing.png")},  # thieu session_id
            headers={"Authorization": f"Bearer {token}"},
            content_type="multipart/form-data",
        )
    assert resp.status_code == 400
    mock_get_provider.assert_not_called()


def test_read_with_other_users_session_returns_404(client):
    token1, _ = _register_login_and_grant(client, email="aihoread4c-a@pccc.local")
    other_session_id = _open_session(client, token1)

    token2, _ = _register_login_and_grant(client, email="aihoread4c-b@pccc.local")
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider) as mock_get_provider:
        resp = _upload(client, token2, other_session_id)
    assert resp.status_code == 404
    mock_get_provider.assert_not_called()


def test_read_with_closed_session_returns_400(client):
    token, _ = _register_login_and_grant(client, email="aihoread4d@pccc.local")
    session_id = _open_session(client, token)
    close_resp = client.post(
        "/api/aiho/session/close",
        json={"session_id": session_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert close_resp.status_code == 200

    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider) as mock_get_provider:
        resp = _upload(client, token, session_id)
    assert resp.status_code == 400
    mock_get_provider.assert_not_called()


def test_closing_session_with_zero_successes_refunds_credit(client):
    token, user_id = _register_login_and_grant(client, email="aihoread4e@pccc.local", amount=3)
    session_id = _open_session(client, token)
    assert credits.credit_balance(user_id) == 2  # tru 1 luc mo

    provider = FakeProvider(exc=ProviderNotConfigured("chua cau hinh"))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        _upload(client, token, session_id)  # loi, khong co lan thanh cong nao

    close_resp = client.post(
        "/api/aiho/session/close",
        json={"session_id": session_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert close_resp.status_code == 200
    assert close_resp.get_json()["status"] == "closed_refunded"
    assert credits.credit_balance(user_id) == 3  # hoan lai dung 1


def test_closing_session_with_one_success_keeps_deduction(client):
    token, user_id = _register_login_and_grant(client, email="aihoread4f@pccc.local", amount=3)
    session_id = _open_session(client, token)
    assert credits.credit_balance(user_id) == 2

    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 200

    close_resp = client.post(
        "/api/aiho/session/close",
        json={"session_id": session_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert close_resp.status_code == 200
    assert close_resp.get_json()["status"] == "closed_used"
    assert credits.credit_balance(user_id) == 2  # KHONG hoan, giu nguyen tru


# ---------------------------------------------------------------------------
# Gioi han 5 file / 7 form trong 1 phien
# ---------------------------------------------------------------------------
def test_file_cap_exceeded_returns_400(client):
    token, _ = _register_login_and_grant(client, email="aihoread5file@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        for _ in range(5):  # dung dung 5 file (gioi han)
            resp = _upload(client, token, session_id)
            assert resp.status_code == 200
        resp = _upload(client, token, session_id)  # file thu 6 - vuot gioi han
    assert resp.status_code == 400
    assert "5 file" in resp.get_json()["error"]


def test_form_cap_exceeded_returns_400(client):
    """ccnuoc chiem 3 form/lan goi (B3+B5+B6) - 3 lan = 9 form > gioi han 7."""
    token, _ = _register_login_and_grant(client, email="aihoread5form@pccc.local")
    session_id = _open_session(client, token)

    def fake_generate(system_prompt):
        loai = "tram_bom" if "B3" in system_prompt else ("hong_nuoc" if "B5" in system_prompt else "chua_chay_tu_dong")
        rows = mdc_filler.load_criteria_rows(loai)
        return json.dumps({
            "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
            "tong_ket": "ok",
            "kien_nghi": EMPTY_KIEN_NGHI,
            "so_hieu_ban_ve": "N-01",
        })

    provider = FakeProvider(fn=fake_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp1 = _upload(client, token, session_id, path="/api/aiho/read-ccnuoc", filename="a.png")
        assert resp1.status_code == 200  # 3 form
        resp2 = _upload(client, token, session_id, path="/api/aiho/read-ccnuoc", filename="b.png")
        assert resp2.status_code == 200  # 6 form
        resp3 = _upload(client, token, session_id, path="/api/aiho/read-ccnuoc", filename="c.png")  # 9 form - vuot 7
    assert resp3.status_code == 400
    assert "7 form" in resp3.get_json()["error"]


# ---------------------------------------------------------------------------
# Thanh cong (dienpccc, don gian nhat)
# ---------------------------------------------------------------------------
def test_dienpccc_success_returns_200_with_so_hieu_ban_ve_and_ho_so_info(client):
    token, _ = _register_login_and_grant(client, email="aihoread6@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["so_hieu_ban_ve"] == "E-01"
    assert data["provider"] == "fake"
    assert data["ho_so"]["session_id"] == session_id
    assert data["ho_so"]["files_used"] == 1
    assert data["ho_so"]["forms_used"] == 1
    assert data["ho_so"]["max_files"] == 5
    assert data["ho_so"]["max_forms"] == 7


# ---------------------------------------------------------------------------
# Partial result chua chay nuoc (ccnuoc): 1 trong 3 mau loi, 2 mau con lai van
# thanh cong - phai tra ve 200 voi ket qua rieng phan, khong sap ca request.
# ---------------------------------------------------------------------------
def test_ccnuoc_partial_result_when_one_form_fails(client):
    token, _ = _register_login_and_grant(client, email="aihoread7@pccc.local")
    session_id = _open_session(client, token)

    def fake_generate(system_prompt):
        if "B5" in system_prompt:
            raise ConnectionError("mat ket noi luc doc mau B5")
        loai = "tram_bom" if "B3" in system_prompt else "chua_chay_tu_dong"
        rows = mdc_filler.load_criteria_rows(loai)
        return json.dumps({
            "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
            "tong_ket": "ok",
            "kien_nghi": EMPTY_KIEN_NGHI,
            "so_hieu_ban_ve": "N-01",
        })

    provider = FakeProvider(fn=fake_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id, path="/api/aiho/read-ccnuoc")

    assert resp.status_code == 200  # KHONG sap ca request vi 1 mau loi
    data = resp.get_json()
    forms = data["forms"]
    assert "error" in forms["hong_nuoc"]
    assert "items" in forms["tram_bom"] and forms["tram_bom"]["items"]
    assert "items" in forms["chua_chay_tu_dong"] and forms["chua_chay_tu_dong"]["items"]
    assert "mat ket noi" in data["tong_ket"]


def test_ccnuoc_partial_result_mdc_files_flag_failed_form(client):
    token, _ = _register_login_and_grant(client, email="aihoread8@pccc.local")
    session_id = _open_session(client, token)

    def fake_generate(system_prompt):
        if "B5" in system_prompt:
            raise ConnectionError("mat ket noi")
        loai = "tram_bom" if "B3" in system_prompt else "chua_chay_tu_dong"
        rows = mdc_filler.load_criteria_rows(loai)
        return json.dumps({
            "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
            "tong_ket": "ok",
            "kien_nghi": EMPTY_KIEN_NGHI,
            "so_hieu_ban_ve": "N-01",
        })

    provider = FakeProvider(fn=fake_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id, path="/api/aiho/read-ccnuoc", extra_form={"outputs": "mdc"})

    assert resp.status_code == 200
    files = resp.get_json()["mdc_docx_files"]
    by_loai = {f["loai"]: f for f in files}
    assert "error" in by_loai["hong_nuoc"]
    assert "base64" in by_loai["tram_bom"]
    assert "base64" in by_loai["chua_chay_tu_dong"]
