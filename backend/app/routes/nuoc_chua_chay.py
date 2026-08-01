"""API contract cho cụm 3 (nước chữa cháy, BƯỚC 3-4) — Batch 3.

Theo quyết định của owner: đây là endpoint "đối chiếu song song", production
(js/tuvan-so-bo.js) chưa gọi tới route này — xem
docs/02-implementation-batches.md mục Batch 3.
"""

from flask import Blueprint, jsonify, request

from ..services.nuoc_chua_chay import NuocChuaChayInputError, evaluate_nuoc

bp = Blueprint("nuoc_chua_chay", __name__, url_prefix="/api/nuoc-chua-chay")


@bp.post("/evaluate")
def evaluate():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Dữ liệu gửi lên phải là một object JSON (vd. {\"occ\": ...})."}), 400
    try:
        result = evaluate_nuoc(payload)
    except NuocChuaChayInputError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)
