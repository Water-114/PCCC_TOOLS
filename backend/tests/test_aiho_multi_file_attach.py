"""Batch 5A Pha 1 - dinh NHIEU file (toi da 3) cho 1 hang muc trong 1 lan goi
AI: /api/aiho/read-dienpccc (dai dien cho 9 route di qua _handle_read_request()).

Kiem tra: (1) qua 3 file bi tu choi 400, (2) tong dung luong PDF/anh vuot
SINGLE_MAX_BYTES_* (tinh TONG, khong phai tung file) bi tu choi 400, (3) dinh
2-3 file van chi tru DUNG 1/5 file + 1/7 form trong phien (khong tru theo so
file), (4) provider that su nhan du CA N file trong 1 request (generate_with_documents).

KHONG goi AI that - mock app.routes.aiho.get_provider hoan toan."""

import io
import json
from unittest.mock import patch

from app.models import HoSoSession
from app.providers.base import GenerationResult
from app.services import credits, mdc_filler

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF_HEADER = b"%PDF-1.4\n"

EMPTY_KIEN_NGHI = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}


def _register_login_and_grant(client, email="multifile@pccc.local", password="matkhau123", amount=5):
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
    name = "fake"
    model = "fake-model"

    def __init__(self, fn):
        self.fn = fn
        self.calls = []  # list[int] - so content_blocks nhan duoc moi lan goi

    def generate_with_documents(self, system_prompt, content_blocks):
        self.calls.append(len(content_blocks))
        return GenerationResult(text=self.fn(system_prompt))


def _dienpccc_payload():
    rows = mdc_filler.load_criteria_rows("dien_pccc")
    return json.dumps({
        "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
        "so_hieu_ban_ve": "E-01",
    })


def _upload_files(client, token, session_id, files, extra_form=None):
    """files: list[(bytes, filename)] - upload tat ca duoi CUNG 1 field 'files'."""
    data = {"session_id": str(session_id)}
    if extra_form:
        data.update(extra_form)
    data["files"] = [(io.BytesIO(content), filename) for content, filename in files]
    return client.post(
        "/api/aiho/read-dienpccc",
        data=data,
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


def test_2_files_accepted_and_provider_receives_both(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_files(client, token, session_id, [(PNG_BYTES, "a.png"), (PNG_BYTES, "b.png")])
    assert resp.status_code == 200, resp.get_json()
    assert provider.calls == [2]


def test_3_files_accepted_at_the_cap(client):
    token, _ = _register_login_and_grant(client, email="multifile3@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_files(client, token, session_id, [(PNG_BYTES, "a.png"), (PNG_BYTES, "b.png"), (PNG_BYTES, "c.png")])
    assert resp.status_code == 200, resp.get_json()
    assert provider.calls == [3]


def test_4_files_rejected_over_cap(client):
    token, _ = _register_login_and_grant(client, email="multifile4@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    files = [(PNG_BYTES, f"f{i}.png") for i in range(4)]
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_files(client, token, session_id, files)
    assert resp.status_code == 400
    assert "tối đa 3 file" in resp.get_json()["error"]
    assert provider.calls == []  # khong duoc goi AI khi da bi chan o buoc validate file


def test_no_files_field_returns_400(client):
    token, _ = _register_login_and_grant(client, email="multifilenone@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = client.post(
            "/api/aiho/read-dienpccc",
            data={"session_id": str(session_id)},
            headers={"Authorization": f"Bearer {token}"},
            content_type="multipart/form-data",
        )
    assert resp.status_code == 400
    assert "files" in resp.get_json()["error"]


def test_multi_file_only_consumes_1_of_5_file_slot_and_1_of_7_form_slot(client):
    """Chot voi owner: dinh 2-3 file van chi tru DUNG 1/5 file + 1 form - khong
    tru theo so file dinh kem (xem ho_so_session.reserve_slot(session, 1, forms_per_call)
    trong _handle_read_request(), khong doi du dinh may file)."""
    token, _ = _register_login_and_grant(client, email="multifileslot@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_files(client, token, session_id, [(PNG_BYTES, "a.png"), (PNG_BYTES, "b.png"), (PNG_BYTES, "c.png")])
    assert resp.status_code == 200, resp.get_json()

    session = HoSoSession.query.get(session_id)
    assert session.files_used == 1
    assert session.forms_used == 1


def test_total_pdf_size_over_limit_rejected_even_if_each_file_under_limit(client):
    """Gioi han SINGLE_MAX_BYTES_PDF (22MB) tinh TONG nhieu file trong CUNG 1
    request, khong phai tung file rieng - 2 file PDF ~15MB moi file (duoi han
    muc tung file) nhung TONG ~30MB > 22MB phai bi chan o backend, KHONG duoc
    gui thang len AI."""
    token, _ = _register_login_and_grant(client, email="multifilepdf@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    big_pdf_1 = PDF_HEADER + b"\x00" * (15 * 1024 * 1024)
    big_pdf_2 = PDF_HEADER + b"\x00" * (15 * 1024 * 1024)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_files(client, token, session_id, [(big_pdf_1, "a.pdf"), (big_pdf_2, "b.pdf")])
    assert resp.status_code == 400
    assert "Tổng dung lượng" in resp.get_json()["error"] and "PDF" in resp.get_json()["error"]
    assert provider.calls == []


def test_total_image_size_over_limit_rejected(client):
    """Tuong tu nhung cho anh - gioi han SINGLE_MAX_BYTES_IMAGE (7MB) tinh TONG."""
    token, _ = _register_login_and_grant(client, email="multifileimg@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=lambda sp: _dienpccc_payload())
    big_png_1 = PNG_BYTES + b"\x00" * (4 * 1024 * 1024)
    big_png_2 = PNG_BYTES + b"\x00" * (4 * 1024 * 1024)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_files(client, token, session_id, [(big_png_1, "a.png"), (big_png_2, "b.png")])
    assert resp.status_code == 400
    assert "Tổng dung lượng" in resp.get_json()["error"] and "ảnh" in resp.get_json()["error"]
    assert provider.calls == []
