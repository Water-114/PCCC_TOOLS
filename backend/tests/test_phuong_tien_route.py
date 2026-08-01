"""Test validation cho /api/phuong-tien/evaluate (Batch 3, cụm 4) — đúng
chuẩn Batch 1 và các cụm trước, cộng thêm 2 trường MỚI: extLevel (enum) và
pplFloor (optional, số nguyên không âm)."""


def test_evaluate_returns_200_with_all_six_results(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "truso", "areaFloor": 250})
    assert resp.status_code == 200
    data = resp.get_json()
    for key in ("pha_do", "mat_na", "co_gioi", "loa", "binh", "den"):
        assert key in data
        assert data[key]["rule_set_version"]
    assert data["binh"]["result"] == "yes"
    assert data["den"]["result"] == "yes"


def test_json_root_list_rejected_with_400_not_500(client):
    resp = client.post("/api/phuong-tien/evaluate", json=[{"occ": "truso"}])
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_json_root_string_rejected_with_400_not_500(client):
    resp = client.post("/api/phuong-tien/evaluate", json="truso")
    assert resp.status_code == 400


def test_json_root_bool_rejected_with_400_not_500(client):
    resp = client.post("/api/phuong-tien/evaluate", json=True)
    assert resp.status_code == 400


def test_non_numeric_string_field_rejected_with_400_not_500(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "truso", "floors": "abc"})
    assert resp.status_code == 400


def test_nan_string_field_rejected_with_400(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "truso", "areaFloor": "NaN"})
    assert resp.status_code == 400


def test_infinity_string_field_rejected_with_400(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "truso", "volume": "Infinity"})
    assert resp.status_code == 400


def test_negative_field_rejected_with_400(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "truso", "totalArea": -1})
    assert resp.status_code == 400


def test_non_scalar_field_rejected_with_400_not_500(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "truso", "areaFloor": {"a": 1}})
    assert resp.status_code == 400


def test_unknown_occupation_rejected_with_400(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "khong_ton_tai"})
    assert resp.status_code == 400


def test_optional_fields_not_required_returns_200(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "truso"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 2 truong MOI: extLevel (enum) va pplFloor (so nguyen khong am, tuy chon)
# ---------------------------------------------------------------------------
def test_invalid_ext_level_enum_rejected_with_400(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "truso", "extLevel": "khong_hop_le"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_valid_ext_level_values_return_200(client):
    for lv in ("auto", "thap", "tb", "cao"):
        resp = client.post("/api/phuong-tien/evaluate", json={"occ": "truso", "extLevel": lv})
        assert resp.status_code == 200, lv


def test_ppl_floor_absent_returns_200(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "karaoke"})
    assert resp.status_code == 200


def test_ppl_floor_negative_rejected_with_400(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "karaoke", "pplFloor": -1})
    assert resp.status_code == 400


def test_ppl_floor_non_integer_rejected_with_400(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "karaoke", "pplFloor": 12.5})
    assert resp.status_code == 400


def test_ppl_floor_non_numeric_string_rejected_with_400(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "karaoke", "pplFloor": "abc"})
    assert resp.status_code == 400


def test_ppl_floor_valid_integer_returns_200_and_affects_loa(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "karaoke", "pplFloor": 50})
    assert resp.status_code == 200
    assert resp.get_json()["loa"]["result"] == "yes"


def test_gara_kin_invalid_enum_rejected_with_400(client):
    resp = client.post("/api/phuong-tien/evaluate", json={"occ": "garakin", "garaKin": "khong_hop_le"})
    assert resp.status_code == 400
