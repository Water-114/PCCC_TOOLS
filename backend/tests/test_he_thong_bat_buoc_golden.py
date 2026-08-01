"""Batch 3, cụm 2 (hệ thống bắt buộc) — golden/boundary test cho
backend/app/services/he_thong_bat_buoc.py, so khớp với evalBaoChay()/
evalA3()/evalSprinkler()/evalHongNuoc()/evalNgoaiNha() gốc trong
js/tuvan-so-bo.js (QCVN 10:2025/BCA — Bảng A.1, Bảng A.3, Phụ lục B, C).

Theo quyết định của owner (xem docs/02-implementation-batches.md mục Batch 3):
đây là bản "đối chiếu song song" — production vẫn tính 100% ở client bằng
bản JS gốc, KHÔNG có endpoint nào gọi service này. Test dưới đây chỉ khoá
lại đúng ngưỡng hiện có để bắt được thay đổi vô tình, không phải cơ chế phê
duyệt ngưỡng đúng/sai theo quy định.
"""

import pytest

from app.services.he_thong_bat_buoc import (
    evaluate_bao_chay,
    evaluate_hong_nuoc,
    evaluate_ngoai_nha,
    evaluate_sprinkler,
)


def _payload(occ, **kwargs):
    base = {"occ": occ, "floors": 0, "totalArea": 0, "areaFloor": 0, "hFire": 0, "basements": 0, "semiBasements": 0}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# evaluate_bao_chay — QCVN 10:2025/BCA Bảng A.1
