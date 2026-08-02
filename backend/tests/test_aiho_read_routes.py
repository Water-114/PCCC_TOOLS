"""Batch 4 + Batch 5A sub-bước 2 — gate kiểm tra cho các route AI đọc bản vẽ
thật (/api/aiho/read-baochay, read-dienpccc, read-ccnuoc, read-densucco):
không có API key, provider timeout, hết Bộ hồ sơ, partial result chữa cháy
nước/đèn sự cố+bình chữa cháy — CỘNG các gate riêng của mô hình "phiên Bộ hồ
sơ" (session_id thiếu/sai/không thuộc user/đã đóng, vượt giới hạn 5 file/7
form).

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


def _ccnuoc_payload_for(loai, so_hieu="N-01"):
    """loai: 'tram_bom' (B3) | 'hong_nuoc' (B5) | 'chua_chay_tu_dong' (B6).
    B6 phai co them 'co_thiet_ke_tu_dong' (field moi, bat buoc, khong default) -
    mac dinh True o day (kich ban "co thiet ke sprinkler, du thong tin") vi day
    la payload dung cho cac test hien co, gia lap AI tra loi day du/thanh cong."""
    rows = mdc_filler.load_criteria_rows(loai)
    payload = {
        "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
        "so_hieu_ban_ve": so_hieu,
    }
    if loai == "chua_chay_tu_dong":
        payload["co_thiet_ke_tu_dong"] = True
    return json.dumps(payload)


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
        return _ccnuoc_payload_for(loai)

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
        return _ccnuoc_payload_for(loai)

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
        return _ccnuoc_payload_for(loai)

    provider = FakeProvider(fn=fake_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id, path="/api/aiho/read-ccnuoc", extra_form={"outputs": "mdc"})

    assert resp.status_code == 200
    files = resp.get_json()["mdc_docx_files"]
    by_loai = {f["loai"]: f for f in files}
    assert "error" in by_loai["hong_nuoc"]
    assert "base64" in by_loai["tram_bom"]
    assert "base64" in by_loai["chua_chay_tu_dong"]


# ---------------------------------------------------------------------------
# Chi dao nghiep vu cua owner: B6 chi xuat khi AI xac dinh cong trinh THAT SU
# thiet ke he sprinkler/drencher (co_thiet_ke_tu_dong). Neu khong: chi con
# B3+B5, khong sinh MDC B6, khong cong kien nghi tu B6.
# ---------------------------------------------------------------------------
def _b6_not_designed_payload():
    rows = mdc_filler.load_criteria_rows("chua_chay_tu_dong")
    return json.dumps({
        "co_thiet_ke_tu_dong": False,
        "items": [
            {"id": r["id"], "noi_dung_thiet_ke": "Công trình không thiết kế hệ thống chữa cháy tự động bằng nước/bọt (sprinkler/drencher).", "ket_luan": "dat"}
            for r in rows
        ],
        "tong_ket": "Công trình không thiết kế hệ thống chữa cháy tự động bằng nước/bọt (sprinkler/drencher).",
        "kien_nghi": EMPTY_KIEN_NGHI,
        "so_hieu_ban_ve": "ND-01",
    })


def test_ccnuoc_b6_not_designed_excludes_b6_from_forms_and_kien_nghi(client):
    token, _ = _register_login_and_grant(client, email="aihoread14@pccc.local")
    session_id = _open_session(client, token)

    def fake_generate(system_prompt):
        if "B6" in system_prompt:
            return _b6_not_designed_payload()
        loai = "tram_bom" if "B3" in system_prompt else "hong_nuoc"
        return _ccnuoc_payload_for(loai)

    provider = FakeProvider(fn=fake_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id, path="/api/aiho/read-ccnuoc", extra_form={"outputs": "mdc"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data["forms"].keys()) == {"tram_bom", "hong_nuoc"}  # KHONG con "chua_chay_tu_dong"
    assert "Công trình không thiết kế hệ thống chữa cháy tự động" in data["tong_ket"]
    for group in data["kien_nghi"].values():
        assert group == []  # khong co kien nghi nao tu B6 (hay tu B3/B5 vi ca 2 deu "dat")

    mdc_loai = {f["loai"] for f in data["mdc_docx_files"]}
    assert mdc_loai == {"tram_bom", "hong_nuoc"}  # khong sinh MDC B6


def test_ccnuoc_b6_designed_still_includes_b6_as_before(client):
    """Regression: neu AI xac dinh co thiet ke sprinkler, hanh vi giu nguyen
    nhu truoc (van xuat du 3 form)."""
    token, _ = _register_login_and_grant(client, email="aihoread15@pccc.local")
    session_id = _open_session(client, token)

    def fake_generate(system_prompt):
        loai = "tram_bom" if "B3" in system_prompt else ("hong_nuoc" if "B5" in system_prompt else "chua_chay_tu_dong")
        return _ccnuoc_payload_for(loai)

    provider = FakeProvider(fn=fake_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id, path="/api/aiho/read-ccnuoc")

    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data["forms"].keys()) == {"tram_bom", "hong_nuoc", "chua_chay_tu_dong"}


def test_ccnuoc_b6_missing_co_thiet_ke_field_triggers_retry_repair_then_fails(client):
    """AI khong tra field co_thiet_ke_tu_dong bat buoc -> SchemaValidationError
    -> retry-repair 1 lan -> van thieu -> AIReaderError cho rieng B6 (B3/B5 van
    thanh cong, dung dung co che "partial result" da co)."""
    token, _ = _register_login_and_grant(client, email="aihoread16@pccc.local")
    session_id = _open_session(client, token)

    def fake_generate(system_prompt):
        if "B6" in system_prompt:
            rows = mdc_filler.load_criteria_rows("chua_chay_tu_dong")
            return json.dumps({  # thieu "co_thiet_ke_tu_dong" - field bat buoc
                "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
                "tong_ket": "ok",
                "kien_nghi": EMPTY_KIEN_NGHI,
                "so_hieu_ban_ve": "N-01",
            })
        loai = "tram_bom" if "B3" in system_prompt else "hong_nuoc"
        return _ccnuoc_payload_for(loai)

    provider = FakeProvider(fn=fake_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id, path="/api/aiho/read-ccnuoc")

    assert resp.status_code == 200  # van tra 200 - loi B6 duoc coi la partial result
    data = resp.get_json()
    forms = data["forms"]
    assert "items" in forms["tram_bom"] and "items" in forms["hong_nuoc"]
    assert "error" in forms["chua_chay_tu_dong"]  # loi validate schema (thieu field bat buoc), khac voi truong hop "khong thiet ke"


# ---------------------------------------------------------------------------
# Den su co / binh chua chay (densucco, MDC B12+B13) - gop 2 mau tren 1 ban ve,
# theo dung khuon ccnuoc (forms_per_call=2 thay vi 3).
# ---------------------------------------------------------------------------
def _fake_densucco_generate(system_prompt):
    loai = "binh_chua_chay" if "B12" in system_prompt else "den_su_co"
    rows = mdc_filler.load_criteria_rows(loai)
    return json.dumps({
        "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
        "so_hieu_ban_ve": "DSC-01",
    })


def test_densucco_success_returns_200_with_2_forms(client):
    token, _ = _register_login_and_grant(client, email="aihoread9@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=_fake_densucco_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id, path="/api/aiho/read-densucco")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["so_hieu_ban_ve"] == "DSC-01"
    assert set(data["forms"].keys()) == {"binh_chua_chay", "den_su_co"}
    assert data["forms"]["binh_chua_chay"]["items"]
    assert data["forms"]["den_su_co"]["items"]
    assert data["ho_so"]["files_used"] == 1
    assert data["ho_so"]["forms_used"] == 2  # B12+B13 = 2 form, khong phai 3 nhu ccnuoc


def test_densucco_partial_result_when_one_form_fails(client):
    token, _ = _register_login_and_grant(client, email="aihoread10@pccc.local")
    session_id = _open_session(client, token)

    def fake_generate(system_prompt):
        if "B13" in system_prompt:
            raise ConnectionError("mat ket noi luc doc mau B13")
        rows = mdc_filler.load_criteria_rows("binh_chua_chay")
        return json.dumps({
            "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
            "tong_ket": "ok",
            "kien_nghi": EMPTY_KIEN_NGHI,
            "so_hieu_ban_ve": "DSC-02",
        })

    provider = FakeProvider(fn=fake_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id, path="/api/aiho/read-densucco")

    assert resp.status_code == 200  # KHONG sap ca request vi 1 mau loi
    data = resp.get_json()
    forms = data["forms"]
    assert "error" in forms["den_su_co"]
    assert "items" in forms["binh_chua_chay"] and forms["binh_chua_chay"]["items"]
    assert "mat ket noi" in data["tong_ket"]


def test_densucco_partial_result_mdc_files_flag_failed_form(client):
    token, _ = _register_login_and_grant(client, email="aihoread11@pccc.local")
    session_id = _open_session(client, token)

    def fake_generate(system_prompt):
        if "B13" in system_prompt:
            raise ConnectionError("mat ket noi")
        rows = mdc_filler.load_criteria_rows("binh_chua_chay")
        return json.dumps({
            "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
            "tong_ket": "ok",
            "kien_nghi": EMPTY_KIEN_NGHI,
            "so_hieu_ban_ve": "DSC-03",
        })

    provider = FakeProvider(fn=fake_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id, path="/api/aiho/read-densucco", extra_form={"outputs": "mdc"})

    assert resp.status_code == 200
    files = resp.get_json()["mdc_docx_files"]
    by_loai = {f["loai"]: f for f in files}
    assert "error" in by_loai["den_su_co"]
    assert "base64" in by_loai["binh_chua_chay"]


def test_densucco_form_cap_exceeded_returns_400(client):
    """densucco chiem 2 form/lan goi (B12+B13) - 4 lan = 8 form > gioi han 7."""
    token, _ = _register_login_and_grant(client, email="aihoread12@pccc.local")
    session_id = _open_session(client, token)
    provider = FakeProvider(fn=_fake_densucco_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        for i in range(3):  # 3 lan x 2 form = 6 form, van trong gioi han
            resp = _upload(client, token, session_id, path="/api/aiho/read-densucco", filename=f"f{i}.png")
            assert resp.status_code == 200
        resp = _upload(client, token, session_id, path="/api/aiho/read-densucco", filename="f3.png")  # 8 form - vuot 7
    assert resp.status_code == 400
    assert "7 form" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# Mo phong AI TUAN THU dung 2 huong dan dac biet moi (khong the test AI that
# tuan thu prompt hay khong - chi xac nhan CODE xu ly dung khi AI tra loi theo
# dung dinh dang da huong dan trong prompt).
# ---------------------------------------------------------------------------
def test_densucco_binh_bot_treo_absent_does_not_generate_bo_sung_kien_nghi(client):
    """Mo phong AI tuan thu huong dan: id=14,15 (binh bot treo) vang mat tren
    ban ve -> AI tra ve 'dat' (khong phai 'chua_the_hien') - dam bao code
    khong tu sinh kien nghi 'Bo sung' cho 2 id nay (vi ket_luan=dat khong bao
    gio sinh kien nghi, theo dung Buoc 2 cua prompt)."""
    token, _ = _register_login_and_grant(client, email="aihoread17@pccc.local")
    session_id = _open_session(client, token)

    def fake_generate(system_prompt):
        if "B12" in system_prompt:
            rows = mdc_filler.load_criteria_rows("binh_chua_chay")
            items = []
            for r in rows:
                if r["id"] in (14, 15):
                    items.append({"id": r["id"], "noi_dung_thiet_ke": "Không có thiết kế bình bột chữa cháy tự động loại treo", "ket_luan": "dat"})
                else:
                    items.append({"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"})
            return json.dumps({
                "items": items, "tong_ket": "ok", "kien_nghi": EMPTY_KIEN_NGHI, "so_hieu_ban_ve": "BB-01",
            })
        rows = mdc_filler.load_criteria_rows("den_su_co")
        return json.dumps({
            "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
            "tong_ket": "ok", "kien_nghi": EMPTY_KIEN_NGHI, "so_hieu_ban_ve": "BB-01",
        })

    provider = FakeProvider(fn=fake_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id, path="/api/aiho/read-densucco")

    assert resp.status_code == 200
    data = resp.get_json()
    binh_items = {i["id"]: i for i in data["forms"]["binh_chua_chay"]["items"]}
    assert binh_items[14]["ket_luan"] == "dat"
    assert binh_items[14]["noi_dung_thiet_ke"] == "Không có thiết kế bình bột chữa cháy tự động loại treo"
    for group in data["kien_nghi"].values():
        assert group == []  # khong co kien nghi "Bo sung" nao duoc sinh ra


def test_densucco_insufficient_scope_info_kien_nghi_flows_to_nhom_iv(client):
    """Mo phong AI tuan thu huong dan: id=28,29 (mat na loc doc) thieu thong
    tin quy mo -> AI tra 'chua_the_hien' + kien nghi xep vao nhom IV (theo
    dung huong dan moi) - xac nhan code KHONG ep kien nghi ve nhom I, chuyen
    dung nguyen vao response cuoi cung."""
    token, _ = _register_login_and_grant(client, email="aihoread18@pccc.local")
    session_id = _open_session(client, token)
    nhom_iv_cau = "Đối chiếu bổ sung hồ sơ quy mô công trình để xác định mặt nạ lọc độc và mặt nạ phòng độc cách ly có thuộc diện bắt buộc trang bị hay không (Căn cứ Phụ lục F QCVN 10:2025/BCA)."

    def fake_generate(system_prompt):
        if "B12" in system_prompt:
            rows = mdc_filler.load_criteria_rows("binh_chua_chay")
            items = []
            for r in rows:
                if r["id"] in (28, 29):
                    items.append({"id": r["id"], "noi_dung_thiet_ke": "Chưa đủ thông tin quy mô công trình (số tầng/khối tích/công năng) trên bản vẽ để xác định có thuộc diện trang bị hay không — cần đối chiếu thêm với hồ sơ quy mô công trình", "ket_luan": "chua_the_hien"})
                else:
                    items.append({"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"})
            return json.dumps({
                "items": items, "tong_ket": "ok",
                "kien_nghi": {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": [nhom_iv_cau]},
                "so_hieu_ban_ve": "MN-01",
            })
        rows = mdc_filler.load_criteria_rows("den_su_co")
        return json.dumps({
            "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
            "tong_ket": "ok", "kien_nghi": EMPTY_KIEN_NGHI, "so_hieu_ban_ve": "MN-01",
        })

    provider = FakeProvider(fn=fake_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload(client, token, session_id, path="/api/aiho/read-densucco")

    assert resp.status_code == 200
    data = resp.get_json()
    assert nhom_iv_cau in data["kien_nghi"]["IV_de_xuat_bo_sung"]
    assert data["kien_nghi"]["I_chua_the_hien"] == []


def test_all_4_real_categories_in_one_session_hits_exactly_file_and_form_cap(client):
    """Ca 4 hang muc AI that (baochay 1f/1m + dienpccc 1f/1m + ccnuoc 1f/3m +
    densucco 1f/2m) trong CUNG 1 phien = dung 4 file, 7 form - dung khit tran
    form (7), con du dung 1 file (5) - dung nhu thiet ke da duyet."""
    token, _ = _register_login_and_grant(client, email="aihoread13@pccc.local")
    session_id = _open_session(client, token)

    def fake_generate(system_prompt):
        if "B1" in system_prompt and "B2" in system_prompt:
            rows = mdc_filler.load_criteria_rows("thuong")
            return json.dumps({
                "loai_he_thong": "thuong",
                "ly_do_nhan_dien": "test",
                "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
                "tong_ket": "ok",
                "kien_nghi": EMPTY_KIEN_NGHI,
                "so_hieu_ban_ve": "ALL-01",
            })
        if "B14" in system_prompt:
            return _dienpccc_payload()
        if "B3" in system_prompt or "B5" in system_prompt or "B6" in system_prompt:
            loai = "tram_bom" if "B3" in system_prompt else ("hong_nuoc" if "B5" in system_prompt else "chua_chay_tu_dong")
            return _ccnuoc_payload_for(loai, so_hieu="ALL-01")
        return _fake_densucco_generate(system_prompt)

    provider = FakeProvider(fn=fake_generate)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        r1 = _upload(client, token, session_id, path="/api/aiho/read-baochay", filename="a.png")
        r2 = _upload(client, token, session_id, path="/api/aiho/read-dienpccc", filename="b.png")
        r3 = _upload(client, token, session_id, path="/api/aiho/read-ccnuoc", filename="c.png")
        r4 = _upload(client, token, session_id, path="/api/aiho/read-densucco", filename="d.png")

    assert [r.status_code for r in (r1, r2, r3, r4)] == [200, 200, 200, 200]
    session = HoSoSession.query.get(session_id)
    assert session.files_used == 4
    assert session.forms_used == 7
