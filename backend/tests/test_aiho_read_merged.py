"""Batch 5A sub-bước 5 — "Đính 1 bản vẽ, AI tự nhận diện nhiều hạng mục"
(/api/aiho/read-merged + /api/aiho/read-merged/confirm). KHÔNG gọi AI thật —
mock app.routes.aiho.get_provider hoàn toàn, giống test_aiho_read_routes.py.

Trọng tâm test: (1) cơ chế xác nhận 2 giai đoạn (giữ chỗ file trước, form sau
khi confirm), (2) forms_needed tính đúng theo CATEGORY_FORMS_PER_CALL (không
phải 1 form/hạng mục đồng loạt), (3) confirm không cho xác nhận hạng mục ngoài
detected_categories, (4) confirm re-validate dữ liệu client gửi lại (không tin
mù), (5) giới hạn file phân theo ảnh/PDF, (6) quy_mo bị loại khỏi danh sách có
thể phát hiện khi phiên đã có sẵn + được lưu khi phát hiện mới, (7) dùng chung
hạn mức AIHO_DAILY_QUOTA, (8) forms cap-exceeded ở bước confirm không làm
lệch forms_used (atomic, giống test reserve_slot gốc)."""

import io
import json
from unittest.mock import patch

from app.extensions import db
from app.models import HoSoSession, User
from app.providers.base import GenerationResult, ProviderNotConfigured
from app.services import credits, mdc_filler, quy_mo_store

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF_HEADER = b"%PDF-1.4\n"

EMPTY_KIEN_NGHI = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}


