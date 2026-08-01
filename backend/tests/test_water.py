"""Test cho /api/water/calculate (backend/app/services/water_calculator.py).

Lưu ý: route này hiện chỉ được frontend/ (MVP React đã đóng băng) gọi tới —
index.html production tính nước 100% ở client (js/cong-cu-tinh-toan.js).

Batch 1 đã sửa 3 lỗi validation từng được Batch 0 ghi nhận baseline (NaN lọt
ra response, số âm lọt qua, TypeError gây 500) — các test dưới đây đã cập
nhật để xác nhận hành vi ĐÚNG mới (400 sạch, không rò rỉ NaN/số âm/exception).
"""


def test_happy_path_computes_v_equals_q_times_t_times_60(client):
    resp = client.post("/api/water/calculate", json={
        "htn_n": 2, "htn_q": 2.5, "htn_t": 60,
        "sp_q": 0, "sp_t": 0,
        "nn_q": 0, "nn_t": 0,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    # q_tn = 2*2.5 = 5 (l/s) ; v_tn = 5*60*60 = 18000 lit
    assert data["hong_nuoc_trong_nha"]["the_tich_lit"] == 18000.0
    assert data["tong"]["the_tich_lit"] == 18000.0


def test_missing_all_inputs_rejected_with_400(client):
    resp = client.post("/api/water/calculate", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_nan_string_input_now_rejected_with_400(client):
    """Batch 1: 'htn_n': 'NaN' giờ bị chặn ngay ở validation, không còn lọt
    NaN vào response nữa (trước đây trả 200 với NaN — xem lịch sử Batch 0)."""
    resp = client.post("/api/water/calculate", json={
        "htn_n": "NaN", "htn_q": 10, "htn_t": 2,
        "nn_q": 100, "nn_t": 1,
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_negative_value_now_rejected_with_400(client):
    """Batch 1: giá trị âm ở bất kỳ trường nào giờ bị chặn ngay, kể cả khi
    tổng vẫn dương (trước đây lọt qua — xem lịch sử Batch 0)."""
    resp = client.post("/api/water/calculate", json={
        "htn_n": -5, "htn_q": 10, "htn_t": 2,
        "nn_q": 200, "nn_t": 1,
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_non_scalar_payload_now_rejected_with_400_not_500(client):
    """Batch 1: gửi dict/list cho 1 trường số giờ trả 400 sạch, không còn
    crash 500 do TypeError không được bắt (trước đây 500 — xem lịch sử Batch 0)."""
    resp = client.post("/api/water/calculate", json={"htn_n": {"a": 1}})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_infinity_string_input_rejected_with_400(client):
    resp = client.post("/api/water/calculate", json={
        "htn_n": "Infinity", "htn_q": 10, "htn_t": 2,
    })
    assert resp.status_code == 400
