"""API contract cho cụm 4 (phương tiện & hạng mục khác, BƯỚC 5) — Batch 3.

Theo quyết định của owner: đây là endpoint "đối chiếu song song", production
(js/tuvan-so-bo.js) chưa gọi tới route này — xem
docs/02-implementation-batches.md mục Batch 3.
"""

from flask import Blueprint, jsonify, request

from ..services.phuong_tien import (
    PhuongTienInputError,
    evaluate_binh,
    evaluate_co_gioi,
    evaluate_den,
    evaluate_loa,
    evaluate_mat_na,
    evaluate_pha_do,
)

bp = Blueprint("phuong_tien", __name__, url_prefix="/api/phuong-tien")


@bp.post("/evaluate")
def evaluate():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Dữ liệu gửi lên phải là một object JSON (vd. {\"occ\": ...})."}), 400
    try:
        result = {
            "pha_do": evaluate_pha_do(payload),
            "mat_na": evaluate_mat_na(payload),
            "co_gioi": evaluate_co_gioi(payload),
            "loa": evaluate_loa(payload),
            "binh": evaluate_binh(payload),
            "den": evaluate_den(payload),
        }
    except PhuongTienInputError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)
