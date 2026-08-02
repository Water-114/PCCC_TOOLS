"""Batch 5A mở rộng ("Quy mô"/Form A) — xác nhận ĐÚNG đính chính của owner:
tích hợp Quy mô vào 4 reader hiện có (báo cháy/điện PCCC/nước/đèn-bình) PHẢI
hoàn toàn TUỲ CHỌN — hạng mục khác vẫn chạy bình thường khi phiên KHÔNG có
Quy mô (không blocking, không bắt buộc), và khi CÓ Quy mô thì system prompt
gửi AI được nối thêm đúng 1 đoạn ngữ cảnh (KHÔNG thay thế việc tự đọc bản vẽ).

Khác test_aiho_read_routes.py (test hành vi chung của route) và test cấp
reader-function (baochay_reader.read_drawing() trực tiếp) — file này test qua
route thật /api/aiho/read-* để xác nhận get_quy_mo(session.id) THỰC SỰ được
route truyền xuống, không chỉ đúng ở tầng function."""

import io
import json
from unittest.mock import patch

from app.providers.base import GenerationResult
from app.services import credits, mdc_filler, quy_mo_store

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
EMPTY_KIEN_NGHI = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}


def _register_login_and_grant(client, email, amount=5):
    client.post("/api/auth/register", json={"email": email, "password": "matkhau123"})
    resp = client.post("/api/auth/login", json={"email": email, "password": "matkhau123"})
    data = resp.get_json()
    token, user_id = data["token"], data["user"]["id"]
    credits.grant_credits(user_id, amount, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="test setup")
    return token, user_id


def _open_session(client, token):
    resp = client.post("/api/aiho/session/open", headers={"Authorization": f"Bearer {token}"})
    return resp.get_json()["session_id"]


class CapturingProvider:
    """Ghi lai TOAN BO system_prompt tung lan goi (co the >1 lan voi ccnuoc/
    densucco - moi lan 1 form), tra ve JSON hop le cho dien_pccc (1 form don)."""
    name = "fake"
    model = "fake-model"

    def __init__(self, payload_fn):
        self.captured_prompts = []
        self.payload_fn = payload_fn

    def generate_with_document(self, system_prompt, content_block):
        self.captured_prompts.append(system_prompt)
        return GenerationResult(text=self.payload_fn(system_prompt))


def _dienpccc_payload(_system_prompt=None):
    rows = mdc_filler.load_criteria_rows("dien_pccc")
    return json.dumps({
        "items": [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows],
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
        "so_hieu_ban_ve": "E-01",
    })


def _upload_dienpccc(client, token, session_id):
    return client.post(
        "/api/aiho/read-dienpccc",
        data={"file": (io.BytesIO(PNG_BYTES), "drawing.png"), "session_id": str(session_id)},
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


def test_dienpccc_without_quy_mo_prompt_unchanged(client):
    """Chua dinh Quy mo trong phien -> prompt gui AI phai GIONG HET truoc day,
    khong bi anh huong gi (dung tinh than dinh chinh cua owner)."""
    from app.services import dienpccc_reader

    token, _ = _register_login_and_grant(client, "optint1@pccc.local")
    session_id = _open_session(client, token)
    provider = CapturingProvider(_dienpccc_payload)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_dienpccc(client, token, session_id)
    assert resp.status_code == 200
    assert provider.captured_prompts[0] == dienpccc_reader.SYSTEM_PROMPT


def test_dienpccc_with_quy_mo_prompt_augmented(client):
    """Da dinh Quy mo (route quymo-manual) truoc do trong CUNG phien -> khi doc
    dien PCCC, prompt PHAI duoc noi them dung 1 doan ngu canh quy mo."""
    from app.services import dienpccc_reader

    token, _ = _register_login_and_grant(client, "optint2@pccc.local", amount=5)
    session_id = _open_session(client, token)

    manual_resp = client.post(
        "/api/aiho/quymo-manual",
        json={"session_id": session_id, "quy_mo": {"occ": "khachsan", "floors": 9, "totalArea": 4000}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert manual_resp.status_code == 200

    provider = CapturingProvider(_dienpccc_payload)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_dienpccc(client, token, session_id)
    assert resp.status_code == 200

    prompt = provider.captured_prompts[0]
    assert prompt.startswith(dienpccc_reader.SYSTEM_PROMPT)
    assert "QUY MÔ CÔNG TRÌNH ĐÃ XÁC NHẬN" in prompt
    assert "Số tầng nổi: 9" in prompt


def test_quy_mo_from_other_session_does_not_leak_in(client):
    """Quy mo gan voi phien A khong duoc anh huong toi phien B cua CUNG user
    (moi phien Bo ho so doc lap) - dung open 1 phien thu 2, khong dinh Quy mo,
    xac nhan prompt khong bi anh huong boi phien truoc do."""
    from app.services import dienpccc_reader

    token, _ = _register_login_and_grant(client, "optint3@pccc.local", amount=5)
    session_a = _open_session(client, token)
    client.post(
        "/api/aiho/quymo-manual",
        json={"session_id": session_a, "quy_mo": {"occ": "khachsan", "floors": 9}},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post("/api/aiho/session/close", json={"session_id": session_a}, headers={"Authorization": f"Bearer {token}"})

    session_b = _open_session(client, token)
    assert quy_mo_store.get_quy_mo(session_b) is None

    provider = CapturingProvider(_dienpccc_payload)
    with patch("app.routes.aiho.get_provider", return_value=provider):
        resp = _upload_dienpccc(client, token, session_b)
    assert resp.status_code == 200
    assert provider.captured_prompts[0] == dienpccc_reader.SYSTEM_PROMPT
