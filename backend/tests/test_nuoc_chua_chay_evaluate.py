"""Batch 3, cụm 3 — test end-to-end evaluate_nuoc() (đúng entry point mà
route /api/nuoc-chua-chay/evaluate gọi tới), đối chiếu Vtn/Vnn/Vtd/Vtong và
lưu lượng bơm chữa cháy sơ bộ với công thức trong evalNuoc()/render() gốc.

Các giá trị mong đợi được tính tay độc lập theo đúng công thức nguồn (không
copy từ implementation) — xem chú thích từng test."""

import pytest

from app.services.nuoc_chua_chay import evaluate_nuoc


def test_chungcu_sprinkler_va_hong_nuoc_khong_ngoai_nha():
    """Chung cư 10 tầng, ΣF=5000, H=32m (>=30 -> sprinkler bắt buộc),
    corridor mặc định <=10m, nhóm nguy cơ 1.
    - sprinkler: T=10<30 nhưng H=32>=30 -> yes -> Bảng 1 TCVN 7336 nhóm 1: Q=10, t=30 -> Vtd=10*30*60=18000
    - họng nước: chungcu T=10>=7 -> yes -> Bảng 11 mục 1, <=16 tầng, hành lang <=10m -> n=1,q=2.5 -> Qtn=2.5
      có sprinkler, nhóm 1 -> tTn=30 -> Vtn=2.5*30*60=4500
    - ngoài nhà: chungcu không thuộc Phụ lục C -> na -> Vnn=None
    - Vtong=4500+0+18000+0=22500; Q_bom_so_bo=Qtn+Qtd=2.5+10=12.5
    """
    payload = {
        "occ": "chungcu", "floors": 10, "totalArea": 5000, "hFire": 32,
        "volume": 20000, "nhomNC": "1", "corridor": "le10",
    }
    result = evaluate_nuoc(payload)
    kq = result["kq"]
    assert kq["Qtd"] == 10
    assert kq["tTd"] == 30
    assert kq["Vtd"] == 18000
    assert kq["Qtn"] == 2.5
    assert kq["tTn"] == 30
    assert kq["Vtn"] == 4500
    assert kq["Vnn"] is None
    assert kq["Vtong"] == 22500
    assert kq["Q_bom_so_bo"] == 12.5
    assert result["rule_set_version"] == "QCVN06-TCVN7336-2021-TCVN14496-2025"
    assert result["errs"] == []


def test_yte_sprinkler_hong_nuoc_va_ngoai_nha_deu_ap_dung():
    """Y te: floors=5, totalArea=3000 (>=2000 -> sprinkler yes theo Bang A.1);
    floors=5>=3 -> hong nuoc yes; floors=5>=5 -> ngoai nha yes (TT1).
    - sprinkler: nhomNC=1, khong hBaoVe -> Bang 1 TCVN 7336 nhom 1: Q=10,t=30 -> Vtd=18000
    - hong nuoc: khong phai chungcu/nhahat/truso/buudien -> nhanh "nha cong cong",
      floors=5<=10, volume=2000 (khong >25000) -> n=1,q=2.5 -> Qtn=2.5; co sprinkler,
      nhom 1 -> tTn=30 -> Vtn=4500
    - ngoai nha: floors=5<=12 -> row=[10,15,20,25,30]; Vk=volume/1000=2 -> idx=1 (Vk<=5) -> Q=15
      Vnn=15*180*60=162000
    - Vtong=4500+162000+18000+0=184500; Q_bom_so_bo=2.5+10=12.5
    """
    payload = {
        "occ": "yte", "floors": 5, "totalArea": 3000, "hFire": 10,
        "volume": 2000, "nhomNC": "1",
    }
    result = evaluate_nuoc(payload)
    kq = result["kq"]
    assert kq["Qtd"] == 10 and kq["Vtd"] == 18000
    assert kq["Qtn"] == 2.5 and kq["Vtn"] == 4500
    assert kq["Qnn"] == 15 and kq["Vnn"] == 162000
    assert kq["Vtong"] == 184500
    assert kq["Q_bom_so_bo"] == 12.5
    assert result["errs"] == []


def test_kho_hazard_c_dung_bang12_va_khong_co_sprinkler_neu_khong_du_dien_tich():
    """Kho hạng C, bậc III, cấp S0: Bảng A.3 (chữa cháy tự động) yêu cầu
    diện tích gian phòng >=300m² -> nếu areaFloor<300 thì sprinkler KHÔNG
    bắt buộc theo Bảng A.1 (sp.v=no) -> co_spr=False (không tangCuong) ->
    không tính Vtd. Nhưng kho luôn tính họng nước trong nhà (occ in kho)
    theo Bảng 12 QCVN 06 (không phải Bảng 1 TCVN 14496 vì không phải kệ cao).
    - Bảng 12: bậc III, hạng C, cấp S0, V<=150000 -> n=2,q=2.5 -> Qtn=5
    - không sprinkler -> tTn=60 -> Vtn=5*60*60=18000
    - kho không thuộc Phụ lục C -> Vnn=None
    """
    payload = {
        "occ": "kho", "floors": 1, "totalArea": 200, "areaFloor": 200,
        "volume": 5000, "hazard": "C", "bcl": "III", "capS": "S0",
    }
    result = evaluate_nuoc(payload)
    kq = result["kq"]
    assert kq["Qtd"] is None  # khong co sprinkler bat buoc, khong tick tang cuong
    assert kq["Vtd"] is None
    assert kq["Qtn"] == 5
    assert kq["tTn"] == 60
    assert kq["Vtn"] == 18000
    assert kq["Vnn"] is None
    assert kq["Q_bom_so_bo"] is None
    assert result["errs"] == []


