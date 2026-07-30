from flask import Blueprint, jsonify, request

from ..auth import extract_token, verify_token
from ..extensions import db
from ..models import Feedback

bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")


@bp.post("")
def submit_feedback():
    payload = request.get_json(silent=True) or {}
    feature = (payload.get("feature") or "").strip()
    rating = payload.get("rating")
    comment = (payload.get("comment") or "").strip() or None

    if not feature:
        return jsonify({"error": "Thiếu 'feature' (tính năng đang góp ý)."}), 400
    if rating is not None:
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            return jsonify({"error": "'rating' phải là số từ 1 đến 5."}), 400
        if not 1 <= rating <= 5:
            return jsonify({"error": "'rating' phải trong khoảng 1-5."}), 400

    # Đăng nhập là tuỳ chọn cho góp ý — vẫn nhận góp ý ẩn danh nếu token không hợp lệ.
    token = extract_token()
    user = verify_token(token) if token else None

    fb = Feedback(user_id=user.id if user else None, feature=feature, rating=rating, comment=comment)
    db.session.add(fb)
    db.session.commit()

    return jsonify({"ok": True})
