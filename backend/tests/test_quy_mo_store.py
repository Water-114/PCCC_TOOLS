"""Batch 5A mở rộng ("Quy mô"/Form A) — test cho
backend/app/services/quy_mo_store.py: build_form_a_items() (40 dòng, không
trùng id, không crash khi thiếu dữ liệu), validate_manual_fields(), lưu/đọc
qua HoSoSessionQuyMo (get_quy_mo/save_quy_mo), và format_quy_mo_context()
(đoạn ngữ cảnh nối vào 4 reader khác)."""

import pytest

from app.services import quy_mo_store
from app.services.ho_so_session import open_session
from app.services import credits
from app.models import User
from app.extensions import db


EXPECTED_IDS = {
    2, 3, 4, 7, 8, 9, 10, 12, 13, 16, 17, 18, 19, 21, 22, 25, 27, 28, 30, 31,
    32, 34, 36, 37, 38, 42, 43, 45, 46, 49, 50, 51, 52, 55, 56, 57, 58, 60, 61, 63,
}


# ---------------------------------------------------------------------------
# build_form_a_items — dung cho ca route AI va route nhap tay
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fields", [
    {"occ": "chungcu", "floors": 8, "totalArea": 3200, "hFire": 22, "basements": 1},
    {"occ": "sanxuat", "hazard": "C", "areaFloor": 400, "totalArea": 1000, "volume": 5000},
    {"occ": "garakin", "totalArea": 5000, "floors": 3, "garaKin": "kin"},
    {"occ": "khachsan", "floors": 8, "volume": 6000, "hanhLangDaiNhat": 12},
    {"occ": "hamgiaothong"},  # occ can "extra" field khong co trong QuyMoFields
    {"occ": "khachsan"},  # hau nhu trong, khong duoc crash
])
def test_build_form_a_items_returns_exactly_40_rows_no_duplicates(app, fields):
    with app.app_context():
        items = quy_mo_store.build_form_a_items(fields)
    ids = [i["id"] for i in items]
    assert len(items) == 40
    assert set(ids) == EXPECTED_IDS
    assert len(ids) == len(set(ids))
    for i in items:
        assert i["ket_luan"] in ("dat", "chua_dat", "chua_the_hien", "khong_ap_dung")
        assert isinstance(i["noi_dung_thiet_ke"], str) and i["noi_dung_thiet_ke"]


def test_build_form_a_items_ai_answered_rows_use_provided_text(app):
    with app.app_context():
        items = quy_mo_store.build_form_a_items(
            {"occ": "chungcu"},
            a2_bao_chay="Khu vực kỹ thuật tầng hầm.",
            a4_bao_chay=None,
            a2_sprinkler="",
            a4_sprinkler="Tủ điện phòng bơm.",
        )
    by_id = {i["id"]: i for i in items}
    assert by_id[8]["noi_dung_thiet_ke"] == "Khu vực kỹ thuật tầng hầm."
    assert by_id[8]["ket_luan"] == "dat"
    assert by_id[10]["noi_dung_thiet_ke"] == quy_mo_store.KHONG_XAC_DINH_AI
    assert by_id[10]["ket_luan"] == "chua_the_hien"
    assert by_id[17]["noi_dung_thiet_ke"] == quy_mo_store.KHONG_XAC_DINH_AI
    assert by_id[19]["noi_dung_thiet_ke"] == "Tủ điện phòng bơm."


def test_build_form_a_items_khong_thiet_ke_cluster_marked_khong_ap_dung(app):
    with app.app_context():
        items = quy_mo_store.build_form_a_items({"occ": "chungcu"})
    by_id = {i["id"]: i for i in items}
    for row_id in (36, 37, 38, 51, 52):
        assert by_id[row_id]["ket_luan"] == "khong_ap_dung", row_id
        assert "Không thiết kế" in by_id[row_id]["noi_dung_thiet_ke"]


def test_build_form_a_items_profile_rows_reflect_floors_and_hfire(app):
    with app.app_context():
        items = quy_mo_store.build_form_a_items({"occ": "chungcu", "floors": 10, "basements": 2, "hFire": 30})
    by_id = {i["id"]: i for i in items}
    assert "10" in by_id[3]["noi_dung_thiet_ke"]
    assert "2" in by_id[3]["noi_dung_thiet_ke"]
    assert by_id[3]["ket_luan"] == "dat"
    assert "30" in by_id[4]["noi_dung_thiet_ke"]


