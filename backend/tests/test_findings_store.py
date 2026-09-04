from app.services.findings_store import Finding, build_findings


def test_build_findings_chuyen_doi_dung_field():
    items = [
        {"id": 2, "noi_dung_thiet_ke": "Đầu báo khói bố trí đủ theo TCVN 5738", "ket_luan": "dat"},
        {"id": 5, "noi_dung_thiet_ke": "Chưa thể hiện trên bản vẽ cung cấp", "ket_luan": "chua_the_hien"},
    ]
    result = build_findings(items, he_thong="Báo cháy tự động", muc_form="thuong", ky_hieu_ban_ve="FA-01", session_id=42)
    assert len(result) == 2
    assert isinstance(result[0], Finding)
    assert result[0].id == 2
    assert result[0].he_thong == "Báo cháy tự động"
    assert result[0].muc_form == "thuong"
    assert result[0].trang_thai == "dat"
    assert result[0].hien_trang == "Đầu báo khói bố trí đủ theo TCVN 5738"
    assert result[0].ky_hieu_ban_ve == "FA-01"
    assert result[0].session_id == 42
    assert result[1].trang_thai == "chua_the_hien"


def test_build_findings_bo_qua_id_khong_hop_le():
    items = [{"id": "khong-phai-so", "noi_dung_thiet_ke": "x", "ket_luan": "dat"}]
    result = build_findings(items, he_thong="X", muc_form="x")
    assert result == []


def test_build_findings_mac_dinh_khi_thieu_tham_so_tuy_chon():
    items = [{"id": 1, "noi_dung_thiet_ke": "abc", "ket_luan": "dat"}]
    result = build_findings(items, he_thong="X", muc_form="x")
    assert result[0].ky_hieu_ban_ve == ""
    assert result[0].session_id is None
