"""Batch 3, cụm 3 (nước chữa cháy sơ bộ) — golden/boundary test cho
backend/app/services/nuoc_chua_chay.py, đối chiếu với traBang11()/traBang12()/
traBang8()/traSprinkler()/tinh14496_1tang()/tinh14496_nhieutang()/
traBang1_14496() gốc trong js/tuvan-so-bo.js.

Theo quyết định của owner (docs/02-implementation-batches.md mục Batch 3):
đây là bản "đối chiếu song song" — production vẫn tính 100% ở client, test
dưới đây chỉ khoá lại đúng ngưỡng/công thức hiện có, không phải cơ chế phê
duyệt.

Test các hàm tra bảng nội bộ trực tiếp (import với dấu gạch dưới) để cô lập
chính xác từng ngưỡng, không phụ thuộc logic gating của evaluate_nuoc()."""

import pytest

from app.services.nuoc_chua_chay import (
    B1_7336,
    _he_so_psi_14496,
    _tinh_14496_1tang,
    _tinh_14496_nhieutang,
    _tra_bang_1_14496,
    _tra_bang_8,
    _tra_bang_11,
    _tra_bang_12,
    _tra_sprinkler,
)


def _p(**kwargs):
    base = {"floors": 0, "volume": 0}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Bảng 11 QCVN 06 — họng nước trong nhà (nhà ở & công cộng)
# ---------------------------------------------------------------------------
BANG11_CASES = [
    ("chungcu <=16 tang, hanh lang le10", _p(occ="chungcu", floors=16, corridor="le10"), {"n": 1, "q": 2.5}),
    ("chungcu <=16 tang, hanh lang gt10", _p(occ="chungcu", floors=16, corridor="gt10"), {"n": 2, "q": 2.5}),
    ("chungcu 17-25 tang, hanh lang le10", _p(occ="chungcu", floors=17, corridor="le10"), {"n": 2, "q": 2.5}),
    ("chungcu 17-25 tang, hanh lang gt10", _p(occ="chungcu", floors=25, corridor="gt10"), {"n": 3, "q": 2.5}),
    ("chungcu >25 tang la err", _p(occ="chungcu", floors=26, corridor="le10"), {"err": True}),
    ("nhahat duoi 300 cho", _p(occ="nhahat", floors=0, seats=300), {"n": 2, "q": 2.5}),
    ("nhahat tren 300 cho", _p(occ="nhahat", floors=0, seats=301), {"n": 2, "q": 5.0}),
    ("truso <=10 tang, V le 25000", _p(occ="truso", floors=10, volume=25000), {"n": 1, "q": 2.5}),
    ("truso <=10 tang, V gt 25000", _p(occ="truso", floors=10, volume=25001), {"n": 2, "q": 2.5}),
    ("truso >10 tang, V le 25000", _p(occ="truso", floors=11, volume=25000), {"n": 2, "q": 2.5}),
    ("truso >10 tang, V gt 25000", _p(occ="truso", floors=11, volume=25001), {"n": 3, "q": 2.5}),
    ("khachsan (nha cong cong) <=10 tang V le 25000", _p(occ="khachsan", floors=10, volume=25000), {"n": 1, "q": 2.5}),
]


@pytest.mark.parametrize("description,payload,expected", BANG11_CASES, ids=[c[0] for c in BANG11_CASES])
def test_tra_bang_11_golden(description, payload, expected):
    result = _tra_bang_11(payload)
    if expected.get("err"):
        assert "err" in result, description
    else:
        assert result["n"] == expected["n"], description
        assert result["q"] == expected["q"], description


