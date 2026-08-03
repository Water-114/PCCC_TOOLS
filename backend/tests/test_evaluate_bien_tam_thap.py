"""Batch 5A mở rộng ("Quy mô"/Form A) — test cho evaluate_bien_tam_thap()
(backend/app/services/phuong_tien.py).

SỬA 2026-08-03 theo đính chính của owner từ văn bản quy định gốc: 3 điều
kiện (khách sạn / đủ quy mô ≥7 tầng hoặc ≥5.000 m³ / hành lang thoát nạn
>10m) là MỘT điều kiện gộp (AND), CHỈ áp dụng cho khách sạn — khác bản
trước (2 nhánh độc lập, nhánh khối tích áp dụng nhầm cho mọi công năng)."""

from app.services.phuong_tien import evaluate_bien_tam_thap


def _p(occ, **kwargs):
    base = {"occ": occ, "floors": 0, "basements": 0, "semiBasements": 0, "totalArea": 0, "areaFloor": 0, "volume": 0}
    base.update(kwargs)
    return base


def test_non_khachsan_khong_thuoc_dien_du_khoi_tich_lon():
    """Quan trong nhat: cong nang KHONG PHAI khach san thi KHONG thuoc dien,
    du khoi tich >=5000m3 va hanh lang >10m - khac han logic sai truoc day."""
    r = evaluate_bien_tam_thap(_p("truso", volume=6000, hanhLangDaiNhat=15))
    assert r["result"] == "no"


def test_khachsan_duoi_7_tang_va_khoi_tich_nho_khong_thuoc_dien():
    r = evaluate_bien_tam_thap(_p("khachsan", floors=6, volume=100))
    assert r["result"] == "no"


def test_khachsan_du_7_tang_nhung_thieu_hanh_lang_chua_du_du_lieu():
    """Khac ban truoc: >=7 tang KHONG con tu dong "yes" - van phai kiem tra
    hanh lang, thieu du lieu thi bao chua_du_du_lieu."""
    r = evaluate_bien_tam_thap(_p("khachsan", floors=7, volume=0))
    assert r["result"] == "chua_du_du_lieu"


def test_khachsan_du_7_tang_va_hanh_lang_tren_10m_thuoc_dien():
    r = evaluate_bien_tam_thap(_p("khachsan", floors=7, volume=0, hanhLangDaiNhat=10.5))
    assert r["result"] == "yes"
    assert "7 tầng" in r["detail"]


def test_khachsan_du_7_tang_nhung_hanh_lang_duoi_10m_khong_thuoc_dien():
    r = evaluate_bien_tam_thap(_p("khachsan", floors=7, volume=0, hanhLangDaiNhat=8))
    assert r["result"] == "no"


def test_khachsan_khoi_tich_5000_thieu_hanh_lang_chua_du_du_lieu():
    r = evaluate_bien_tam_thap(_p("khachsan", floors=3, volume=5000))
    assert r["result"] == "chua_du_du_lieu"


def test_khachsan_khoi_tich_5000_hanh_lang_tren_10m_thuoc_dien():
    r = evaluate_bien_tam_thap(_p("khachsan", floors=3, volume=5000, hanhLangDaiNhat=10.5))
    assert r["result"] == "yes"


def test_khachsan_khoi_tich_5000_hanh_lang_duoi_10m_khong_thuoc_dien():
    r = evaluate_bien_tam_thap(_p("khachsan", floors=3, volume=5000, hanhLangDaiNhat=10))
    assert r["result"] == "no"


def test_rule_set_version_present():
    r = evaluate_bien_tam_thap(_p("chungcu"))
    assert r["rule_set_version"]
