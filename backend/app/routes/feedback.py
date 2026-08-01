from flask import Blueprint, jsonify, request

from ..auth import extract_token, verify_token
from ..extensions import db, limiter
from ..models import Feedback

bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")

# Danh sách "feature" hợp lệ — khớp đúng giá trị frontend thực sự gửi hôm nay
# (js/ai-doc-ho-so.js gửi cố định 'aiho_baochay' cho mọi lượt góp ý dù đã chạy
# hạng mục nào — nhãn hơi lệch nhưng không phải vấn đề bảo mật, để dành sửa
# nhãn khi đụng tới ai-doc-ho-so.js ở dịp khác). Chặn giá trị tự do bất kỳ mà
# client có thể POST thẳng tới API để tránh phình dữ liệu rác/không phân loại được.
ALLOWED_FEATURES = {"aiho_baochay", "aiho_dienpccc", "aiho_ccnuoc"}
MAX_COMMENT_LENGTH = 2000


@bp.post("")
@limiter.limit("10/hour")
def submit_feedback():
    payload = request.get_json(silent=True) or {}
    feature = (payload.get("feature") or "").strip()
    rating = payload.get("rating")
    comment = (payload.get("comment") or "").strip() or None

    if feature not in ALLOWED_FEATURES:
        return jsonify({"error": "Giá trị 'feature' không hợp lệ."}), 400
    if comment is not None and len(comment) > MAX_COMMENT_LENGTH:
        return jsonify({"error": f"Góp ý không được quá {MAX_COMMENT_LENGTH} ký tự."}), 400
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