# ---------------------------------------------------------------------------
# Bảng 12 QCVN 06 — họng nước trong nhà (nhà SX/kho)
# ---------------------------------------------------------------------------
BANG12_CASES = [
    ("bac I, hangA, S0, V le 150000", _p(bcl="I", hazard="A", capS="S0", volume=150000), {"n": 2, "q": 2.5}),
    ("bac I, hangA, S0, V gt 150000", _p(bcl="I", hazard="A", capS="S0", volume=150001), {"n": 3, "q": 2.5}),
    ("bac I, hangD (khong xet S)", _p(bcl="I", hazard="D", capS="", volume=0), {"n": 1, "q": 2.5}),
    ("bac III, hangC, S0, V le", _p(bcl="III", hazard="C", capS="S0", volume=100000), {"n": 2, "q": 2.5}),
    ("bac III, hangD, S0, V le", _p(bcl="III", hazard="D", capS="S0", volume=100000), {"n": 1, "q": 2.5}),
    ("bac IV, hangC, S0S1, V le", _p(bcl="IV", hazard="C", capS="S1", volume=100000), {"n": 2, "q": 2.5}),
    ("bac IV, hangC, S0S1, V gt", _p(bcl="IV", hazard="C", capS="S1", volume=150001), {"n": 2, "q": 5}),
    ("bac IV, hangC, S2S3, V le", _p(bcl="IV", hazard="C", capS="S2", volume=100000), {"n": 3, "q": 2.5}),
    ("bac IV, hangC, S2S3, V gt", _p(bcl="IV", hazard="C", capS="S3", volume=150001), {"n": 4, "q": 2.5}),
    ("bac IV, hangD, V le -> q 2.5 (khac Bang1 TCVN14496)", _p(bcl="IV", hazard="D", capS="", volume=100000), {"n": 1, "q": 2.5}),
    ("bac IV, hangD, V gt -> q 2.5 (khac Bang1 TCVN14496 q=2)", _p(bcl="IV", hazard="D", capS="", volume=150001), {"n": 2, "q": 2.5}),
    ("bac V, hangC, V le", _p(bcl="V", hazard="C", capS="", volume=100000), {"n": 2, "q": 2.5}),
    # bac I/II: hang D/E khong xet capS (luon tag(1,2.5)) - to hop khong khop
    # phai la hang A/B/C VOI capS ngoai S0/S1 (vd S2), khong roi vao nhanh nao.
    ("to hop khong hop le la err", _p(bcl="I", hazard="A", capS="S2", volume=0), {"err": True}),
]


@pytest.mark.parametrize("description,payload,expected", BANG12_CASES, ids=[c[0] for c in BANG12_CASES])
def test_tra_bang_12_golden(description, payload, expected):
    result = _tra_bang_12(payload)
    if expected.get("err"):
        assert "err" in result, description
    else:
        assert result["n"] == expected["n"], description
        assert result["q"] == expected["q"], description


# ---------------------------------------------------------------------------
# Bảng 1 TCVN 14496 — họng nước trong nhà cho kho kệ cao (khác Bảng 12!)
# ---------------------------------------------------------------------------
BANG1_14496_CASES = [
    ("bac IV, hangD, V le -> q 2.5", _p(bcl="IV", hazard="D", capS="", volume=100000), {"n": 1, "q": 2.5}),
    ("bac IV, hangD, V gt -> q 2 (KHAC Bang 12 QCVN06 q=2.5)", _p(bcl="IV", hazard="D", capS="", volume=150001), {"n": 2, "q": 2}),
    ("bac III, hangA, S0, V le", _p(bcl="III", hazard="A", capS="S0", volume=100000), {"n": 2, "q": 2.5}),
    ("bac III, hangC, S0S1, V le", _p(bcl="III", hazard="C", capS="S1", volume=100000), {"n": 2, "q": 2.5}),
    ("bac III, hangC, S0S1, V gt", _p(bcl="III", hazard="C", capS="S0", volume=150001), {"n": 2, "q": 5}),
]


@pytest.mark.parametrize("description,payload,expected", BANG1_14496_CASES, ids=[c[0] for c in BANG1_14496_CASES])
def test_tra_bang_1_14496_golden(description, payload, expected):
    result = _tra_bang_1_14496(payload)
    assert result["n"] == expected["n"], description
    assert result["q"] == expected["q"], description


# ---------------------------------------------------------------------------
# Bảng 8 QCVN 06 — cấp nước ngoài nhà
# ---------------------------------------------------------------------------
BANG8_CASES = [
    ("<=3 tang, V<=1000", _p(floors=3, volume=1000), 10),
    ("<=3 tang, 1000<V<=5000", _p(floors=3, volume=5000), 10),
    ("<=3 tang, 5000<V<=25000", _p(floors=3, volume=25000), 15),
    ("<=3 tang, 25000<V<=50000", _p(floors=3, volume=50000), 20),
    ("<=3 tang, V>50000", _p(floors=3, volume=50001), 25),
    ("4-12 tang, V<=1000", _p(floors=12, volume=1000), 10),
    ("13-16 tang, V<=1000 la err (dau -)", _p(floors=16, volume=1000), None),
    ("13-16 tang, 1000<V<=5000", _p(floors=16, volume=5000), 20),
    (">16 tang, V<=1000 la err", _p(floors=17, volume=1000), None),
    (">16 tang, 25000<V<=50000", _p(floors=17, volume=50000), 30),
]


@pytest.mark.parametrize("description,payload,expected_q", BANG8_CASES, ids=[c[0] for c in BANG8_CASES])
def test_tra_bang_8_golden(description, payload, expected_q):
    result = _tra_bang_8(payload)
    if expected_q is None:
        assert "err" in result, description
    else:
        assert result["Q"] == expected_q, description


