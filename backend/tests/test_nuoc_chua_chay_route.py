"""Test validation cho /api/nuoc-chua-chay/evaluate (Batch 3, cụm 3) — đúng
chuẩn Batch 1 và 2 lỗi validation hole đã sửa ở cụm 2 (JSON root không phải
object, trường số ở nhánh không dùng vẫn phải được validate)."""


def test_evaluate_returns_200_with_version(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={
        "occ": "chungcu", "floors": 10, "totalArea": 5000, "hFire": 32,
        "volume": 20000, "nhomNC": "1", "corridor": "le10",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["rule_set_version"] == "QCVN06-TCVN7336-2021-TCVN14496-2025"
    assert data["kq"]["Vtong"] == 22500


def test_json_root_list_rejected_with_400_not_500(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json=[{"occ": "chungcu"}])
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_json_root_string_rejected_with_400_not_500(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json="chungcu")
    assert resp.status_code == 400


def test_json_root_bool_rejected_with_400_not_500(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json=True)
    assert resp.status_code == 400


def test_non_numeric_string_field_rejected_with_400_not_500(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={
        "occ": "chungcu", "floors": "abc",
    })
    assert resp.status_code == 400


def test_nan_string_field_rejected_with_400(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={
        "occ": "chungcu", "botS": "NaN",
    })
    assert resp.status_code == 400


def test_infinity_string_field_rejected_with_400(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={
        "occ": "chungcu", "hGianPhong": "Infinity",
    })
    assert resp.status_code == 400


def test_negative_field_not_used_by_current_branch_still_rejected(client):
    """Trường botS chỉ được đọc khi nhomNC ở nhóm bọt (4.2/7), nhưng payload
    dưới đây KHÔNG chọn nhóm bọt — vẫn phải bị chặn 400 vì validate_payload()
    quét toàn bộ trường số đã biết, không phụ thuộc nhánh nghiệp vụ nào dùng."""
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={
        "occ": "chungcu", "botS": -1,
    })
    assert resp.status_code == 400


def test_non_scalar_field_rejected_with_400_not_500(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={
        "occ": "chungcu", "hXepM": {"a": 1},
    })
    assert resp.status_code == 400


def test_unknown_occupation_rejected_with_400(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={
        "occ": "khong_ton_tai", "floors": 5,
    })
    assert resp.status_code == 400


def test_invalid_nhom_nc_enum_rejected_with_400(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={
        "occ": "chungcu", "nhomNC": "99",
    })
    assert resp.status_code == 400


def test_invalid_hxep_enum_rejected_with_400(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={
        "occ": "kho", "hXep": "khong_hop_le",
    })
    assert resp.status_code == 400


def test_invalid_bcl_enum_rejected_with_400(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={
        "occ": "kho", "bcl": "VI",
    })
    assert resp.status_code == 400


def test_invalid_cap_s_enum_rejected_with_400(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={
        "occ": "kho", "capS": "S9",
    })
    assert resp.status_code == 400


def test_invalid_phuong_an_14496_enum_rejected_with_400(client):
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={
        "occ": "kho", "phuongAn14496": "khong_hop_le",
    })
    assert resp.status_code == 400


def test_optional_fields_not_required_returns_200(client):
    """Không bắt buộc nhập các trường không áp dụng cho công năng đang chọn."""
    resp = client.post("/api/nuoc-chua-chay/evaluate", json={"occ": "truso", "floors": 1})
    assert resp.status_code == 200