# ---------------------------------------------------------------------------
BAO_CHAY_CASES = [
    ("chungcu duoi nguong", _payload("chungcu", floors=4, totalArea=699), "no"),
    ("chungcu dung nguong tang", _payload("chungcu", floors=5, totalArea=0), "yes"),
    ("chungcu dung nguong dien tich", _payload("chungcu", floors=0, totalArea=700), "yes"),

    ("nhatre duoi nguong", _payload("nhatre", kids=99, totalArea=299), "no"),
    ("nhatre dung nguong so tre", _payload("nhatre", kids=100, totalArea=0), "yes"),
    ("nhatre dung nguong dien tich", _payload("nhatre", kids=0, totalArea=300), "yes"),

    ("truonghoc duoi nguong", _payload("truonghoc", floors=4, totalArea=1499), "no"),
    ("truonghoc dung nguong tang", _payload("truonghoc", floors=5, totalArea=0), "yes"),

    ("yte duoi nguong", _payload("yte", floors=2, totalArea=299), "no"),
    ("yte dung nguong tang", _payload("yte", floors=3, totalArea=0), "yes"),

    ("thethao duoi nguong", _payload("thethao", totalArea=499, seats=199), "no"),
    ("thethao dung nguong dien tich", _payload("thethao", totalArea=500, seats=0), "yes"),
    ("thethao dung nguong cho ngoi", _payload("thethao", totalArea=0, seats=200), "yes"),

    ("nhahat duoi nguong", _payload("nhahat", totalArea=499), "no"),
    ("nhahat dung nguong", _payload("nhahat", totalArea=500), "yes"),

    ("baotang co ham luon yes", _payload("baotang", basements=1), "yes"),
    ("baotang tren mat dat 3 tang luon yes", _payload("baotang", floors=3), "yes"),
    ("baotang 1-2 tang duoi nguong", _payload("baotang", floors=2, totalArea=499), "no"),
    ("baotang 1-2 tang dung nguong", _payload("baotang", floors=1, totalArea=500), "yes"),

    ("vanhoa duoi nguong", _payload("vanhoa", floors=4, totalArea=499), "no"),
    ("vanhoa dung nguong tang", _payload("vanhoa", floors=5, totalArea=0), "yes"),

    ("karaoke luon yes", _payload("karaoke"), "yes"),
    ("tttm luon yes", _payload("tttm"), "yes"),

    ("nhahang duoi nguong", _payload("nhahang", totalArea=499), "no"),
    ("nhahang dung nguong", _payload("nhahang", totalArea=500), "yes"),

    ("cuahang co ham luon yes", _payload("cuahang", basements=1), "yes"),
    ("cuahang duoi nguong", _payload("cuahang", floors=2, totalArea=299), "no"),
    ("cuahang dung nguong tang", _payload("cuahang", floors=3, totalArea=0), "yes"),

    ("khachsan duoi nguong", _payload("khachsan", floors=2, totalArea=699), "no"),
    ("khachsan dung nguong tang", _payload("khachsan", floors=3, totalArea=0), "yes"),

    ("buudien duoi nguong", _payload("buudien", floors=2, totalArea=499), "no"),
    ("buudien dung nguong tang", _payload("buudien", floors=3, totalArea=0), "yes"),

    ("truso duoi nguong", _payload("truso", floors=4, totalArea=499), "no"),
    ("truso dung nguong tang", _payload("truso", floors=5, totalArea=0), "yes"),

    ("honhop duoi nguong", _payload("honhop", floors=2, totalArea=499), "no"),
    ("honhop dung nguong tang", _payload("honhop", floors=3, totalArea=0), "yes"),

    ("nhaga duoi nguong", _payload("nhaga", totalArea=499), "no"),
    ("nhaga dung nguong", _payload("nhaga", totalArea=500), "yes"),

    # garakin — dang kin co ham hoac >=2 tang: luon yes
    ("garakin kin co ham luon yes", _payload("garakin", basements=1), "yes"),
    ("garakin kin 2 tang luon yes", _payload("garakin", floors=2), "yes"),
    # dang ho, khoang cach <=12m: F>=4000 || T>=4
    ("garakin ho le12 duoi nguong", _payload("garakin", floors=0, garaKin="ho", garaKC12="le12", totalArea=3999), "no"),
    ("garakin ho le12 dung nguong dt", _payload("garakin", floors=0, garaKin="ho", garaKC12="le12", totalArea=4000), "yes"),
    ("garakin ho le12 dung nguong tang", _payload("garakin", floors=4, garaKin="ho", garaKC12="le12", totalArea=0), "yes"),
    # dang ho, khoang cach >12m: luon yes
    ("garakin ho gt12 luon yes", _payload("garakin", floors=0, garaKin="ho", garaKC12="gt12"), "yes"),
    # dang kin, 1 tang noi, bac I/II/III cap S0
    ("garakin kin bacI S0 duoi nguong", _payload("garakin", floors=1, garaBcl="I", garaCapS="S0", totalArea=1999), "no"),
    ("garakin kin bacI S0 dung nguong", _payload("garakin", floors=1, garaBcl="I", garaCapS="S0", totalArea=2000), "yes"),
    # bac IV/V cap S0
    ("garakin kin bacIV S0 duoi nguong", _payload("garakin", floors=1, garaBcl="IV", garaCapS="S0", totalArea=999), "no"),
    ("garakin kin bacIV S0 dung nguong", _payload("garakin", floors=1, garaBcl="IV", garaCapS="S0", totalArea=1000), "yes"),
    # thieu du lieu bac/cap -> warn
    ("garakin kin thieu du lieu la warn", _payload("garakin", floors=1), "warn"),

    # sanxuat/kho uy quyen cho evalA3 (for_sprinkler=False)
    ("sanxuat hangA khong dt luon yes", _payload("sanxuat", hazard="A", areaFloor=0), "yes"),
    ("kho hangD na", _payload("kho", hazard="D", areaFloor=999999), "na"),
]


@pytest.mark.parametrize("description,payload,expected", BAO_CHAY_CASES, ids=[c[0] for c in BAO_CHAY_CASES])
def test_bao_chay_golden(description, payload, expected):
    result = evaluate_bao_chay(payload)
    assert result["result"] == expected, f"{description}: ky vong '{expected}', duoc '{result['result']}' ({result['detail']})"