# ---------------------------------------------------------------------------
# traSprinkler — Bảng 1/2/3 TCVN 7336 + bọt (foam) + uỷ quyền kho kệ cao
# ---------------------------------------------------------------------------
def test_sprinkler_bang1_nhom_thuong():
    result = _tra_sprinkler(_p(nhomNC="1"))
    assert result["Q"] == B1_7336["1"]["Q"] == 10
    assert result["t"] == B1_7336["1"]["t"] == 30


def test_sprinkler_bang1_nhom2_co_ghi_chu_tai_trong_chay():
    result = _tra_sprinkler(_p(nhomNC="2"))
    assert result["Q"] == 30 and result["t"] == 60
    assert result["note"] is not None


def test_sprinkler_hbaove_duoi_10_dung_bang1():
    result = _tra_sprinkler(_p(nhomNC="1", hBaoVe=9))
    assert result["Q"] == 10  # Bang 1, khong phai Bang 3


def test_sprinkler_hbaove_dung_nguong_10_dung_bang3():
    result = _tra_sprinkler(_p(nhomNC="1", hBaoVe=10))
    assert result["Q"] == 12  # Bang 3, dai <=12m, nhom 1


def test_sprinkler_hbaove_tren_20_la_err():
    result = _tra_sprinkler(_p(nhomNC="1", hBaoVe=21))
    assert "err" in result


def test_sprinkler_nhom5_hxep_thuong():
    result = _tra_sprinkler(_p(nhomNC="5", hXep="3"))
    assert result["Q"] == 45  # B2_7336["5"]["3"]
    assert result["t"] == 60


def test_sprinkler_foam_nhom_4_2():
    result = _tra_sprinkler(_p(nhomNC="4.2", botS=100, botJ=0.5, botT=10, botK=1.05, botCB=6))
    assert result["foam"] is True
    Qct = 100 * 0.5
    Wdd = 1.05 * Qct * 10 * 60
    assert result["Qct"] == pytest.approx(Qct)
    assert result["Wdd"] == pytest.approx(Wdd)
    assert result["Wctb"] == pytest.approx(Wdd * 6 / 100)
    assert result["Wnuoc"] == pytest.approx(Wdd * 94 / 100)


def test_sprinkler_ke_cao_uy_quyen_1tang():
    result = _tra_sprinkler(_p(nhomNC="5", hXep="cao", phuongAn14496="1tang", nhomNC14496="5", hXepM=8, hGianPhong=10, soDauPhun90=4))
    assert result["kecao"] is True
    assert result["res"]["Qs"] is not None


def test_sprinkler_missing_nhom_khong_crash_500_ma_tra_err():
    """Bug-preemption: neu nhomNC trong (chua chon), JS goc se crash truy cap
    thuoc tinh cua undefined; ban port phai tra ve loi mem, khong duoc raise
    exception khong kiem soat (route se doi thanh 400)."""
    result = _tra_sprinkler(_p(nhomNC=""))
    assert "err" in result


# ---------------------------------------------------------------------------
# TCVN 14496 — kho kệ cao
# ---------------------------------------------------------------------------
def test_he_so_psi_boundary():
    assert _he_so_psi_14496(6.4) == 0
    assert _he_so_psi_14496(6.41) == 0.06


def test_1tang_nhom_khong_hop_le():
    result = _tinh_14496_1tang(_p(nhomNC14496="1", hXepM=8, hGianPhong=10, soDauPhun90=4))
    assert "err" in result


def test_1tang_h_gian_phong_qua_14m():
    result = _tinh_14496_1tang(_p(nhomNC14496="5", hXepM=8, hGianPhong=14.1, soDauPhun90=4))
    assert "err" in result


def test_1tang_h_xep_qua_12_5m():
    result = _tinh_14496_1tang(_p(nhomNC14496="5", hXepM=12.6, hGianPhong=10, soDauPhun90=4))
    assert "err" in result


def test_1tang_h_xep_duoi_5_5m():
    result = _tinh_14496_1tang(_p(nhomNC14496="5", hXepM=5.4, hGianPhong=10, soDauPhun90=4))
    assert "err" in result


def test_1tang_cong_thuc_qcd_dung():
    result = _tinh_14496_1tang(_p(nhomNC14496="5", hXepM=8, hGianPhong=10, soDauPhun90=4))
    q55 = 5.3
    psi = _he_so_psi_14496(10)
    expected_qcd = (q55 + 0.19 * (8 - 5.5)) * (1 + psi * (10 - 10))
    assert result["qcd"] == pytest.approx(expected_qcd)
    assert result["Qs"] == pytest.approx(expected_qcd * 4)


def test_1tang_thieu_so_dau_phun_tra_qs_none():
    result = _tinh_14496_1tang(_p(nhomNC14496="6", hXepM=8, hGianPhong=10))
    assert result["Qs"] is None
    assert result["qcd"] is not None


def test_nhieutang_h_duoi_5_5m():
    result = _tinh_14496_nhieutang(_p(hXepM2=5.4))
    assert "err" in result


