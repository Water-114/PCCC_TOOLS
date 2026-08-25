"""Dự án nhiều công trình (Đợt 2a) — test trực tiếp service layer
hang_muc_store.py (không qua route) + quy_mo_store.build_thuoc_dien_preview_items().

Trọng tâm: build_thuoc_dien_preview_items() PHẢI phân biệt đúng "yes" (thuộc
diện, "dat") với "no" (rule đã chạy nhưng KHÔNG thuộc diện, "khong_ap_dung")
— khác build_type1_items() (Form A) vốn gộp cả 2 thành "dat" vì mục đích
khác (Form A chỉ quan tâm "đã trả lời chưa", không phải "có bắt buộc
không"). Đây là đúng lỗi thực tế owner đã gặp (công trình dưới ngưỡng loa
thông báo 18.000m² bị kết luận sai)."""

import pytest

from app.extensions import db
from app.models import HoSoSession
from app.services import hang_muc_store, quy_mo_store


@pytest.fixture
def open_session(app, client):
    from app.services import credits
    client.post("/api/auth/register", json={"email": "hangmucstore@pccc.local", "password": "matkhau123"})
    resp = client.post("/api/auth/login", json={"email": "hangmucstore@pccc.local", "password": "matkhau123"})
    data = resp.get_json()
    credits.grant_credits(data["user"]["id"], 5, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="test")
    resp2 = client.post("/api/aiho/session/open", headers={"Authorization": f"Bearer {data['token']}"})
    return resp2.get_json()["session_id"]


def test_build_thuoc_dien_preview_items_loa_below_threshold_is_khong_ap_dung():
    items = quy_mo_store.build_thuoc_dien_preview_items({"occ": "sanxuat", "totalArea": 15108, "pplFloor": 350})
    loa = next(it for it in items if it["id"] == 45)
    assert loa["ket_luan"] == "khong_ap_dung"


def test_build_thuoc_dien_preview_items_loa_above_threshold_is_dat():
    items = quy_mo_store.build_thuoc_dien_preview_items({"occ": "sanxuat", "totalArea": 20000, "pplFloor": 350})
    loa = next(it for it in items if it["id"] == 45)
    assert loa["ket_luan"] == "dat"


def test_build_thuoc_dien_preview_items_differs_from_form_a_ket_luan():
    """Cung 1 fields, id=45 phai KHAC nhau giua 2 ham: Form A ("dat" - da co
    ket luan, du la yes/no) vs preview ("khong_ap_dung" - khong bat buoc)."""
    fields = {"occ": "sanxuat", "totalArea": 15108, "pplFloor": 350}
    form_a_items = quy_mo_store.build_type1_items(fields)
    preview_items = quy_mo_store.build_thuoc_dien_preview_items(fields)

    form_a_loa = next(it for it in form_a_items if it["id"] == 45)
    preview_loa = next(it for it in preview_items if it["id"] == 45)

    assert form_a_loa["ket_luan"] == "dat"  # Form A: da tra loi (khong phai "bat buoc")
    assert preview_loa["ket_luan"] == "khong_ap_dung"  # Preview: KHONG bat buoc


def test_build_thuoc_dien_preview_items_malformed_data_is_chua_the_hien():
    """pplFloor khong phai so nguyen -> PhuongTienInputError -> _safe_eval()
    tra ve "warn" -> "chua_the_hien" (khac voi CHI thieu pplFloor, truong
    hop nay evaluate_loa() tu giam nhe xuong "no" kem ghi chu, khong phai
    "warn" - _num()/_int_or_none() chi raise khi gia tri SAI DANG, khong
    raise khi gia tri THIEU hoan toan)."""
    items = quy_mo_store.build_thuoc_dien_preview_items({"occ": "sanxuat", "totalArea": 20000, "pplFloor": 5.5})
    loa = next(it for it in items if it["id"] == 45)
    assert loa["ket_luan"] == "chua_the_hien"


def test_build_thuoc_dien_preview_items_missing_optional_field_degrades_to_khong_ap_dung():
    """Thieu HOAN TOAN pplFloor (khac gia tri sai dang o test tren) - evaluate_loa()
    tu giam nhe xuong "no" (khong dat nguong nao) kem ghi chu giai thich,
    KHONG phai "warn" - _num()/_int_or_none() tra ve None/default thay vi
    raise khi gia tri thieu. Hanh vi nay la CUA evaluate_loa() co san, khong
    phai loi cua build_thuoc_dien_preview_items()."""
    items = quy_mo_store.build_thuoc_dien_preview_items({"occ": "sanxuat", "totalArea": 20000})
    loa = next(it for it in items if it["id"] == 45)
    assert loa["ket_luan"] == "khong_ap_dung"


def test_build_thuoc_dien_preview_items_binh_chua_chay_always_dat():
    items = quy_mo_store.build_thuoc_dien_preview_items({"occ": "chungcu"})
    binh = next(it for it in items if it["id"] == 49)
    assert binh["ket_luan"] == "dat"


def test_save_hang_muc_creates_new_record_each_call(open_session):
    r1 = hang_muc_store.save_hang_muc(open_session, "Xưởng A", {"occ": "chungcu", "floors": 5})
    r2 = hang_muc_store.save_hang_muc(open_session, "Kho B", {"occ": "kho"})
    assert r1["hang_muc_id"] != r2["hang_muc_id"]

    items = hang_muc_store.list_hang_muc(open_session)
    assert len(items) == 2


def test_save_hang_muc_blank_ten_raises():
    with pytest.raises(hang_muc_store.HangMucInputError):
        hang_muc_store.save_hang_muc(1, "   ", {"occ": "chungcu"})


def test_save_hang_muc_invalid_fields_raises():
    with pytest.raises(hang_muc_store.HangMucInputError):
        hang_muc_store.save_hang_muc(1, "Xưởng A", {"occ": "khong_ton_tai"})


def test_update_hang_muc_wrong_session_raises_not_found(open_session):
    row = hang_muc_store.save_hang_muc(open_session, "Xưởng A", {"occ": "chungcu"})
    with pytest.raises(hang_muc_store.HangMucNotFound):
        hang_muc_store.update_hang_muc(row["hang_muc_id"], open_session + 999, "X", {"occ": "chungcu"})


def test_delete_hang_muc_wrong_session_raises_not_found(open_session):
    row = hang_muc_store.save_hang_muc(open_session, "Xưởng A", {"occ": "chungcu"})
    with pytest.raises(hang_muc_store.HangMucNotFound):
        hang_muc_store.delete_hang_muc(row["hang_muc_id"], open_session + 999)


def test_list_hang_muc_empty_for_session_with_none(open_session):
    assert hang_muc_store.list_hang_muc(open_session) == []