# ---------------------------------------------------------------------------
# evaluate_sprinkler — QCVN 10:2025/BCA Bảng A.1 (chữa cháy tự động)
# ---------------------------------------------------------------------------
SPRINKLER_CASES = [
    ("chungcu duoi nguong H", _payload("chungcu", hFire=29), "no"),
    ("chungcu dung nguong H", _payload("chungcu", hFire=30), "yes"),

    ("nhatre thieu 1 dieu kien la no", _payload("nhatre", floors=4, totalArea=4999), "no"),
    ("nhatre du 2 dieu kien dong thoi", _payload("nhatre", floors=4, totalArea=5000), "yes"),

    ("truonghoc duoi nguong H", _payload("truonghoc", hFire=24), "no"),
    ("truonghoc dung nguong H", _payload("truonghoc", hFire=25), "yes"),

    ("yte duoi ca 2 nguong", _payload("yte", hFire=24, totalArea=1999), "no"),
    ("yte dung nguong dt", _payload("yte", hFire=0, totalArea=2000), "yes"),

    ("thethao duoi nguong H", _payload("thethao", hFire=24), "no"),
    ("thethao dung nguong H", _payload("thethao", hFire=25), "yes"),

    ("nhahat duoi nguong H", _payload("nhahat", hFire=24), "no"),
    ("nhahat dung nguong H", _payload("nhahat", hFire=25), "yes"),

    ("baotang ham duoi nguong", _payload("baotang", basements=1, totalArea=199), "no"),
    ("baotang ham dung nguong", _payload("baotang", basements=1, totalArea=200), "yes"),
    ("baotang >=3 tang duoi nguong", _payload("baotang", floors=3, totalArea=499), "no"),
    ("baotang >=3 tang dung nguong", _payload("baotang", floors=3, totalArea=500), "yes"),
    ("baotang 1-2 tang duoi nguong", _payload("baotang", floors=1, totalArea=3999), "no"),
    ("baotang 1-2 tang dung nguong", _payload("baotang", floors=1, totalArea=4000), "yes"),

    ("vanhoa duoi ca 2 nguong", _payload("vanhoa", hFire=24, totalArea=4999), "no"),
    ("vanhoa dung nguong dt", _payload("vanhoa", hFire=0, totalArea=5000), "yes"),

    ("karaoke co ham luon yes", _payload("karaoke", basements=1), "yes"),
    ("karaoke >=3 tang luon yes", _payload("karaoke", floors=3), "yes"),
    ("karaoke 1-2 tang duoi nguong", _payload("karaoke", floors=1, totalArea=499), "no"),
    ("karaoke 1-2 tang dung nguong", _payload("karaoke", floors=1, totalArea=500), "yes"),

    ("tttm co ham duoi nguong", _payload("tttm", basements=1, totalArea=199), "no"),
    ("tttm co ham dung nguong", _payload("tttm", basements=1, totalArea=200), "yes"),
    ("tttm >=3 tang luon yes", _payload("tttm", floors=3), "yes"),
    ("tttm 1-2 tang duoi nguong", _payload("tttm", floors=1, totalArea=3499), "no"),
    ("tttm 1-2 tang dung nguong", _payload("tttm", floors=1, totalArea=3500), "yes"),

    ("nhahang duoi ca 2 nguong", _payload("nhahang", hFire=24, totalArea=4999), "no"),
    ("nhahang dung nguong dt", _payload("nhahang", hFire=0, totalArea=5000), "yes"),

    ("cuahang co ham duoi nguong", _payload("cuahang", basements=1, totalArea=199), "no"),
    ("cuahang co ham dung nguong", _payload("cuahang", basements=1, totalArea=200), "yes"),
    ("cuahang khong ham duoi ca 2 nguong", _payload("cuahang", hFire=24, totalArea=3499), "no"),
    ("cuahang khong ham dung nguong dt", _payload("cuahang", hFire=0, totalArea=3500), "yes"),

    ("khachsan duoi ca 2 nguong", _payload("khachsan", hFire=24, totalArea=4999), "no"),
    ("khachsan dung nguong dt", _payload("khachsan", hFire=0, totalArea=5000), "yes"),

    ("buudien duoi ca 2 nguong", _payload("buudien", hFire=24, totalArea=4999), "no"),
    ("buudien dung nguong dt", _payload("buudien", hFire=0, totalArea=5000), "yes"),

    ("truso duoi ca 2 nguong", _payload("truso", hFire=24, totalArea=4999), "no"),
    ("truso dung nguong dt", _payload("truso", hFire=0, totalArea=5000), "yes"),

    ("honhop duoi ca 2 nguong", _payload("honhop", hFire=24, totalArea=4999), "no"),
    ("honhop dung nguong dt", _payload("honhop", hFire=0, totalArea=5000), "yes"),

    ("nhaga duoi ca 2 nguong", _payload("nhaga", hFire=24, totalArea=9999), "no"),
    ("nhaga dung nguong dt", _payload("nhaga", hFire=0, totalArea=10000), "yes"),

    ("garakin co ham luon yes", _payload("garakin", basements=1), "yes"),
    ("garakin ho le12 luon warn dang canh bao kiem tra lai", _payload("garakin", garaKin="ho", garaKC12="le12"), "yes"),
    ("garakin ho gt12 duoi nguong", _payload("garakin", garaKin="ho", garaKC12="gt12", totalArea=3999, floors=0), "no"),
    ("garakin ho gt12 dung nguong", _payload("garakin", garaKin="ho", garaKC12="gt12", totalArea=4000, floors=0), "yes"),
    ("garakin kin bacI S0S1 duoi nguong", _payload("garakin", floors=1, garaBcl="I", garaCapS="S0", totalArea=1999), "no"),
    ("garakin kin bacI S0S1 dung nguong", _payload("garakin", floors=1, garaBcl="I", garaCapS="S0", totalArea=2000), "yes"),
    ("garakin kin bacIV duoi nguong", _payload("garakin", floors=1, garaBcl="IV", garaCapS="S2", totalArea=1999), "no"),
    ("garakin kin bacIV dung nguong", _payload("garakin", floors=1, garaBcl="IV", garaCapS="S2", totalArea=2000), "yes"),
]


