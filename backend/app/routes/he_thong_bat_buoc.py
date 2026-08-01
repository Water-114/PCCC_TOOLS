"""API contract cho cụm 2 (hệ thống bắt buộc, QCVN 10:2025/BCA) — Batch 3.

Theo quyết định của owner: đây là endpoint "đối chiếu song song", production
(js/tuvan-so-bo.js) chưa gọi tới các route này — xem
docs/02-implementation-batches.md mục Batch 3.
"""

from flask import Blueprint, jsonify, request

from ..services.he_thong_bat_buoc import (
    HeThongBatBuocInputError,
    evaluate_bao_chay,
    evaluate_hong_nuoc,
    evaluate_ngoai_nha,
    evaluate_sprinkler,
)

bp = Blueprint("he_thong_bat_buoc", __name__, url_prefix="/api/he-thong-bat-buoc")


@bp.post("/evaluate")
def evaluate():
    payload = request.get_json(silent=True)
    # JSON hop le nhung khong phai object (list/string/number/bool) khien
    # payload.get(...) o tang service nem AttributeError khong duoc bat rieng
    # -> 500. Chan som o day, tra 400 ro rang.
    if not isinstance(payload, dict):
        return jsonify({"error": "Dữ liệu gửi lên phải là một object JSON (vd. {\"occ\": \"chungcu\", ...})."}), 400
    try:
        result = {
            "bao_chay": evaluate_bao_chay(payload),
            "sprinkler": evaluate_sprinkler(payload),
            "hong_nuoc": evaluate_hong_nuoc(payload),
            "ngoai_nha": evaluate_ngoai_nha(payload),
        }
    except HeThongBatBuocInputError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)
