"""Batch 3, cụm 4 (phương tiện & hạng mục khác) — golden test cho
backend/app/services/phuong_tien.py, đối chiếu với evalPhaDo()/evalMatNa()/
evalCoGioi()/evalLoa()/evalBinh()/evalDen() gốc trong js/tuvan-so-bo.js.

Theo quyết định của owner (docs/02-implementation-batches.md mục Batch 3):
đây là bản "đối chiếu song song" — production vẫn tính 100% ở client, test
dưới đây chỉ khoá lại đúng ngưỡng/công thức/nội dung hiện có."""

import math

import pytest

from app.services.phuong_tien import (
    BINH_TBL,
    evaluate_binh,
    evaluate_co_gioi,
    evaluate_den,
    evaluate_loa,
    evaluate_mat_na,
    evaluate_pha_do,
)


def _p(occ, **kwargs):
    base = {"occ": occ, "floors": 0, "basements": 0, "semiBasements": 0, "totalArea": 0, "areaFloor": 0, "volume": 0}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Nhóm A: evaluate_pha_do / evaluate_mat_na / evaluate_co_gioi
# ---------------------------------------------------------------------------
PHA_DO_CASES = [
    ("sanxuat -> muc 1", _p("sanxuat"), "yes", "1"),
    ("kho -> muc 2", _p("kho"), "yes", "2"),
    ("chungcu -> muc 3", _p("chungcu"), "yes", "3"),
    ("khachsan -> muc 3", _p("khachsan"), "yes", "3"),
    ("truso -> muc 4", _p("truso"), "yes", "4"),
    ("truonghoc -> muc 4", _p("truonghoc"), "yes", "4"),
    ("yte -> muc 4", _p("yte"), "yes", "4"),
    ("nhaga -> muc 5", _p("nhaga"), "yes", "5"),
    ("karaoke -> muc 6", _p("karaoke"), "yes", "6"),
    ("nhahat -> muc 6", _p("nhahat"), "yes", "6"),
    ("tttm -> muc 7", _p("tttm"), "yes", "7"),
    ("nhatre khong trong 7 muc -> no", _p("nhatre"), "no", None),
]


@pytest.mark.parametrize("description,payload,expected_result,expected_muc", PHA_DO_CASES, ids=[c[0] for c in PHA_DO_CASES])
def test_pha_do_golden(description, payload, expected_result, expected_muc):
    r = evaluate_pha_do(payload)
    assert r["result"] == expected_result, description
    if expected_muc:
        assert f"mục {expected_muc}" in r["can_cu"], description
    assert r["rule_set_version"]


MAT_NA_CASES = [
    ("khachsan duoi 3 tang -> no", _p("khachsan", floors=2), "no"),
    ("khachsan dung nguong 3 tang -> yes", _p("khachsan", floors=3), "yes"),
    ("karaoke luon yes", _p("karaoke"), "yes"),
    ("occ khac -> na", _p("truso"), "na"),
]


@pytest.mark.parametrize("description,payload,expected", MAT_NA_CASES, ids=[c[0] for c in MAT_NA_CASES])
def test_mat_na_golden(description, payload, expected):
    assert evaluate_mat_na(payload)["result"] == expected, description


CO_GIOI_CASES = [
    ("sanxuat luon na", _p("sanxuat"), "na"),
    ("kho luon na", _p("kho"), "na"),
    ("chungcu luon na", _p("chungcu"), "na"),
]


@pytest.mark.parametrize("description,payload,expected", CO_GIOI_CASES, ids=[c[0] for c in CO_GIOI_CASES])
def test_co_gioi_luon_na(description, payload, expected):
    assert evaluate_co_gioi(payload)["result"] == expected, description


# ---------------------------------------------------------------------------
# evaluate_loa — nhiều điều kiện độc lập (TT1, TT2, TT3, TT4, TT6)
# ---------------------------------------------------------------------------
def test_loa_tt1_qua_10_tang():
    r = evaluate_loa(_p("chungcu", floors=11))
    assert r["result"] == "yes"
    assert "1" in r["can_cu"]


def test_loa_tt1_dung_10_tang_chua_dat():
    r = evaluate_loa(_p("chungcu", floors=10))
    assert r["result"] == "no"


def test_loa_tt1_2_tang_ham():
    r = evaluate_loa(_p("chungcu", floors=5, basements=2))
    assert r["result"] == "yes"


def test_loa_tt2_thieu_ppl_floor_co_ghi_chu_khong_loi():
    r = evaluate_loa(_p("karaoke"))
    assert r["result"] == "no"
    assert any("TT 2" in n for n in r["notes"])


def test_loa_tt2_du_50_nguoi():
    r = evaluate_loa(_p("karaoke", pplFloor=50))
    assert r["result"] == "yes"


def test_loa_tt2_duoi_50_nguoi():
    r = evaluate_loa(_p("nhahat", pplFloor=49))
    assert r["result"] == "no"


def test_loa_tt3_garakin_dang_kin_du_18000():
    r = evaluate_loa(_p("garakin", garaKin="kin", totalArea=18000))
    assert r["result"] == "yes"


def test_loa_tt3_garakin_dang_ho_khong_ap_dung():
    r = evaluate_loa(_p("garakin", garaKin="ho", totalArea=99999))
    assert r["result"] == "no"


def test_loa_tt4_sanxuat_dong_thoi_dat():
    r = evaluate_loa(_p("sanxuat", totalArea=18000, pplFloor=300))
    assert r["result"] == "yes"


def test_loa_tt4_sanxuat_chi_dat_1_dieu_kien_khong_du():
    r = evaluate_loa(_p("sanxuat", totalArea=18000, pplFloor=299))
    assert r["result"] == "no"