@pytest.mark.parametrize("description,payload,expected", SPRINKLER_CASES, ids=[c[0] for c in SPRINKLER_CASES])
def test_sprinkler_golden(description, payload, expected):
    result = evaluate_sprinkler(payload)
    assert result["result"] == expected, f"{description}: ky vong '{expected}', duoc '{result['result']}' ({result['detail']})"


# ---------------------------------------------------------------------------
# evaluate_hong_nuoc — QCVN 10:2025/BCA Phụ lục B (họng nước trong nhà)
# ---------------------------------------------------------------------------
HONG_NUOC_CASES = [
    ("chungcu duoi nguong", _payload("chungcu", floors=6), "no"),
    ("chungcu dung nguong", _payload("chungcu", floors=7), "yes"),

    ("honhop duoi nguong", _payload("honhop", floors=4, totalArea=1499), "no"),
    ("honhop dung nguong tang", _payload("honhop", floors=5, totalArea=0), "yes"),
    ("khachsan dung nguong dt", _payload("khachsan", floors=0, totalArea=1500), "yes"),

    ("nhatre duoi ca 3 nguong", _payload("nhatre", kids=99, floors=2, totalArea=999), "no"),
    ("nhatre dung nguong tre", _payload("nhatre", kids=100, floors=0, totalArea=0), "yes"),

    ("truonghoc duoi nguong", _payload("truonghoc", floors=2, totalArea=599), "no"),
    ("truonghoc dung nguong tang", _payload("truonghoc", floors=3, totalArea=0), "yes"),
    ("yte dung nguong dt", _payload("yte", floors=0, totalArea=600), "yes"),

    ("thethao duoi nguong", _payload("thethao", floors=5, totalArea=1499), "no"),
    ("thethao dung nguong tang", _payload("thethao", floors=6, totalArea=0), "yes"),

    ("nhahat duoi ca 2 nguong", _payload("nhahat", seats=299, totalArea=999), "no"),
    ("nhahat dung nguong cho", _payload("nhahat", seats=300, totalArea=0), "yes"),

    ("vanhoa duoi nguong", _payload("vanhoa", totalArea=1499), "no"),
    ("baotang dung nguong", _payload("baotang", totalArea=1500), "yes"),

    ("truso duoi nguong", _payload("truso", floors=5, totalArea=1499), "no"),
    ("buudien dung nguong tang", _payload("buudien", floors=6, totalArea=0), "yes"),

    ("karaoke co ham luon yes", _payload("karaoke", basements=1), "yes"),
    ("karaoke >=3tang luon yes", _payload("karaoke", floors=3), "yes"),
    ("karaoke 1-2tang duoi nguong", _payload("karaoke", floors=1, totalArea=299), "no"),
    ("karaoke 1-2tang dung nguong", _payload("karaoke", floors=1, totalArea=300), "yes"),

    ("tttm luon yes", _payload("tttm"), "yes"),

    ("nhahang duoi nguong", _payload("nhahang", floors=5, totalArea=1499), "no"),
    ("nhahang dung nguong tang", _payload("nhahang", floors=6, totalArea=0), "yes"),

    ("nhaga duoi nguong", _payload("nhaga", totalArea=1499), "no"),
    ("nhaga dung nguong", _payload("nhaga", totalArea=1500), "yes"),

    ("sanxuat hangA duoi nguong", _payload("sanxuat", hazard="A", totalArea=499), "no"),
    ("sanxuat hangA dung nguong", _payload("sanxuat", hazard="A", totalArea=500), "yes"),
    ("kho hangE luon no", _payload("kho", hazard="E", totalArea=999999), "no"),

    ("garakin kin ham luon yes", _payload("garakin", garaKin="kin", basements=1), "yes"),
    ("garakin kin duoi nguong", _payload("garakin", garaKin="kin", totalArea=149), "no"),
    ("garakin kin dung nguong", _payload("garakin", garaKin="kin", totalArea=150), "yes"),
    ("garakin ho duoi nguong", _payload("garakin", garaKin="ho", totalArea=999), "no"),
    ("garakin ho dung nguong", _payload("garakin", garaKin="ho", totalArea=1000), "yes"),
]