def test_build_form_a_items_profile_rows_missing_data_are_chua_the_hien(app):
    with app.app_context():
        items = quy_mo_store.build_form_a_items({"occ": "chungcu"})
    by_id = {i["id"]: i for i in items}
    assert by_id[3]["ket_luan"] == "chua_the_hien"
    assert by_id[4]["ket_luan"] == "chua_the_hien"


def test_build_type1_id42_den_always_yes_lists_positions(app):
    with app.app_context():
        items = quy_mo_store.build_type1_items({"occ": "chungcu"})
    row = next(i for i in items if i["id"] == 42)
    assert row["ket_luan"] == "dat"
    assert "Vị trí bắt buộc lắp đặt" in row["noi_dung_thiet_ke"]


def test_build_type1_id49_binh_static_always_dat(app):
    with app.app_context():
        items = quy_mo_store.build_type1_items({"occ": "chungcu"})
    row = next(i for i in items if i["id"] == 49)
    assert row["ket_luan"] == "dat"


# ---------------------------------------------------------------------------
# validate_manual_fields
# ---------------------------------------------------------------------------
def test_validate_manual_fields_rejects_non_dict(app):
    with app.app_context(), pytest.raises(quy_mo_store.QuyMoInputError):
        quy_mo_store.validate_manual_fields("not-a-dict")


def test_validate_manual_fields_rejects_invalid_occ(app):
    with app.app_context(), pytest.raises(quy_mo_store.QuyMoInputError):
        quy_mo_store.validate_manual_fields({"occ": "khong_ton_tai"})


def test_validate_manual_fields_rejects_negative_number(app):
    with app.app_context(), pytest.raises(quy_mo_store.QuyMoInputError):
        quy_mo_store.validate_manual_fields({"occ": "chungcu", "floors": -1})


def test_validate_manual_fields_accepts_valid_and_coerces_types(app):
    with app.app_context():
        data = quy_mo_store.validate_manual_fields({"occ": "chungcu", "floors": 8, "totalArea": "3200"})
    assert data["occ"] == "chungcu"
    assert data["floors"] == 8
    assert data["totalArea"] == 3200.0


# ---------------------------------------------------------------------------
# get_quy_mo / save_quy_mo — luu tru theo session_id (UNIQUE, upsert)
# ---------------------------------------------------------------------------
def _make_session(app):
    user = User(email="quymostore@pccc.local")
    user.set_password("matkhau123")
    db.session.add(user)
    db.session.commit()
    credits.grant_credits(user.id, 3, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="test")
    return open_session(user.id)


def test_get_quy_mo_returns_none_when_nothing_saved(app):
    with app.app_context():
        session = _make_session(app)
        assert quy_mo_store.get_quy_mo(session.id) is None


def test_save_then_get_quy_mo_roundtrip(app):
    with app.app_context():
        session = _make_session(app)
        quy_mo_store.save_quy_mo(session.id, {"occ": "chungcu", "floors": 8, "hFire": 22}, source="manual")
        data = quy_mo_store.get_quy_mo(session.id)
    assert data["occ"] == "chungcu"
    assert data["floors"] == 8
    assert data["hFire"] == 22
    assert data["totalArea"] is None


def test_save_quy_mo_upserts_same_session_no_duplicate_row(app):
    from app.models import HoSoSessionQuyMo
    with app.app_context():
        session = _make_session(app)
        quy_mo_store.save_quy_mo(session.id, {"occ": "chungcu", "floors": 5}, source="manual")
        quy_mo_store.save_quy_mo(session.id, {"occ": "khachsan", "floors": 9}, source="ai")
        rows = HoSoSessionQuyMo.query.filter_by(session_id=session.id).all()
        data = quy_mo_store.get_quy_mo(session.id)
    assert len(rows) == 1
    assert data["occ"] == "khachsan"
    assert data["floors"] == 9


# ---------------------------------------------------------------------------
# format_quy_mo_context
# ---------------------------------------------------------------------------
def test_format_quy_mo_context_includes_only_present_fields(app):
    with app.app_context():
        ctx = quy_mo_store.format_quy_mo_context({"occ": "chungcu", "floors": 8})
    assert "QUY MÔ CÔNG TRÌNH ĐÃ XÁC NHẬN" in ctx
    assert "Số tầng nổi: 8" in ctx
    assert "Tổng diện tích sàn" not in ctx
