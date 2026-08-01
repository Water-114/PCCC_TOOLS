"""Test cho /api/tham-dinh/evaluate (backend/app/services/tham_dinh.py).

Lưu ý: route này hiện chỉ được frontend/ (MVP React đã đóng băng) gọi tới —
index.html production tự đánh giá 100% ở client (js/tuvan-so-bo.js, hàm
evalThamDinh — đã có validate input tốt hơn route backend này).

Batch 1 đã sửa lỗi 500 do input không hợp lệ (ValueError không được bắt)
từng được Batch 0 ghi nhận baseline — test dưới đây đã cập nhật để xác
nhận hành vi ĐÚNG mới (400 sạch thay vì crash 500).
"""


def test_happy_path_chungcu_dat_nguong(client):
    resp = client.post("/api/tham-dinh/evaluate", json={
        "occ": "chungcu", "floors": 8, "totalArea": 500, "volume": 1000,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["result"] == "yes"


def test_response_includes_rule_set_version(client):
    """Batch 3: mỗi kết quả rule phải kèm rule_set_version để truy vết được
    đang đối chiếu theo phiên bản nguồn pháp lý nào."""
    resp = client.post("/api/tham-dinh/evaluate", json={
        "occ": "chungcu", "floors": 8, "totalArea": 500,
    })
    assert resp.get_json()["rule_set_version"] == "ND105-2025-PLIII"


def test_unknown_occupation_rejected_with_400(client):
    resp = client.post("/api/tham-dinh/evaluate", json={"occ": "khong_ton_tai"})
    assert resp.status_code == 400


def test_missing_required_extra_field_rejected_with_400(client):
    # occ="sanxuat" bắt buộc phải có "hazard" theo OCCUPATIONS trong tham_dinh.py
    resp = client.post("/api/tham-dinh/evaluate", json={
        "occ": "sanxuat", "totalArea": 500, "volume": 1000,
    })
    assert resp.status_code == 400


def test_non_numeric_field_now_rejected_with_400_not_500(client):
    """Batch 1: '_num()' giờ validate rõ ràng, trả ThamDinhInputError (400)
    thay vì để ValueError lọt ra ngoài gây 500 (trước đây 500 — xem lịch sử
    Batch 0)."""
    resp = client.post("/api/tham-dinh/evaluate", json={
        "occ": "chungcu", "floors": 8, "totalArea": "abc",
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_negative_field_rejected_with_400(client):
    resp = client.post("/api/tham-dinh/evaluate", json={
        "occ": "chungcu", "floors": -3, "totalArea": 500,
    })
    assert resp.status_code == 400


def test_non_scalar_field_rejected_with_400_not_500(client):
    resp = client.post("/api/tham-dinh/evaluate", json={
        "occ": "chungcu", "floors": {"a": 1}, "totalArea": 500,
    })
    assert resp.status_code == 400