@pytest.mark.parametrize("description,payload,expected", HONG_NUOC_CASES, ids=[c[0] for c in HONG_NUOC_CASES])
def test_hong_nuoc_golden(description, payload, expected):
    result = evaluate_hong_nuoc(payload)
    assert result["result"] == expected, f"{description}: ky vong '{expected}', duoc '{result['result']}' ({result['detail']})"


# ---------------------------------------------------------------------------
# evaluate_ngoai_nha — QCVN 10:2025/BCA Phụ lục C (cấp nước ngoài nhà)
# ---------------------------------------------------------------------------
NGOAI_NHA_CASES = [
    ("yte duoi nguong", _payload("yte", floors=4, totalArea=2999), "no"),
    ("yte dung nguong tang", _payload("yte", floors=5, totalArea=0), "yes"),
    ("yte dung nguong dt", _payload("yte", floors=0, totalArea=3000), "yes"),
    ("tttm luon yes", _payload("tttm"), "yes"),
    ("nhaga luon yes", _payload("nhaga"), "yes"),
    ("occ khac la na", _payload("chungcu"), "na"),
]


@pytest.mark.parametrize("description,payload,expected", NGOAI_NHA_CASES, ids=[c[0] for c in NGOAI_NHA_CASES])
def test_ngoai_nha_golden(description, payload, expected):
    result = evaluate_ngoai_nha(payload)
    assert result["result"] == expected, f"{description}: ky vong '{expected}', duoc '{result['result']}' ({result['detail']})"