def _register_login_and_grant(client, email="aihomerged@pccc.local", password="matkhau123", amount=5):
    client.post("/api/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    data = resp.get_json()
    token, user_id = data["token"], data["user"]["id"]
    if amount:
        credits.grant_credits(user_id, amount, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="test setup")
    return token, user_id


def _bump_daily_quota(email, value):
    user = User.query.filter_by(email=email).first()
    user.daily_quota = value
    db.session.commit()


def _open_session(client, token):
    resp = client.post("/api/aiho/session/open", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["session_id"]


def _upload_merged(client, token, session_id, data=PNG_BYTES, filename="drawing.png"):
    form = {"file": (io.BytesIO(data), filename), "session_id": str(session_id)}
    return client.post(
        "/api/aiho/read-merged",
        data=form,
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


def _confirm(client, token, session_id, detection, selected_categories):
    return client.post(
        "/api/aiho/read-merged/confirm",
        json={"session_id": session_id, "detection": detection, "selected_categories": selected_categories},
        headers={"Authorization": f"Bearer {token}"},
    )


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


def _items_for(loai):
    rows = mdc_filler.load_criteria_rows(loai)
    return [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows]


def _merged_payload(detected, so_hieu="DWG-01"):
    data = {"detected_categories": detected, "so_hieu_ban_ve": so_hieu}
    if "dienpccc" in detected:
        data["dienpccc"] = {"items": _items_for("dien_pccc"), "tong_ket": "ok", "kien_nghi": EMPTY_KIEN_NGHI}
    if "baochay" in detected:
        data["baochay"] = {
            "loai_he_thong": "thuong", "ly_do_nhan_dien": "co zone",
            "items": _items_for("thuong"), "tong_ket": "ok", "kien_nghi": EMPTY_KIEN_NGHI,
        }
    if "ccnuoc" in detected:
        forms = {}
        for loai in ("tram_bom", "hong_nuoc", "chua_chay_tu_dong"):
            d = {"items": _items_for(loai), "tong_ket": "ok", "kien_nghi": EMPTY_KIEN_NGHI}
            if loai == "chua_chay_tu_dong":
                d["co_thiet_ke_tu_dong"] = True
            forms[loai] = d
        data["ccnuoc"] = {"forms": forms}
    if "densucco" in detected:
        forms = {loai: {"items": _items_for(loai), "tong_ket": "ok", "kien_nghi": EMPTY_KIEN_NGHI}
                 for loai in ("binh_chua_chay", "den_su_co")}
        data["densucco"] = {"forms": forms}
    if "quy_mo" in detected:
        data["quy_mo"] = {
            "quy_mo": {"occ": "khachsan", "floors": 5},
            "bang_a2_bao_chay": "x", "bang_a4_bao_chay": "x",
            "bang_a2_sprinkler": "x", "bang_a4_sprinkler": "x",
        }
    return json.dumps(data)


def _fake_provider_for(detected, so_hieu="DWG-01"):
    return FakeProvider(fn=lambda system_prompt: _merged_payload(detected, so_hieu))


# ---------------------------------------------------------------------------
# /read-merged: chi giu cho FILE, KHONG giu cho FORM
# ---------------------------------------------------------------------------
def test_read_merged_detects_subset_and_does_not_reserve_forms_yet(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = _fake_provider_for(["dienpccc"])
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_merged(client, token, session_id)
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["detection"]["detected_categories"] == ["dienpccc"]
    assert body["forms_needed"] == 1
    assert body["ho_so"]["files_used"] == 1
    assert body["ho_so"]["forms_used"] == 0  # CHUA giu cho form o buoc nay

    session = HoSoSession.query.get(session_id)
    assert session.files_used == 1
    assert session.forms_used == 0


def test_read_merged_empty_detection_still_counts_file_and_ai_call(client):
    """Ban ve khong thuoc hang muc nao (detected_categories rong) van la 1 lan
    goi AI that su (tinh vao han muc/ngay, tinh 1 file) - chi khong co gi de
    xac nhan o buoc confirm."""
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = _fake_provider_for([])
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_merged(client, token, session_id)
    assert resp.status_code == 200
    assert resp.get_json()["detection"]["detected_categories"] == []
    assert resp.get_json()["forms_needed"] == 0


# ---------------------------------------------------------------------------
# forms_needed dung theo CATEGORY_FORMS_PER_CALL (ccnuoc=3, densucco=2, con lai=1)
# ---------------------------------------------------------------------------
def test_confirm_ccnuoc_reserves_3_forms_and_returns_mdc_for_3_submaus(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = _fake_provider_for(["ccnuoc"])
    with patch("app.routes.aiho.get_provider", return_value=provider):
        detection = _upload_merged(client, token, session_id).get_json()["detection"]

    resp = _confirm(client, token, session_id, detection, ["ccnuoc"])
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["ho_so"]["forms_used"] == 3
    files = body["results"]["ccnuoc"]["mdc_docx_files"]
    assert {f["loai"] for f in files} == {"tram_bom", "hong_nuoc", "chua_chay_tu_dong"}
    assert all(f.get("base64") for f in files)

    session = HoSoSession.query.get(session_id)
    assert session.forms_used == 3
    assert session.files_used == 1  # khong doi them o buoc confirm


def test_confirm_multiple_categories_sums_forms_per_call_correctly(client):
    """dienpccc(1) + densucco(2) = 3 form - khong phai 2 (1 form/hang muc)."""
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = _fake_provider_for(["dienpccc", "densucco"])
    with patch("app.routes.aiho.get_provider", return_value=provider):
        detection = _upload_merged(client, token, session_id).get_json()["detection"]

    resp = _confirm(client, token, session_id, detection, ["dienpccc", "densucco"])
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["ho_so"]["forms_used"] == 3
    assert set(resp.get_json()["results"].keys()) == {"dienpccc", "densucco"}


# ---------------------------------------------------------------------------
# Chon 1 phan (bo bot hang muc) truoc khi xac nhan - chi giu cho dung phan da chon
# ---------------------------------------------------------------------------
def test_confirm_partial_selection_only_reserves_selected_categories(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = _fake_provider_for(["dienpccc", "baochay"])
    with patch("app.routes.aiho.get_provider", return_value=provider):
        detection = _upload_merged(client, token, session_id).get_json()["detection"]

    resp = _confirm(client, token, session_id, detection, ["dienpccc"])  # bo baochay
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["ho_so"]["forms_used"] == 1
    assert list(resp.get_json()["results"].keys()) == ["dienpccc"]


def test_confirm_rejects_category_not_in_detected_categories(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = _fake_provider_for(["dienpccc"])
    with patch("app.routes.aiho.get_provider", return_value=provider):
        detection = _upload_merged(client, token, session_id).get_json()["detection"]

    resp = _confirm(client, token, session_id, detection, ["baochay"])  # AI khong phat hien baochay
    assert resp.status_code == 400
    assert "baochay" in resp.get_json()["error"]

    session = HoSoSession.query.get(session_id)
    assert session.forms_used == 0  # khong bi giu cho nham


# ---------------------------------------------------------------------------
# Confirm re-validate du lieu client gui lai - khong tin mu
# ---------------------------------------------------------------------------
def test_confirm_rejects_tampered_detection_missing_id(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    provider = _fake_provider_for(["dienpccc"])
    with patch("app.routes.aiho.get_provider", return_value=provider):
        detection = _upload_merged(client, token, session_id).get_json()["detection"]

    # gia mao: xoa bot 1 item khoi danh sach da duoc AI tra ve (vd bug frontend/
    # can thiep thu cong) - confirm phai phat hien va tu choi, khong am tham
    # xuat file MDC thieu tieu chi.
    detection["dienpccc"]["items"] = detection["dienpccc"]["items"][:-1]
    resp = _confirm(client, token, session_id, detection, ["dienpccc"])
    assert resp.status_code == 400
    assert "hợp lệ" in resp.get_json()["error"] or "id" in resp.get_json()["error"]

    session = HoSoSession.query.get(session_id)
    assert session.forms_used == 0


# ---------------------------------------------------------------------------
# Gioi han file rieng cho tinh nang nay - phan theo anh/PDF (khac 15MB dung chung)
# ---------------------------------------------------------------------------
def test_read_merged_image_over_7mb_rejected(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    big_png = PNG_BYTES + b"\x00" * (7 * 1024 * 1024 + 100)
    provider = _fake_provider_for(["dienpccc"])
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_merged(client, token, session_id, data=big_png)
    assert resp.status_code == 400
    assert "ảnh" in resp.get_json()["error"] and "7" in resp.get_json()["error"]


def test_read_merged_pdf_up_to_20mb_accepted_but_over_rejected(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)

    ok_pdf = PDF_HEADER + b"\x00" * (10 * 1024 * 1024)  # duoi 20MB - phai qua duoc buoc kich thuoc
    provider = _fake_provider_for(["dienpccc"])
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp_ok = _upload_merged(client, token, session_id, data=ok_pdf, filename="drawing.pdf")
    assert resp_ok.status_code == 200, resp_ok.get_json()

    session_id_2 = _open_session(client, token)
    big_pdf = PDF_HEADER + b"\x00" * (20 * 1024 * 1024 + 100)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp_big = _upload_merged(client, token, session_id_2, data=big_pdf, filename="drawing.pdf")
    assert resp_big.status_code == 400
    assert "PDF" in resp_big.get_json()["error"] and "20" in resp_big.get_json()["error"]


# ---------------------------------------------------------------------------
# Quy mo: loai khoi danh sach co the phat hien khi phien DA co san; duoc luu
# khi AI moi phat hien (phien CHUA co)
# ---------------------------------------------------------------------------
def test_quy_mo_excluded_from_prompt_when_session_already_has_it(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    quy_mo_store.save_quy_mo(session_id, {"occ": "khachsan", "floors": 5}, source="manual")

    captured = {}

    def fn(system_prompt):
        captured["prompt"] = system_prompt
        return _merged_payload(["dienpccc"])

    provider = FakeProvider(fn=fn)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_merged(client, token, session_id)
    assert resp.status_code == 200, resp.get_json()
    assert 'id="quy_mo"' not in captured["prompt"]
    assert "QUY MÔ CÔNG TRÌNH ĐÃ XÁC NHẬN" in captured["prompt"]  # van duoc dung lam ngu canh


def test_confirm_quy_mo_persists_to_quy_mo_store_when_newly_detected(client):
    token, _ = _register_login_and_grant(client)
    session_id = _open_session(client, token)
    assert quy_mo_store.get_quy_mo(session_id) is None

    provider = _fake_provider_for(["quy_mo"])
    with patch("app.routes.aiho.get_provider", return_value=provider):
        detection = _upload_merged(client, token, session_id).get_json()["detection"]

    resp = _confirm(client, token, session_id, detection, ["quy_mo"])
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["results"]["quy_mo"]["mdc_docx_files"][0].get("base64")

    saved = quy_mo_store.get_quy_mo(session_id)
    assert saved is not None
    assert saved["occ"] == "khachsan"


# ---------------------------------------------------------------------------
# Dung chung han muc goi AI/ngay (AIHO_API_NAME) voi 5 route rieng le
# ---------------------------------------------------------------------------
def test_read_merged_counts_toward_shared_daily_quota(client):
    token, _ = _register_login_and_grant(client, email="aihomergedquota@pccc.local", amount=10)
    provider = _fake_provider_for(["dienpccc"])
    with patch("app.routes.aiho.get_provider", return_value=provider):
        for _ in range(5):
            sid = _open_session(client, token)
            resp = _upload_merged(client, token, sid)
            assert resp.status_code == 200, resp.get_json()
        sid6 = _open_session(client, token)
        resp6 = _upload_merged(client, token, sid6)
    assert resp6.status_code == 429


# ---------------------------------------------------------------------------
# Vuot han muc form o BUOC CONFIRM - khong lam lech forms_used (atomic)
# ---------------------------------------------------------------------------
def test_confirm_forms_cap_exceeded_leaves_forms_used_unchanged(client):
    token, _ = _register_login_and_grant(client, email="aihomergedcap@pccc.local")
    _bump_daily_quota("aihomergedcap@pccc.local", 20)
    session_id = _open_session(client, token)

    # Dung het 6/7 form bang 1 lan goi rieng le (dienpccc, forms_per_call=1) x 6 -
    # khong the goi read-dienpccc 6 lan (moi lan la 1 file, gioi han 5 file/phien).
    # Don gian hon: chiem truoc forms_used=6 bang cach mo phien roi goi thang
    # ho_so_session.reserve_slot (dung ham that, khong gia lap truong).
    from app.services import ho_so_session
    session = HoSoSession.query.get(session_id)
    ho_so_session.reserve_slot(session, 0, 6)  # con lai 1/7 form, 5/5 file van con nguyen

    provider = _fake_provider_for(["ccnuoc"])  # can 3 form nhung chi con 1
    with patch("app.routes.aiho.get_provider", return_value=provider):
        detection = _upload_merged(client, token, session_id).get_json()["detection"]

    resp = _confirm(client, token, session_id, detection, ["ccnuoc"])
    assert resp.status_code == 400

    session = HoSoSession.query.get(session_id)
    assert session.forms_used == 6  # khong tang len 9, khong giam - dung nguyen


# ---------------------------------------------------------------------------
# Loi provider - 502 + van ghi UsageLog (khong lo chi tiet exception)
# ---------------------------------------------------------------------------
def test_read_merged_provider_error_returns_502_and_logs_usage(client):
    from app.models import UsageLog

    token, _ = _register_login_and_grant(client, email="aihomergederr@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(exc=TimeoutError("connection timed out to internal-host:443"))
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_merged(client, token, session_id)
    assert resp.status_code == 502
    assert "internal-host" not in resp.get_json()["error"]

    user = User.query.filter_by(email="aihomergederr@pccc.local").first()
    logs = UsageLog.query.filter_by(user_id=user.id).all()
    assert len(logs) == 1 and logs[0].status == "error"
