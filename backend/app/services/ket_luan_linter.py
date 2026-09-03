"""Kiem tra + tu sua loi "Ket luan = KN nhung noi dung da noi khong ap dung"
(doi chieu tu tai lieu "Bo quy tac doc ban ve va dien MDC" 03/9/2026, Phan IV
+ Phan V checklist #12) - day la loi lap nhieu nhat theo tai lieu: AI ghi ro
trong noi_dung_thiet_ke rang he thong/noi dung "khong su dung/khong co/khong
thuoc pham vi" nhung van chon ket_luan la chua_dat/chua_the_hien (-> hien
"KN" tren file .docx xuat ra, SAI vi day khong phai loi cua don vi thiet ke -
xem ai_schema.KetLuan cho dung 4 trang thai).

Sua 1 CHIEU AN TOAN: chua_dat/chua_the_hien -> khong_ap_dung khi khop cum tu.
KHONG BAO GIO sua "dat" hoac "khong_ap_dung" - chi cham vao 2 gia tri co the
la loi.
"""

import logging

logger = logging.getLogger(__name__)

_KHONG_AP_DUNG_PATTERNS = (
    "không sử dụng",
    "không có hệ thống",
    "không có thiết bị",
    "không thuộc phạm vi",
    "không trang bị",
    "không thiết kế",
    "không dùng",
    "không bố trí",
)

def fix_items(items):
    """items: list[dict] co {id, noi_dung_thiet_ke, ket_luan, ...}. Tra ve
    list MOI (khong sua in-place) voi ket_luan da duoc sua neu can."""
    fixed = []
    for it in items:
        noi_dung = (it.get("noi_dung_thiet_ke") or "").lower()
        ket_luan = it.get("ket_luan")
        if ket_luan in ("chua_dat", "chua_the_hien") and any(p in noi_dung for p in _KHONG_AP_DUNG_PATTERNS):
            logger.info(
                "ket_luan_linter: sua id=%s tu '%s' -> 'khong_ap_dung' (noi_dung_thiet_ke='%s')",
                it.get("id"), ket_luan, it.get("noi_dung_thiet_ke"),
            )
            it = {**it, "ket_luan": "khong_ap_dung"}
        fixed.append(it)
    return fixed
