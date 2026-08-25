"""Dự án nhiều công trình (Đợt 2a) — khai báo + xem trước quy mô TỪNG công
trình/khối trong 1 dự án PCCC (vd Xưởng A, Kho B, Kho C cùng 1 phiên Bộ hồ
sơ). Thuần nhập tay + tính toán rule-based đã có sẵn — KHÔNG dùng AI.

LƯU Ý THUẬT NGỮ: "hạng mục" ở module này nghĩa là 1 CÔNG TRÌNH/KHỐI trong dự
án — KHÁC "hạng mục" ở khu "Bước 1" AIHO (nghĩa là 1 loại hệ thống PCCC). Xem
models.HoSoSessionHangMuc.

Tái dùng tối đa: QuyMoFields (validate, occ bắt buộc — nhập tay có chủ đích,
khác ScanQuyMoFields của Lượt 0), build_thuoc_dien_preview_items() (rule-based,
quy_mo_store.py) — KHÔNG viết lại logic ngưỡng/công thức nào ở đây."""

from pydantic import ValidationError

from ..extensions import db
from ..models import HoSoSessionHangMuc
from .ai_schema import QuyMoFields
from .quy_mo_store import build_thuoc_dien_preview_items


class HangMucInputError(Exception):
    pass


class HangMucNotFound(Exception):
    pass


def _validate_ten_hang_muc(ten_hang_muc) -> str:
    if not isinstance(ten_hang_muc, str) or not ten_hang_muc.strip():
        raise HangMucInputError("Thiếu tên công trình — vui lòng nhập tên (vd \"Xưởng A\").")
    return ten_hang_muc.strip()


def _validate_fields(fields) -> dict:
    """Validate quy mô nhập tay cho 1 công trình — dùng ĐÚNG QuyMoFields
    (occ bắt buộc, giống validate_manual_fields() của quy_mo_store.py) vì
    đây là nhập tay có chủ đích cho 1 công trình cụ thể, không phải quét nhẹ
    như Lượt 0 (ScanQuyMoFields, occ optional)."""
    if not isinstance(fields, dict):
        raise HangMucInputError("Dữ liệu quy mô phải là một JSON object.")
    try:
        model = QuyMoFields.model_validate(fields)
    except ValidationError as exc:
        raise HangMucInputError(f"Dữ liệu quy mô không hợp lệ: {exc}") from exc
    data = model.model_dump()
    for key in (
        "floors", "basements", "semiBasements", "areaFloor", "totalArea",
        "volume", "hFire", "kids", "seats", "pplFloor", "hanhLangDaiNhat",
        "chieuCaoKeHang",
    ):
        v = data.get(key)
        if v is not None and v < 0:
            raise HangMucInputError(f"Giá trị của '{key}' không được âm.")
    return data


def _apply_fields(row: HoSoSessionHangMuc, fields: dict) -> None:
    row.occ = fields.get("occ")
    row.floors = fields.get("floors")
    row.basements = fields.get("basements")
    row.semi_basements = fields.get("semiBasements")
    row.area_floor = fields.get("areaFloor")
    row.total_area = fields.get("totalArea")
    row.volume = fields.get("volume")
    row.h_fire = fields.get("hFire")
    row.kids = fields.get("kids")
    row.seats = fields.get("seats")
    row.hazard = fields.get("hazard")
    row.gara_kin = fields.get("garaKin")
    row.gara_kc12 = fields.get("garaKC12")
    row.gara_bcl = fields.get("garaBcl")
    row.gara_cap_s = fields.get("garaCapS")
    row.ppl_floor = fields.get("pplFloor")
    row.ext_level = fields.get("extLevel")
    row.hanh_lang_dai_nhat = fields.get("hanhLangDaiNhat")
    row.chieu_cao_ke_hang = fields.get("chieuCaoKeHang")
    row.co_be_xang_dau_ngoai_troi = fields.get("coBeXangDauNgoaiTroi")


def _to_public_dict(row: HoSoSessionHangMuc) -> dict:
    fields = row.to_fields_dict()
    return {
        "hang_muc_id": row.id,
        "ten_hang_muc": row.ten_hang_muc,
        "fields": fields,
        "thuoc_dien_items": build_thuoc_dien_preview_items(fields),
    }


def save_hang_muc(session_id: int, ten_hang_muc, fields) -> dict:
    """Tạo 1 công trình MỚI trong phiên — KHÔNG upsert theo session_id (khác
    save_quy_mo()) vì 1 phiên có thể có nhiều công trình."""
    ten = _validate_ten_hang_muc(ten_hang_muc)
    clean_fields = _validate_fields(fields)

    row = HoSoSessionHangMuc(session_id=session_id, ten_hang_muc=ten)
    _apply_fields(row, clean_fields)
    db.session.add(row)
    db.session.commit()
    return _to_public_dict(row)


def _get_row_or_raise(hang_muc_id: int, session_id: int) -> HoSoSessionHangMuc:
    row = db.session.get(HoSoSessionHangMuc, hang_muc_id)
    if row is None or row.session_id != session_id:
        raise HangMucNotFound("Không tìm thấy công trình này trong phiên Bộ hồ sơ hiện tại.")
    return row


def update_hang_muc(hang_muc_id: int, session_id: int, ten_hang_muc, fields) -> dict:
    row = _get_row_or_raise(hang_muc_id, session_id)
    ten = _validate_ten_hang_muc(ten_hang_muc)
    clean_fields = _validate_fields(fields)

    row.ten_hang_muc = ten
    _apply_fields(row, clean_fields)
    db.session.commit()
    return _to_public_dict(row)


def delete_hang_muc(hang_muc_id: int, session_id: int) -> None:
    row = _get_row_or_raise(hang_muc_id, session_id)
    db.session.delete(row)
    db.session.commit()


def list_hang_muc(session_id: int) -> list:
    rows = (
        HoSoSessionHangMuc.query.filter_by(session_id=session_id)
        .order_by(HoSoSessionHangMuc.id.asc())
        .all()
    )
    return [_to_public_dict(row) for row in rows]
