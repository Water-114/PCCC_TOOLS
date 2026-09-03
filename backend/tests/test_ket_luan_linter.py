from app.services import ket_luan_linter


def test_fix_items_sua_khong_su_dung_thanh_khong_ap_dung():
    item = {
        "id": 1,
        "noi_dung_thiet_ke": "Hệ thống không sử dụng đầu báo kiểu hút",
        "ket_luan": "chua_dat",
    }
    result = ket_luan_linter.fix_items([item])
    assert result[0]["ket_luan"] == "khong_ap_dung"


def test_fix_items_khong_dong_toi_muc_binh_thuong():
    item = {
        "id": 2,
        "noi_dung_thiet_ke": "Đầu báo khói bố trí đủ theo TCVN 5738",
        "ket_luan": "dat",
    }
    result = ket_luan_linter.fix_items([item])
    assert result[0]["ket_luan"] == "dat"
