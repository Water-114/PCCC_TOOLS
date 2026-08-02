"""Batch 5A mở rộng ("Quy mô"/Form A) — test cho evaluate_bien_tam_thap()
(backend/app/services/phuong_tien.py), tách từ ghi chú có sẵn trong
evaluate_den() (TCVN 13456:2022 Điều 5.2.3) thành 1 hàm độc lập, giữ NGUYÊN
2 ngưỡng gốc: khách sạn ≥ 7 tầng, HOẶC khối tích ≥ 5.000 m³ và hành lang
thoát nạn > 10 m."""

from app.services.phuong_tien import evaluate_bien_tam_thap


def _p(occ, **kwargs):
    base = {"occ": occ, "floors": 0, "basements": 0, "semiBasements": 0, "totalArea": 0, "areaFloor": 0, "volume": 0}
    base.update(kwargs)
    return base


def test_khachsan_duoi_7_tang_va_khoi_tich_nho_khong_thuoc_dien():
    r = evaluate_bien_tam_thap(_p("khachsan", floors=6, volume=100))
    assert r["result"] == "no"


def test_khachsan_dung_nguong_7_tang_thuoc_dien():
    r = evaluate_bien_tam_thap(_p("khachsan", floors=7, volume=0))
    assert r["result"] == "yes"
    assert "7 tầng" in r["detail"]


def test_khoi_tich_5000_thieu_hanh_lang_chua_du_du_lieu():
    r = evaluate_bien_tam_thap(_p("chungcu", volume=5000))
    assert r["result"] == "chua_du_du_lieu"


def test_khoi_tich_5000_hanh_lang_tren_10m_thuoc_dien():
    r = evaluate_bien_tam_thap(_p("chungcu", volume=5000, hanhLangDaiNhat=10.5))
    assert r["result"] == "yes"


def test_khoi_tich_5000_hanh_lang_duoi_10m_khong_thuoc_dien():
    r = evaluate_bien_tam_thap(_p("chungcu", volume=5000, hanhLangDaiNhat=10))
    assert r["result"] == "no"


def test_non_khachsan_khoi_tich_nho_khong_thuoc_dien():
    r = evaluate_bien_tam_thap(_p("truso", volume=100))
    assert r["result"] == "no"


def test_rule_set_version_present():
    r = evaluate_bien_tam_thap(_p("chungcu"))
    assert r["rule_set_version"]
