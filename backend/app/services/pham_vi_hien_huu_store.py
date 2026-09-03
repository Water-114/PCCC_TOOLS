"""Form A gốc (A14/A15) — Phần 0: "phạm vi đề nghị thẩm định lần này" + "hạ
tầng hiện hữu". Thuần CRUD, KHÔNG AI, KHÔNG quota — dùng cho combiner
form_a_combiner.py phân biệt (a) hệ thống không thuộc diện, (b) hệ thống
hiện hữu ngoài phạm vi đề nghị lần này, (c) hệ thống cần dẫn chiếu B-form.

Đây là tính năng TUỲ CHỌN giống hệt "Quy mô" (đính kèm tự nguyện) — KHÔNG
khai báo gì thì combiner coi như dự án xây mới hoàn toàn, mọi hệ thống đều
trong phạm vi đề nghị lần này (xem save_pham_vi_de_nghi())."""

from ..extensions import db
from ..models import HoSoSessionHaTangHienHuu, HoSoSessionQuyMo

# Khoá hệ thống hợp lệ — DÙNG CHUNG cho ca pham_vi_de_nghi VA ha_tang_hien_huu
# (owner cho san trong prompt, KHONG doan them/bot).
HE_THONG_KEYS = (
    "baochay", "dienpccc", "tram_bom", "hong_nuoc", "chua_chay_tu_dong",
    "giakehang", "botcodinh", "botchuachay", "khibotsolkhi", "densucco",
    "binhchuachay",
)
_HE_THONG_KEYS_SET = set(HE_THONG_KEYS)


class PhamViHienHuuInputError(Exception):
    pass


class HaTangHienHuuNotFound(Exception):
    pass


def _validate_he_thong_key(ten_he_thong):
    if ten_he_thong not in _HE_THONG_KEYS_SET:
        raise PhamViHienHuuInputError(
            f"Khoá hệ thống không hợp lệ: '{ten_he_thong}' — phải là 1 trong {sorted(_HE_THONG_KEYS_SET)}."
        )
    return ten_he_thong


def save_pham_vi_de_nghi(session_id: int, danh_sach_khoa_he_thong) -> list:
    """Lưu danh sách khoá hệ thống ĐANG xin thẩm định lần này. Rỗng/None =
    KHÔNG khai báo gì — combiner coi như TẤT CẢ hệ thống đều trong phạm vi
    (mặc định dự án xây mới hoàn toàn), KHÔNG được coi None là 'không hệ
    thống nào trong phạm vi' (ngược lại hoàn toàn ý nghĩa thật)."""
    if danh_sach_khoa_he_thong is None:
        danh_sach = None
    else:
        if not isinstance(danh_sach_khoa_he_thong, list):
            raise PhamViHienHuuInputError("'pham_vi_de_nghi' phải là một danh sách (list) khoá hệ thống.")
        danh_sach = [_validate_he_thong_key(k) for k in danh_sach_khoa_he_thong]

    row = HoSoSessionQuyMo.query.filter_by(session_id=session_id).first()
    if row is None:
        row = HoSoSessionQuyMo(session_id=session_id, source="manual")
        db.session.add(row)
    row.pham_vi_de_nghi = danh_sach
    db.session.commit()
    return danh_sach


def get_pham_vi_de_nghi(session_id: int):
    """Trả về list khoá hệ thống, hoặc None nếu chưa khai báo gì (session
    chưa có bản ghi HoSoSessionQuyMo nào, HOẶC có bản ghi nhưng pham_vi_de_nghi
    vẫn NULL) — caller (form_a_combiner.py) phải coi None là 'tất cả hệ
    thống đều trong phạm vi', KHÔNG phải 'rỗng'."""
    row = HoSoSessionQuyMo.query.filter_by(session_id=session_id).first()
    return row.pham_vi_de_nghi if row else None


def he_thong_trong_pham_vi(session_id: int, ten_he_thong: str) -> bool:
    """True nếu hệ thống này ĐANG được đề nghị thẩm định lần này. Mặc định
    (chưa khai báo gì) -> True cho MỌI hệ thống (xem get_pham_vi_de_nghi())."""
    danh_sach = get_pham_vi_de_nghi(session_id)
    if danh_sach is None:
        return True
    return ten_he_thong in danh_sach