def test_nhieutang_h_tren_25m():
    result = _tinh_14496_nhieutang(_p(hXepM2=25.1))
    assert "err" in result


def test_nhieutang_thieu_du_lieu():
    result = _tinh_14496_nhieutang(_p(hXepM2=10))
    assert "err" in result
    assert "Loại pallet" in result["err"]


def test_nhieutang_cong_thuc_dung():
    payload = _p(hXepM2=10, loaiPallet14496="phang", chieuRongKeB=2.4, soTamChan=3,
                 loaiHang14496="ranco", daiCaoDo14496="tu2den3", dienTichMai90=90)
    result = _tinh_14496_nhieutang(payload)
    A, B, n, i = 9, 2.4, 3, 0.36
    Qi = A * B * n * i
    iD = 0.12  # h<=16
    Qd = iD * 90
    assert result["Qi"] == pytest.approx(Qi)
    assert result["Qd"] == pytest.approx(Qd)
    assert result["Qs"] == pytest.approx(Qi + Qd)


def test_nhieutang_id_doi_khi_h_tren_16m():
    payload = _p(hXepM2=17, loaiPallet14496="phang", chieuRongKeB=2.4, soTamChan=3,
                 loaiHang14496="ranco", daiCaoDo14496="tu2den3")
    result = _tinh_14496_nhieutang(payload)
    assert result["iD"] == 0.18
    assert result["Sd"] == 90  # mac dinh khi khong nhap dienTichMai90


# ---------------------------------------------------------------------------
# Regression: sua loi mapping hXepM -> hXepM2 o che do nhieu tang dau phun
# (yeu cau cua owner sau khi review Cum 3 lan 1) — dam bao ham nay CHI doc
# hXepM2, khong con bi anh huong boi hXepM (field cua che do 1 tang dau phun).
# ---------------------------------------------------------------------------
def test_nhieutang_hxepm_trong_hxepm2_hop_le_van_tinh_duoc():
    """hXepM de trong, hXepM2 hop le -> van tinh duoc binh thuong (khong con
    phu thuoc hXepM nhu truoc khi sua)."""
    payload = _p(hXepM2=10, loaiPallet14496="phang", chieuRongKeB=2.4, soTamChan=3,
                 loaiHang14496="ranco", daiCaoDo14496="tu2den3", dienTichMai90=90)
    assert "hXepM" not in payload
    result = _tinh_14496_nhieutang(payload)
    assert "err" not in result
    assert result["Qs"] is not None


def test_nhieutang_dung_hxepm2_khong_dung_hxepm_khi_khac_gia_tri():
    """hXepM va hXepM2 khac nhau -> ket qua PHAI theo hXepM2 (dung field cua
    che do nhieu tang), khong duoc lay theo hXepM (field cua che do 1 tang)."""
    payload_dung_m2 = _p(hXepM=3, hXepM2=17, loaiPallet14496="phang", chieuRongKeB=2.4,
                         soTamChan=3, loaiHang14496="ranco", daiCaoDo14496="tu2den3")
    result = _tinh_14496_nhieutang(payload_dung_m2)
    # Neu con doc nham hXepM=3 (< 5.5) se ra "err"; dung hXepM2=17 phai tinh
    # duoc va iD phai la 0.18 (h>16m), KHONG phai 0.12.
    assert "err" not in result
    assert result["iD"] == 0.18

    payload_hxepm_thap_hxepm2_thap = _p(hXepM=20, hXepM2=10, loaiPallet14496="phang",
                                        chieuRongKeB=2.4, soTamChan=3, loaiHang14496="ranco",
                                        daiCaoDo14496="tu2den3")
    result2 = _tinh_14496_nhieutang(payload_hxepm_thap_hxepm2_thap)
    # Neu con doc nham hXepM=20 (>16) se ra iD=0.18; dung hXepM2=10 (<=16m)
    # phai ra iD=0.12.
    assert result2["iD"] == 0.12


def test_nhieutang_nguong_hxepm2_16m_cho_cuong_do_phun_duoi_mai():
    """Nguong hXepM2 <=16m va >16m quyet dinh iD (cuong do phun duoi mai)."""
    payload_le16 = _p(hXepM2=16, loaiPallet14496="phang", chieuRongKeB=2.4, soTamChan=3,
                      loaiHang14496="ranco", daiCaoDo14496="tu2den3")
    assert _tinh_14496_nhieutang(payload_le16)["iD"] == 0.12

    payload_tren16 = _p(hXepM2=16.01, loaiPallet14496="phang", chieuRongKeB=2.4, soTamChan=3,
                        loaiHang14496="ranco", daiCaoDo14496="tu2den3")
    assert _tinh_14496_nhieutang(payload_tren16)["iD"] == 0.18