def test_loa_tt6_nhaga_luon_yes():
    r = evaluate_loa(_p("nhaga"))
    assert r["result"] == "yes"


def test_loa_nhieu_muc_dat_dong_thoi_gom_ca_2():
    """chungcu vua dat TT1 (qua 10 tang) - chi co 1 muc ap dung cho chungcu
    (TT1), nhung nhaga vua thuoc TT1_CONGCONG vua luon dat TT6 -> phai gom
    ca 2 muc trong can_cu."""
    r = evaluate_loa(_p("nhaga", floors=11))
    assert r["result"] == "yes"
    assert "1" in r["can_cu"] and "6" in r["can_cu"]


# ---------------------------------------------------------------------------
# evaluate_binh — công thức + ranh giới (areaFloor<100, bội số dt)
# ---------------------------------------------------------------------------
def test_binh_luon_yes():
    assert evaluate_binh(_p("truso"))["result"] == "yes"


def test_binh_auto_suy_ra_theo_occ():
    r = evaluate_binh(_p("sanxuat", areaFloor=100))
    assert r["lv"] == "cao"  # sanxuat -> cao trong _OCC_BINH_LEVEL


def test_binh_extlevel_ghi_de_auto():
    r = evaluate_binh(_p("sanxuat", areaFloor=100, extLevel="thap"))
    assert r["lv"] == "thap"


def test_binh_nguong_area_floor_duoi_100_min_la_1():
    r = evaluate_binh(_p("truso", areaFloor=99, extLevel="thap"))
    # thap: dt=300, ceil(99/300)=1; min=1 (areaFloor<100) -> n=max(1,1)=1
    assert "≥ 1 bình/tầng" in r["detail"]


def test_binh_nguong_area_floor_dung_100_min_la_2():
    r = evaluate_binh(_p("truso", areaFloor=100, extLevel="thap"))
    # thap: dt=300, ceil(100/300)=1; min=2 (areaFloor>=100) -> n=max(1,2)=2
    assert "≥ 2 bình/tầng" in r["detail"]


@pytest.mark.parametrize("lv,dt", [("thap", 300), ("tb", 150), ("cao", 100)])
def test_binh_cong_thuc_ceil_dung_boi_so_dt(lv, dt):
    assert BINH_TBL[lv]["dt"] == dt
    for area in (dt - 1, dt, dt + 1, 2 * dt, 2 * dt + 1):
        r = evaluate_binh(_p("truso", areaFloor=area, extLevel=lv))
        expected_n1 = math.ceil(area / dt)
        expected_min = 1 if area < 100 else 2
        expected_n = max(expected_n1, expected_min)
        assert f"≥ {expected_n} bình/tầng" in r["detail"], f"lv={lv} area={area}"


# ---------------------------------------------------------------------------
# evaluate_den — nội dung nào xuất hiện đúng điều kiện nào (không so yes/no)
# ---------------------------------------------------------------------------
def test_den_luon_yes():
    assert evaluate_den(_p("truso"))["result"] == "yes"


def test_den_7_vi_tri_co_ban():
    r = evaluate_den(_p("truso"))
    assert len(r["pos"]) == 7


def test_den_them_gara_ham_khi_la_garakin():
    r = evaluate_den(_p("garakin"))
    assert len(r["pos"]) == 8
    assert "Gara" in r["pos"][4]


def test_den_them_gara_ham_khi_co_tang_ham():
    r = evaluate_den(_p("truso", basements=1))
    assert len(r["pos"]) == 8


def test_den_them_gara_ham_khi_co_ban_ham():
    r = evaluate_den(_p("truso", semiBasements=1))
    assert len(r["pos"]) == 8


def test_den_khong_them_gara_ham_khi_khong_thoa_dieu_kien():
    r = evaluate_den(_p("truso"))
    assert not any("Gara" in p for p in r["pos"])


def test_den_khachsan_duoi_7_tang_ghi_chu_co_so_luu_tru():
    r = evaluate_den(_p("khachsan", floors=5))
    assert "Cơ sở lưu trú" in r["notes"][0]
    assert not any("BIỂN TẦM THẤP" in n for n in r["notes"])


def test_den_khachsan_tu_7_tang_ghi_chu_bien_tam_thap():
    r = evaluate_den(_p("khachsan", floors=7))
    assert "BIỂN TẦM THẤP" in r["notes"][0]


def test_den_khong_phai_khachsan_khong_co_ghi_chu_luu_tru():
    r = evaluate_den(_p("truso", floors=10))
    assert not any("lưu trú" in n or "BIỂN TẦM THẤP" in n for n in r["notes"])


def test_den_khoi_tich_duoi_5000_khong_co_ghi_chu_bien_tam_thap_hanh_lang():
    r = evaluate_den(_p("truso", volume=4999))
    assert not any("hành lang thoát nạn" in n for n in r["notes"])


def test_den_khoi_tich_tu_5000_co_ghi_chu():
    r = evaluate_den(_p("truso", volume=5000))
    assert any("hành lang thoát nạn" in n for n in r["notes"])


def test_den_area_floor_duoi_1000_ghi_chu_2_loi_ra():
    r = evaluate_den(_p("truso", areaFloor=1000))
    assert any("≥ 2 lối ra thoát nạn" in n for n in r["notes"])
    assert not any("SƠ ĐỒ CHỈ DẪN THOÁT NẠN" in n for n in r["notes"])


def test_den_area_floor_tren_1000_ghi_chu_so_do_bat_buoc():
    r = evaluate_den(_p("truso", areaFloor=1001))
    assert any("SƠ ĐỒ CHỈ DẪN THOÁT NẠN" in n for n in r["notes"])