def _validate_ha_tang_fields(gcn_so, gcn_ngay, nghiem_thu_so, nghiem_thu_ngay):
    if not isinstance(gcn_so, str) or not gcn_so.strip():
        raise PhamViHienHuuInputError("Thiếu số Giấy chứng nhận thẩm duyệt (gcn_so).")
    if not isinstance(gcn_ngay, str) or not gcn_ngay.strip():
        raise PhamViHienHuuInputError("Thiếu ngày Giấy chứng nhận thẩm duyệt (gcn_ngay).")
    if not isinstance(nghiem_thu_so, str) or not nghiem_thu_so.strip():
        raise PhamViHienHuuInputError("Thiếu số văn bản nghiệm thu (nghiem_thu_so).")
    if not isinstance(nghiem_thu_ngay, str) or not nghiem_thu_ngay.strip():
        raise PhamViHienHuuInputError("Thiếu ngày văn bản nghiệm thu (nghiem_thu_ngay).")


def save_ha_tang_hien_huu(
    session_id: int, ten_he_thong: str, gcn_so: str, gcn_ngay: str,
    gcn_bo_sung_so: str = None, gcn_bo_sung_ngay: str = None,
    nghiem_thu_so: str = None, nghiem_thu_ngay: str = None,
    ghi_chu_ban_ve: str = None,
) -> dict:
    """Tạo 1 bản ghi MỚI (không upsert — 1 phiên có thể có nhiều hệ thống
    hiện hữu khác nhau, vd cả trạm bơm lẫn điện PCCC)."""
    _validate_he_thong_key(ten_he_thong)
    _validate_ha_tang_fields(gcn_so, gcn_ngay, nghiem_thu_so, nghiem_thu_ngay)

    row = HoSoSessionHaTangHienHuu(
        session_id=session_id,
        ten_he_thong=ten_he_thong,
        gcn_so=gcn_so.strip(),
        gcn_ngay=gcn_ngay.strip(),
        gcn_bo_sung_so=(gcn_bo_sung_so or "").strip() or None,
        gcn_bo_sung_ngay=(gcn_bo_sung_ngay or "").strip() or None,
        nghiem_thu_so=nghiem_thu_so.strip(),
        nghiem_thu_ngay=nghiem_thu_ngay.strip(),
        ghi_chu_ban_ve=(ghi_chu_ban_ve or "").strip() or None,
    )
    db.session.add(row)
    db.session.commit()
    return row.to_dict()


def list_ha_tang_hien_huu(session_id: int) -> list:
    rows = (
        HoSoSessionHaTangHienHuu.query.filter_by(session_id=session_id)
        .order_by(HoSoSessionHaTangHienHuu.id.asc())
        .all()
    )
    return [r.to_dict() for r in rows]


def delete_ha_tang_hien_huu(ha_tang_id: int, session_id: int) -> None:
    row = db.session.get(HoSoSessionHaTangHienHuu, ha_tang_id)
    if row is None or row.session_id != session_id:
        raise HaTangHienHuuNotFound("Không tìm thấy bản ghi hạ tầng hiện hữu này trong phiên Bộ hồ sơ hiện tại.")
    db.session.delete(row)
    db.session.commit()


def is_he_thong_hien_huu(session_id: int, ten_he_thong: str) -> HoSoSessionHaTangHienHuu | None:
    """Combiner Form A dùng hàm này (Nhánh (b), ưu tiên cao nhất) — trả về
    bản ghi hiện hữu KHỚP ten_he_thong trong phiên này, hoặc None nếu hệ
    thống này không được khai báo hiện hữu (bản vẽ mới/xin thẩm định lần
    này). Nếu có NHIỀU bản ghi cùng ten_he_thong (không nên xảy ra trong
    thực tế, nhưng không chặn) thì lấy bản ghi tạo SAU CÙNG (mới nhất)."""
    return (
        HoSoSessionHaTangHienHuu.query.filter_by(session_id=session_id, ten_he_thong=ten_he_thong)
        .order_by(HoSoSessionHaTangHienHuu.id.desc())
        .first()
    )
