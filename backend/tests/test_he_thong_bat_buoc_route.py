"""Test API contract cho /api/he-thong-bat-buoc/evaluate (Batch 3, cụm 2).

Route này chưa được production gọi tới (xem docs/02-implementation-batches.md
mục Batch 3) — test dưới đây chỉ xác nhận route trả đúng schema, không phải
regression cho toàn bộ ngưỡng (đã có ở test_he_thong_bat_buoc_golden.py)."""


def test_evaluate_returns_all_four_results_with_version(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "chungcu", "floors": 8, "totalArea": 3500, "hFire": 35,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    for key in ("bao_chay", "sprinkler", "hong_nuoc", "ngoai_nha"):
        assert key in data
        assert data[key]["rule_set_version"] == "QCVN10-2025-BCA"
    assert data["bao_chay"]["result"] == "yes"
    assert data["sprinkler"]["result"] == "yes"


def test_non_numeric_string_field_rejected_with_400_not_500(client):
    """Bug report: {"occ":"chungcu","floors":"abc"} từng trả 500 (ValueError
    không được bắt trong _num()) — nay phải trả 400 sạch, đúng chuẩn Batch 1."""
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "chungcu", "floors": "abc",
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_nan_string_field_rejected_with_400(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "chungcu", "totalArea": "NaN",
    })
    assert resp.status_code == 400


def test_infinity_string_field_rejected_with_400(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "chungcu", "hFire": "Infinity",
    })
    assert resp.status_code == 400


def test_negative_field_rejected_with_400(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "chungcu", "floors": -3,
    })
    assert resp.status_code == 400


def test_non_scalar_field_rejected_with_400_not_500(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "chungcu", "totalArea": {"a": 1},
    })
    assert resp.status_code == 400


def test_unknown_occupation_rejected_with_400(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "khong_ton_tai", "floors": 8,
    })
    assert resp.status_code == 400


def test_valid_payload_still_returns_200_with_unchanged_result(client):
    """Xác nhận validation mới không đổi kết quả nào với dữ liệu hợp lệ —
    cùng payload đã dùng ở test_evaluate_returns_all_four_results_with_version."""
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "chungcu", "floors": 8, "totalArea": 3500, "hFire": 35,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["bao_chay"]["result"] == "yes"
    assert data["sprinkler"]["result"] == "yes"


def test_all_eight_numeric_fields_reject_negative(client):
    """validate_payload() kiem tra TOAN BO 8 truong so bat ke nhanh occ hien
    tai co doc toi hay khong - moi truong deu bi chan khi am, du gui kem occ nao."""
    cases = [
        {"occ": "chungcu", "floors": -1},
        {"occ": "chungcu", "totalArea": -1},
        {"occ": "sanxuat", "hazard": "A", "areaFloor": -1},
        {"occ": "chungcu", "hFire": -1},
        {"occ": "baotang", "basements": -1},
        {"occ": "baotang", "semiBasements": -1},
        {"occ": "nhatre", "kids": -1},
        {"occ": "thethao", "seats": -1},
    ]
    for payload in cases:
        resp = client.post("/api/he-thong-bat-buoc/evaluate", json=payload)
        assert resp.status_code == 400, f"Payload {payload} phai bi tu choi 400"


# ---------------------------------------------------------------------------
# Review lan 2 — dong validation hole: JSON root khong phai object, truong so
# am o nhanh KHONG duoc dung, va enum sai (hazard/gara*).
# ---------------------------------------------------------------------------
def test_json_root_list_rejected_with_400_not_500(client):
    """Bug report: [{"occ":"chungcu","floors":5}] tung gay 500 (payload.get()
    tren list -> AttributeError khong duoc bat rieng)."""
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json=[{"occ": "chungcu", "floors": 5}])
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_json_root_string_rejected_with_400_not_500(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json="chungcu")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_json_root_bool_rejected_with_400_not_500(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json=True)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_negative_field_not_used_by_current_branch_still_rejected(client):
    """Bug report: {"occ":"chungcu","seats":-1} tung tra 200 vi "seats"
    khong duoc nhanh occ=chungcu doc toi — nay phai bi chan du khong dung den."""
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "chungcu", "seats": -1,
    })
    assert resp.status_code == 400


def test_optional_fields_not_required_when_not_applicable(client):
    """Khong bat buoc nguoi dung phai nhap truong khong ap dung cho cong
    nang cua ho — bo trong (hoac khong gui) van hop le, tra 200."""
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={"occ": "chungcu", "floors": 8})
    assert resp.status_code == 200


def test_invalid_hazard_enum_rejected_with_400(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "sanxuat", "hazard": "Z",
    })
    assert resp.status_code == 400


def test_invalid_gara_kin_enum_rejected_with_400(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "garakin", "garaKin": "khong_hop_le",
    })
    assert resp.status_code == 400


def test_invalid_gara_kc12_enum_rejected_with_400(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "garakin", "garaKin": "ho", "garaKC12": "khong_hop_le",
    })
    assert resp.status_code == 400


def test_invalid_gara_bcl_enum_rejected_with_400(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "garakin", "garaBcl": "VI",
    })
    assert resp.status_code == 400


def test_invalid_gara_cap_s_enum_rejected_with_400(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "garakin", "garaCapS": "S9",
    })
    assert resp.status_code == 400


def test_valid_enum_values_still_return_200(client):
    resp = client.post("/api/he-thong-bat-buoc/evaluate", json={
        "occ": "garakin", "garaKin": "ho", "garaKC12": "le12",
    })
    assert resp.status_code == 200
