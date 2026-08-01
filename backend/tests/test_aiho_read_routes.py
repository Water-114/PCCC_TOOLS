"""Batch 4 — gate kiểm tra còn thiếu cho các route AI đọc bản vẽ thật
(/api/aiho/read-baochay, read-dienpccc, read-ccnuoc): "Test không có API key,
provider timeout, quota exhausted, partial result chữa cháy nước" (đúng câu
chữ trong docs/02-implementation-batches.md mục Batch 4). Trước sub-bước 2
CHƯA có test nào cho các route này — file này lấp khoảng trống đó.

KHÔNG gọi AI thật — mock app.routes.aiho.get_provider hoàn toàn."""

import io
import json
from unittest.mock import patch

import pytest

from app.providers.base import GenerationResult, ProviderNotConfigured
from app.providers.resilience import CircuitBreakerOpen
from app.services import mdc_filler

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

EMPTY_KIEN_NGHI = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}


def _register_and_login(client, email="aihoread@pccc.local", password="matkhau123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.get_json()["token"]


def _upload(client, token, path="/api/aiho/read-dienpccc", filename="drawing.png"):
    return client.post(
        path,
        data={"file": (io.BytesIO(PNG_BYTES), filename)},
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
    token = _register_and_login(client)
    provider = FakeProvider(exc=ProviderNotConfigured("Chưa cấu hình ANTHROPIC_API_KEY."))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token)
    assert resp.status_code == 503
    assert "ANTHROPIC_API_KEY" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# Provider timeout / loi ha tang - khong duoc lo chi tiet exception ra client
# ---------------------------------------------------------------------------
def test_provider_timeout_returns_502_without_leaking_internals(client):
    token = _register_and_login(client, email="aihoread2@pccc.local")
    provider = FakeProvider(exc=TimeoutError("connection timed out after 300s to internal-host:443"))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token)
    assert resp.status_code == 502
    error = resp.get_json()["error"]
    assert "internal-host" not in error  # khong lo chi tiet ha tang that
    assert "thử lại sau" in error


def test_circuit_breaker_open_returns_502_with_breaker_message(client):
    token = _register_and_login(client, email="aihoread3@pccc.local")
    provider = FakeProvider(exc=CircuitBreakerOpen("Provider 'fake' vừa lỗi kết nối 3 lần liên tiếp — tạm ngừng gọi thêm khoảng 60 giây."))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token)
    assert resp.status_code == 502
    assert "tạm ngừng gọi thêm" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# Quota exhausted
# ---------------------------------------------------------------------------
def test_quota_exhausted_returns_429_without_calling_ai_again(client):
    token = _register_and_login(client, email="aihoread4@pccc.local")
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        for _ in range(5):  # AIHO_DAILY_QUOTA mac dinh = 5
            resp = _upload(client, token)
            assert resp.status_code == 200
        resp = _upload(client, token)
    assert resp.status_code == 429
    data = resp.get_json()
    assert data["quota"]["remaining_today"] == 0
    assert "Đã dùng hết" in data["error"]


# ---------------------------------------------------------------------------
# Thanh cong (dienpccc, don gian nhat)
# ---------------------------------------------------------------------------
def test_dienpccc_success_returns_200_with_so_hieu_ban_ve_and_quota(client):
    token = _register_and_login(client, email="aihoread5@pccc.local")
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["so_hieu_ban_ve"] == "E-01"
    assert data["quota"]["used_today"] == 1
    assert data["provider"] == "fake"


# ---------------------------------------------------------------------------
# Partial result chua chay nuoc (ccnuoc): 1 trong 3 mau loi, 2 mau con lai van
# thanh cong - phai tra ve 200 voi ket qua rieng phan, khong sap ca request.
# ---------------------------------------------------------------------------
def test_ccnuoc_partial_result_when_one_form_fails(client):
    token = _register_and_login(client, email="aihoread6@pccc.local")

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
        resp = _upload(client, token, path="/api/aiho/read-ccnuoc")

    assert resp.status_code == 200  # KHONG sap ca request vi 1 mau loi
    data = resp.get_json()
    forms = data["forms"]
    assert "error" in forms["hong_nuoc"]
    assert "items" in forms["tram_bom"] and forms["tram_bom"]["items"]
    assert "items" in forms["chua_chay_tu_dong"] and forms["chua_chay_tu_dong"]["items"]
    assert "mat ket noi" in data["tong_ket"]


def test_ccnuoc_partial_result_mdc_files_flag_failed_form(client):
    token = _register_and_login(client, email="aihoread7@pccc.local")

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
        resp = client.post(
            "/api/aiho/read-ccnuoc",
            data={"file": (io.BytesIO(PNG_BYTES), "drawing.png"), "outputs": "mdc"},
            headers={"Authorization": f"Bearer {token}"},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 200
    files = resp.get_json()["mdc_docx_files"]
    by_loai = {f["loai"]: f for f in files}
    assert "error" in by_loai["hong_nuoc"]
    assert "base64" in by_loai["tram_bom"]
    assert "base64" in by_loai["chua_chay_tu_dong"]


def test_missing_api_key_still_counts_as_one_used_reservation(client):
    """Hanh vi co san tu Batch 1 (khong doi o day): cho da duoc "giu truoc" (pending)
    NGAY LUC request bat dau (truoc khi biet provider co cau hinh hay khong), roi
    finalize thanh 'error' - count_usage_today tinh ca 'error' la 1 luot da dung,
    dung 1 lan, khong am - test nay chi khoa lai dung 1 con so, khong doi thiet ke."""
    from app.models import AIHO_API_NAME, count_usage_today

    token = _register_and_login(client, email="aihoread8@pccc.local")
    user_id = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).get_json()["user"]["id"]

    provider = FakeProvider(exc=ProviderNotConfigured("chua cau hinh"))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        _upload(client, token)

    used = count_usage_today(user_id, AIHO_API_NAME)
    assert used == 1
