"""Dung file mau .docx that (letterhead/Kinh gui/Can cu san co) de xuat
"Cong van huong dan" - thay MERGEFIELD thong tin du an, thay danh sach cau
kien nghi duoi tung tieu de nhom he thong bang du lieu that cua phien Bo
ho so. Doi chieu tai lieu "Bo quy tac doc ban ve va dien MDC" 03/9/2026."""

import copy
import io

from docx import Document

from . import mdc_filler
from .docx_mergefield import replace_mergefield

TEMPLATE_PATH = mdc_filler.TEMPLATES_DIR / "cong_van_huong_dan_thiet_ke.docx"
FILENAME = "Cong_van_huong_dan_thiet_ke.docx"

_GROUP_HEADINGS = {
    "thong_tin_cong_trinh": "Thông tin công trình",
    "bao_chay": "Hệ thống báo cháy:",
    "chua_chay": "Hệ thống chữa cháy:",
    "dien": "Hệ thống điện:",
    "khac": "Các hệ thống, phương tiện PCCC khác:",
}

# slot (dung dung ten REAL_CATEGORIES phia frontend) -> nhom VBHD. Gop nhieu
# slot vao 1 nhom vi mau VBHD chi chia 4 nhom he thong (thô hon 11 muc bao
# cao tham dinh se lam o Buoc 4 sau).
SLOT_TO_GROUP = {
    "quy_mo": "thong_tin_cong_trinh",
    "baochay": "bao_chay",
    "dienpccc": "dien",
    "ccnuoc": "chua_chay",
    "khibot": "chua_chay",
    "botcodinh": "chua_chay",
    "giakehang": "chua_chay",
    "botchuachay": "chua_chay",
    "densucco": "khac",
}


class CongVanHuongDanError(Exception):
    pass


def _gom_kien_nghi_theo_nhom(hang_muc_list: list) -> dict:
    """hang_muc_list: list dict {slot, kien_nghi} (kien_nghi la dict 4 khoa
    I..IV -> list cau, dung nguyen dang cac reader tra ve). Tra ve dict
    nhom -> list cau kien nghi PHANG (gop het I,II,III,IV theo dung thu tu,
    khong tach nhom trong van ban xuat ra - dung tinh than van ban mau
    that: liet ke thang cac gach dau dong, khong chia I/II/III/IV)."""
    out = {key: [] for key in _GROUP_HEADINGS}
    for hang_muc in hang_muc_list:
        group = SLOT_TO_GROUP.get(hang_muc.get("slot"))
        if group is None:
            continue
        kn = hang_muc.get("kien_nghi") or {}
        for key in ("I_chua_the_hien", "II_chua_thong_nhat", "III_chua_phu_hop", "IV_de_xuat_bo_sung"):
            out[group].extend(kn.get(key) or [])
    return out


def _tim_doan_tieu_de(doc, text_can_tim):
    for p in doc.paragraphs:
        if p.text.strip() == text_can_tim:
            return p
    return None


def _thay_danh_sach_kien_nghi(doc, group_key, cau_list):
    """Xoa cac doan '- ...' cu ngay sau tieu de group_key, chen doan MOI cho
    tung cau trong cau_list (deepcopy dung 1 doan cu de giu nguyen format).
    Neu cau_list rong: XOA LUON ca tieu de (khong de trong)."""
    heading_p = _tim_doan_tieu_de(doc, _GROUP_HEADINGS[group_key])
    if heading_p is None:
        return  # mau khong co dung tieu de nay - bo qua, khong loi cung (phong truong hop mau doi)

    # gom cac doan "- ..." ngay sau heading_p (dung XML de biet thu tu that)
    body = heading_p._element.getparent()
    all_ps = list(body.findall(f"{{{heading_p._element.nsmap['w']}}}p"))
    start_idx = all_ps.index(heading_p._element)
    old_bullet_elements = []
    idx = start_idx + 1
    while idx < len(all_ps):
        el = all_ps[idx]
        text = "".join(t.text or "" for t in el.iter(f"{{{heading_p._element.nsmap['w']}}}t"))
        if text.strip().startswith("- ") or text.strip() == "":
            old_bullet_elements.append(el)
            idx += 1
        else:
            break  # gap tieu de tiep theo hoac doan ket - dung lai

    if not old_bullet_elements:
        return

    if not cau_list:
        # khong co kien nghi nao cho nhom nay - xoa CA tieu de lan cac doan cu
        for el in old_bullet_elements:
            el.getparent().remove(el)
        heading_p._element.getparent().remove(heading_p._element)
        return

    template_bullet = old_bullet_elements[0]
    anchor = old_bullet_elements[-1]
    for cau in cau_list:
        new_el = copy.deepcopy(template_bullet)
        # thay text: xoa het run cu, dat 1 run moi voi noi dung "- {cau}"
        for t in new_el.iter(f"{{{heading_p._element.nsmap['w']}}}t"):
            t.text = ""
        first_t = next(new_el.iter(f"{{{heading_p._element.nsmap['w']}}}t"), None)
        if first_t is not None:
            first_t.text = f"- {cau}"
        anchor.addnext(new_el)
        anchor = new_el

    for el in old_bullet_elements:
        el.getparent().remove(el)


def build_cong_van_huong_dan_docx(session_data: dict, hang_muc_list: list) -> bytes:
    """session_data: {"quy_mo": dict tu quy_mo_store.get_quy_mo() (co the None)}.
    hang_muc_list: list dict {slot, kien_nghi} tu frontend (giong het shape
    da dung cho /export-kien-nghi, CHI THEM field "slot")."""
    if not TEMPLATE_PATH.exists():
        raise CongVanHuongDanError("Chưa có file mẫu công văn hướng dẫn — liên hệ quản trị hệ thống.")

    doc = Document(str(TEMPLATE_PATH))
    quy_mo = session_data.get("quy_mo") or {}

    replace_mergefield(doc, "tên_công_trình", quy_mo.get("tenCongTrinh"))
    replace_mergefield(doc, "chủ_đầu_tư", quy_mo.get("chuDauTu"))
    replace_mergefield(doc, "ĐỊA_ĐIỂM_XÂY_DỰNG", quy_mo.get("diaDiemXayDung"))
    replace_mergefield(doc, "ĐỊA_CHỈ_CHỦ_ĐẦU_TƯ", quy_mo.get("diaChiChuDauTu"))
    replace_mergefield(doc, "ĐƠN_VỊ_TƯ_VẤN_THIẾT_KẾ_PCCC", quy_mo.get("donViTuVanThietKe"))
    replace_mergefield(doc, "số_ngày_tháng_của_mẫu_số_PC11", quy_mo.get("soNgayPC11"))
    replace_mergefield(doc, "MÃ_HỒ_SƠ", quy_mo.get("maHoSo"))

    nhom_kien_nghi = _gom_kien_nghi_theo_nhom(hang_muc_list)
    for group_key, cau_list in nhom_kien_nghi.items():
        _thay_danh_sach_kien_nghi(doc, group_key, cau_list)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
