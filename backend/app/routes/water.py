from flask import Blueprint, jsonify, request

from ..services.water_calculator import calculate_water_tank

bp = Blueprint("water", __name__, url_prefix="/api/water")


@bp.post("/calculate")
def calculate():
    payload = request.get_json(silent=True) or {}
    try:
        result = calculate_water_tank(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)
