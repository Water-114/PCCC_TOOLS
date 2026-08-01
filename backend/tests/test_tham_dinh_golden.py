"""Batch 3 — golden/boundary test cho evaluate_tham_dinh() (BƯỚC 1 — Diện
thẩm định, Phụ lục III NĐ 105/2025), so khớp với hàm evalThamDinh() gốc trong
js/tuvan-so-bo.js (production UI vẫn dùng bản JS này — xem ghi chú trong
test_tham_dinh.py).

Mục đích: khoá lại đúng ngưỡng dưới/bằng/trên cho từng công năng đã port
sang backend, để bất kỳ thay đổi vô tình nào ở service này cũng bị test bắt
được ngay, KHÔNG phải để tự ý xác nhận ngưỡng đúng hay sai theo quy định —
việc đó vẫn cần kỹ sư PCCC đối chiếu nguồn trước khi coi backend là nguồn sự
thật duy nhất (xem docs/02-implementation-batches.md mục Batch 3).
"""

import pytest

from app.services.tham_dinh import evaluate_tham_dinh


def _payload(occ, **kwargs):
    base = {"occ": occ, "floors": 0, "totalArea": 0, "volume": 0}
    base.update(kwargs)
    return base


# (mo_ta, payload, ket_qua_mong_doi)
CASES = [
    # chungcu: T>=7 || F>=3000 (mục 1)
    ("chungcu duoi ca 2 nguong", _payload("chungcu", floors=6, totalArea=2999), "no"),
    ("chungcu dung nguong tang", _payload("chungcu", floors=7, totalArea=0), "yes"),
    ("chungcu dung nguong dien tich", _payload("chungcu", floors=0, totalArea=3000), "yes"),
    ("chungcu tren ca 2 nguong", _payload("chungcu", floors=8, totalArea=3500), "yes"),

    # nhatre: kids>=150 || F>=2000 (muc 2)
    ("nhatre duoi nguong", _payload("nhatre", kids=149, totalArea=1999), "no"),
    ("nhatre dung nguong so tre", _payload("nhatre", kids=150, totalArea=0), "yes"),
    ("nhatre dung nguong dien tich", _payload("nhatre", kids=0, totalArea=2000), "yes"),

    # truonghoc: T>=5 || F>=3000 (muc 2)
    ("truonghoc duoi nguong", _payload("truonghoc", floors=4, totalArea=2999), "no"),
    ("truonghoc dung nguong tang", _payload("truonghoc", floors=5, totalArea=0), "yes"),
    ("truonghoc dung nguong dien tich", _payload("truonghoc", floors=0, totalArea=3000), "yes"),

    # yte: T>=5 || F>=2000 (muc 3)
    ("yte duoi nguong", _payload("yte", floors=4, totalArea=1999), "no"),
    ("yte dung nguong tang", _payload("yte", floors=5, totalArea=0), "yes"),
    ("yte dung nguong dien tich", _payload("yte", floors=0, totalArea=2000), "yes"),

    # thethao: seats>=5000 || F>=5000 (muc 4)
    ("thethao duoi nguong", _payload("thethao", seats=4999, totalArea=4999), "no"),
    ("thethao dung nguong cho ngoi", _payload("thethao", seats=5000, totalArea=0), "yes"),
    ("thethao dung nguong dien tich", _payload("thethao", seats=0, totalArea=5000), "yes"),

    # nhahat: seats>=300 (muc 5)
    ("nhahat duoi nguong", _payload("nhahat", seats=299), "no"),
    ("nhahat dung nguong", _payload("nhahat", seats=300), "yes"),

    # vanhoa/baotang: T>=5 || F>=3000 (muc 5)
    ("vanhoa duoi nguong", _payload("vanhoa", floors=4, totalArea=2999), "no"),
    ("vanhoa dung nguong tang", _payload("vanhoa", floors=5, totalArea=0), "yes"),
    ("baotang dung nguong dien tich", _payload("baotang", floors=0, totalArea=3000), "yes"),

    # karaoke: T>=4 || F>=1000 (muc 5)
    ("karaoke duoi nguong", _payload("karaoke", floors=3, totalArea=999), "no"),
    ("karaoke dung nguong tang", _payload("karaoke", floors=4, totalArea=0), "yes"),
    ("karaoke dung nguong dien tich", _payload("karaoke", floors=0, totalArea=1000), "yes"),

    # tttm/cuahang: F>=2000 (muc 6)
    ("tttm duoi nguong", _payload("tttm", totalArea=1999), "no"),
    ("tttm dung nguong", _payload("tttm", totalArea=2000), "yes"),
    ("cuahang dung nguong", _payload("cuahang", totalArea=2000), "yes"),

    # nhahang: F>=3000 (muc 6)
    ("nhahang duoi nguong", _payload("nhahang", totalArea=2999), "no"),
    ("nhahang dung nguong", _payload("nhahang", totalArea=3000), "yes"),

    # khachsan/buudien/truso: T>=7 || F>=3000 (muc 7)
    ("khachsan duoi nguong", _payload("khachsan", floors=6, totalArea=2999), "no"),
    ("khachsan dung nguong tang", _payload("khachsan", floors=7, totalArea=0), "yes"),
    ("buudien dung nguong dien tich", _payload("buudien", floors=0, totalArea=3000), "yes"),
    ("truso dung nguong tang", _payload("truso", floors=7, totalArea=0), "yes"),

    # honhop: T>=7 || F>=3000 -> yes, else warn (muc 8) - KHONG bao gio "no"
    ("honhop duoi nguong la warn khong phai no", _payload("honhop", floors=6, totalArea=2999), "warn"),
    ("honhop dung nguong tang", _payload("honhop", floors=7, totalArea=0), "yes"),

    # congnghiep_dacthu: luon yes, khong phu thuoc quy mo (muc 9a/9b/9c)
    ("congnghiep_dacthu luon yes", _payload("congnghiep_dacthu"), "yes"),

    # sanxuat hang A/B: V>=7000 || F>=1000 (muc 9d)
    ("sanxuat A duoi nguong", _payload("sanxuat", hazard="A", volume=6999, totalArea=999), "no"),
    ("sanxuat A dung nguong V", _payload("sanxuat", hazard="A", volume=7000, totalArea=0), "yes"),
    ("sanxuat B dung nguong F", _payload("sanxuat", hazard="B", volume=0, totalArea=1000), "yes"),
    # sanxuat hang C: V>=15000 || F>=2000
    ("sanxuat C duoi nguong", _payload("sanxuat", hazard="C", volume=14999, totalArea=1999), "no"),
    ("sanxuat C dung nguong V", _payload("sanxuat", hazard="C", volume=15000, totalArea=0), "yes"),
    # sanxuat hang D/E: V>=30000 || F>=10000
    ("sanxuat D duoi nguong", _payload("sanxuat", hazard="D", volume=29999, totalArea=9999), "no"),
    ("sanxuat E dung nguong F", _payload("sanxuat", hazard="E", volume=0, totalArea=10000), "yes"),

    # kho hang A/B/C: V>=15000 || F>=2000 (muc 10)
    ("kho A duoi nguong", _payload("kho", hazard="A", volume=14999, totalArea=1999), "no"),
    ("kho B dung nguong V", _payload("kho", hazard="B", volume=15000, totalArea=0), "yes"),
    ("kho C dung nguong F", _payload("kho", hazard="C", volume=0, totalArea=2000), "yes"),
    # kho hang D/E: muc 10 khong ap dung -> luon "no"
    ("kho D luon no du quy mo lon", _payload("kho", hazard="D", volume=999999, totalArea=999999), "no"),

    # garakin: F>=2000 (muc 12)
    ("garakin duoi nguong", _payload("garakin", totalArea=1999), "no"),
    ("garakin dung nguong", _payload("garakin", totalArea=2000), "yes"),

    # nhaga: F>=3000 (muc 13)
    ("nhaga duoi nguong", _payload("nhaga", totalArea=2999), "no"),
    ("nhaga dung nguong", _payload("nhaga", totalArea=3000), "yes"),

    # sanvandong: seats>=5000 (muc 4)
    ("sanvandong duoi nguong", _payload("sanvandong", seats=4999), "no"),
    ("sanvandong dung nguong", _payload("sanvandong", seats=5000), "yes"),

    # hatangkt: luon yes (muc 11)
    ("hatangkt luon yes", _payload("hatangkt"), "yes"),

    # hamgiaothong: tunnelLength>=1000 (muc 14)
    ("hamgiaothong duoi nguong", _payload("hamgiaothong", tunnelLength=999), "no"),
    ("hamgiaothong dung nguong", _payload("hamgiaothong", tunnelLength=1000), "yes"),

    # csohatnhan: luon yes (muc 15)
    ("csohatnhan luon yes", _payload("csohatnhan"), "yes"),

    # phuongtiengt: ppl>=50 || gt>=500 || hp>=300 (muc 16)
    ("phuongtiengt duoi ca 3 nguong", _payload("phuongtiengt", pplTransport=49, vesselGT=499, enginePower=299), "no"),
    ("phuongtiengt dung nguong nguoi", _payload("phuongtiengt", pplTransport=50, vesselGT=0, enginePower=0), "yes"),
    ("phuongtiengt dung nguong GT", _payload("phuongtiengt", pplTransport=0, vesselGT=500, enginePower=0), "yes"),
    ("phuongtiengt dung nguong suc ngua", _payload("phuongtiengt", pplTransport=0, vesselGT=0, enginePower=300), "yes"),
]


@pytest.mark.parametrize("description,payload,expected", CASES, ids=[c[0] for c in CASES])
def test_tham_dinh_golden_boundary(description, payload, expected):
    result = evaluate_tham_dinh(payload)
    assert result["result"] == expected, f"{description}: ky vong '{expected}', duoc '{result['result']}' ({result['detail']})"