def test_foam_group_tinh_dung_va_khong_tinh_ho_ngoai_bo_khac():
    """Nhóm 4.2 (bọt): co_spr=True do isBotGroup, không phụ thuộc sp.v.
    Kiểm tra Vtd suy ra từ Wdd (bọt), không phải công thức Q*t*60 thường."""
    payload = {
        "occ": "sanxuat", "floors": 1, "totalArea": 100, "areaFloor": 100,
        "hazard": "A", "nhomNC": "4.2",
        "botS": 50, "botJ": 0.6, "botT": 10, "botK": 1.05, "botCB": 6,
    }
    result = evaluate_nuoc(payload)
    kq = result["kq"]
    kq_bot = result["kqBot"]
    Qct = 50 * 0.6
    Wdd = 1.05 * Qct * 10 * 60
    assert kq_bot["Wdd"] == Wdd
    assert kq["Vbot"] == Wdd
    assert kq["Vtd"] is None  # foam khong dat Qtd/tTd theo cong thuc Q*t*60 thuong
    assert kq["Vtong"] == (kq["Vtn"] or 0) + (kq["Vnn"] or 0) + (kq["Vtd"] or 0) + Wdd


def test_khong_thuoc_dien_nao_tra_ve_khong_co_loi_va_vtong_bang_0():
    """Trụ sở nhỏ, không thuộc diện sprinkler/họng nước/ngoài nhà -> mọi Q
    đều None, Vtong=0, không có errs (đây là kết luận hợp lệ, không phải lỗi)."""
    payload = {"occ": "truso", "floors": 1, "totalArea": 100, "hFire": 5, "volume": 500}
    result = evaluate_nuoc(payload)
    kq = result["kq"]
    assert kq["Qtd"] is None
    assert kq["Qtn"] is None
    assert kq["Qnn"] is None
    assert kq["Vtong"] == 0
    assert kq["Q_bom_so_bo"] is None
    assert result["errs"] == []


def test_kho_ke_cao_nhieu_tang_end_to_end_dung_hxepm2():
    """Regression cho lỗi mapping đã sửa: kho kệ cao, chế độ "nhiều tầng đầu
    phun" (Điều 6), phải chạy hết đến evaluate_nuoc() và dùng đúng hXepM2.

    hXepM cố tình đặt = 3 (< 5,5 m, sẽ gây "err" nếu bị đọc nhầm); hXepM2 = 10
    (hợp lệ). Nếu mapping còn sai, kq["Qtd"] sẽ là None và result["errs"] sẽ
    không rỗng — bài test này thất bại rõ ràng trong cả 2 trường hợp đó.

    - Qi = A×B×n×i = 9×2,4×3×0,36 = 23,328
    - iD = 0,12 (h=10<=16m), Qd = iD×Sd = 0,12×90 = 10,8
    - Qs = Qi+Qd = 34,128 -> Qtd=34,128, tTd=60 -> Vtd=34,128×60×60=122.860,8
    - Bảng 1 TCVN 14496 (bậc III, hạng A, cấp S0, V=1000<=150000): n=2,q=2.5 -> Qtn=5
      kệ cao -> tTn=60 -> Vtn=5×60×60=18000
    - kho không thuộc Phụ lục C -> Vnn=None
    - Vtong=18000+0+122860.8+0=140860.8; Q_bom_so_bo=5+34.128=39.128
    """
    payload = {
        "occ": "kho", "floors": 1, "totalArea": 100, "areaFloor": 100, "volume": 1000,
        "hazard": "A", "bcl": "III", "capS": "S0",
        "nhomNC": "5", "hXep": "cao", "phuongAn14496": "nhieutang",
        "hXepM": 3,  # cua che do 1 tang - KHONG duoc dung cho nhieu tang
        "hXepM2": 10,  # cua che do nhieu tang - PHAI duoc dung
        "loaiPallet14496": "phang", "chieuRongKeB": 2.4, "soTamChan": 3,
        "loaiHang14496": "ranco", "daiCaoDo14496": "tu2den3", "dienTichMai90": 90,
    }
    result = evaluate_nuoc(payload)
    assert result["errs"] == [], f"Khong duoc co loi (chung to van doc nham hXepM): {result['errs']}"
    kq = result["kq"]
    assert kq["Qtd"] == pytest.approx(34.128)
    assert kq["tTd"] == 60
    assert kq["Vtd"] == pytest.approx(122860.8)
    assert kq["Qtn"] == 5
    assert kq["Vtn"] == 18000
    assert kq["Vnn"] is None
    assert kq["Vtong"] == pytest.approx(140860.8)
    assert kq["Q_bom_so_bo"] == pytest.approx(39.128)
