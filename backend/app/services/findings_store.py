"""Kho "findings" — chuyen doi items[] (da co san o moi reader, dang
{id, noi_dung_thiet_ke, ket_luan}, SAU khi da qua ket_luan_linter.fix_items())
sang 1 ban ghi finding co cau truc, lam nguon du lieu cho cac buoc sau cua
Pha 3 (bao cao tham dinh, linter tong hop) - xem ket_luan_linter.py, doi
chieu tai lieu "Bo quy tac doc ban ve va dien MDC" 03/9/2026 Phan VI.3.

PHAM VI Buoc 1 (co y THU HEP - xem prompt Pha 3 Buoc 1 cho ly do day du): CHI
dua tren du lieu DA CO trong items[] - KHONG gan can_cu/vi_tri_truc (2 thu
nay hien nam trong cau kien_nghi, kien_nghi la List[str] KHONG gan id nen
chua the tach doc lap theo tung finding ma khong doi schema AI). KHONG goi
them AI, KHONG doi bat ky reader/schema nao o buoc nay.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Finding:
    """1 dong ket luan cho 1 tieu chi (1 id) cua 1 form MDC, trong 1 phien Bo ho so."""
    id: int
    he_thong: str              # ten hang muc hien thi, vd "Bao chay tu dong"
    muc_form: str               # loai form MDC (khoa dung trong mdc_filler/quy_mo_store), vd "thuong"/"dien_pccc"/"quy_mo"
    trang_thai: str              # "dat" | "chua_dat" | "chua_the_hien" | "khong_ap_dung" (dung dung gia tri ai_schema.KetLuan)
    hien_trang: str              # = noi_dung_thiet_ke goc
    ky_hieu_ban_ve: str = ""     # tu so_hieu_ban_ve (hoac danh_muc_ban_ve neu nhieu file) cua ket qua doc
    session_id: Optional[int] = None


def build_findings(items: list, he_thong: str, muc_form: str, ky_hieu_ban_ve: str = "", session_id: Optional[int] = None) -> list:
    """items: list[dict] {id, noi_dung_thiet_ke, ket_luan} — dung nguyen dang
    tra ve tu 1 reader (SAU ket_luan_linter.fix_items(), xem aiho.py
    _answers_from_items()). Tra ve 1 Finding cho MOI item, KHONG loc theo
    trang_thai — loc (vd chi lay trang_thai != "dat") la viec cua noi GOI ham
    nay, khong phai viec cua ham nay."""
    findings = []
    for it in items:
        try:
            item_id = int(it.get("id"))
        except (TypeError, ValueError):
            continue
        findings.append(Finding(
            id=item_id,
            he_thong=he_thong,
            muc_form=muc_form,
            trang_thai=it.get("ket_luan"),
            hien_trang=it.get("noi_dung_thiet_ke") or "",
            ky_hieu_ban_ve=ky_hieu_ban_ve,
            session_id=session_id,
        ))
    return findings
