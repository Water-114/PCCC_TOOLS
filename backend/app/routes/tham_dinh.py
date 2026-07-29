from flask import Blueprint, jsonify, request

from ..services.tham_dinh import (
    BASE_FIELDS,
    EXTRA_FIELDS,
    OCCUPATIONS,
    ThamDinhInputError,
    evaluate_tham_dinh,
)

bp = Blueprint("tham_dinh", __name__, url_prefix="/api/tham-dinh")


@bp.get("/occupancies")
def occupancies():
    return jsonify({
        "occupations": OCCUPATIONS,
        "baseFields": BASE_FIELDS,
        "extraFields": EXTRA_FIELDS,
    })


@bp.post("/evaluate")
def evaluate():
    payload = request.get_json(silent=True) or {}
    try:
        result = evaluate_tham_dinh(payload)
    except ThamDinhInputError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)
