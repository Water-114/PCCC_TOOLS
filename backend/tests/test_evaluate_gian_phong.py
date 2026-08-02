"""Batch 5A mở rộng ("Quy mô"/Form A) — test cho evaluate_gian_phong_bao_chay()/
evaluate_gian_phong_sprinkler() (backend/app/services/he_thong_bat_buoc.py).

2 hàm này tách riêng khỏi evaluate_bao_chay()/evaluate_sprinkler() ("Đối với
nhà") vì Form A coi dòng "Đối với gian phòng" là 1 dòng "Đối tượng trang bị"
độc lập — logic bên trong TÁI DÙNG NGUYÊN _eval_a3() (không đổi ngưỡng), test
này chỉ khoá lại hành vi wrapper (chặn occ ngoài sanxuat/kho -> "na", occ đúng
-> gọi thẳng _eval_a3 với for_sprinkler tương ứng)."""

from app.services.he_thong_bat_buoc import (
    evaluate_gian_phong_bao_chay,
    evaluate_gian_phong_sprinkler,
    evaluate_sprinkler,
)


def _p(occ, **kwargs):
    base = {"occ": occ, "floors": 0, "totalArea": 0, "areaFloor": 0, "hFire": 0, "basements": 0, "semiBasements": 0}
    base.update(kwargs)
    return base


def test_gian_phong_bao_chay_na_for_non_sanxuat_kho():
    r = evaluate_gian_phong_bao_chay(_p("chungcu"))
    assert r["result"] == "na"
    assert "Bảng A.3" in r["can_cu"]


def test_gian_phong_sprinkler_na_for_non_sanxuat_kho():
    r = evaluate_gian_phong_sprinkler(_p("khachsan"))
    assert r["result"] == "na"


def test_gian_phong_bao_chay_kho_hang_ab_always_yes():
    r = evaluate_gian_phong_bao_chay(_p("kho", hazard="A", areaFloor=1))
    assert r["result"] == "yes"
    assert "bắt buộc báo cháy tự động" in r["detail"]


def test_gian_phong_bao_chay_kho_hang_c_tren_mat_dat_nguong_500():
    below = evaluate_gian_phong_bao_chay(_p("kho", hazard="C", areaFloor=499))
    at = evaluate_gian_phong_bao_chay(_p("kho", hazard="C", areaFloor=500))
    assert below["result"] == "no"
    assert at["result"] == "yes"


def test_gian_phong_sprinkler_kho_hang_ab_nguong_300():
    below = evaluate_gian_phong_sprinkler(_p("kho", hazard="A", areaFloor=299))
    at = evaluate_gian_phong_sprinkler(_p("kho", hazard="A", areaFloor=300))
    assert below["result"] == "no"
    assert at["result"] == "yes"


def test_gian_phong_sanxuat_hang_c_ham_luon_bat_buoc():
    r = evaluate_gian_phong_bao_chay(_p("sanxuat", hazard="C", basements=1))
    assert r["result"] == "yes"
    assert "hầm" in r["detail"]


def test_gian_phong_matches_eval_a3_directly_for_sprinkler_flag():
    """Ket qua cua evaluate_gian_phong_sprinkler() phai KHOP HET voi nhanh
    sanxuat/kho cua evaluate_sprinkler() (ca 2 deu goi _eval_a3(for_sprinkler=True))
    - dam bao wrapper khong lam lech gia tri ben trong."""
    payload = _p("sanxuat", hazard="C", areaFloor=350)
    assert evaluate_gian_phong_sprinkler(payload) == evaluate_sprinkler(payload)
