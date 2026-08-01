from flask import Blueprint, jsonify, request

from ..auth import extract_token, verify_token
from ..extensions import db, limiter
from ..models import Feedback
from ..services.feedback_bonus import FEEDBACK_BONUS_FEATURE, maybe_grant_feedback_bonus

bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")

# Danh sách "feature" hợp lệ. "aiho_bo_ho_so" là góp ý chung cho cả một lượt
# chạy Bộ hồ sơ (task UX "Góp ý Bộ hồ sơ", sau Batch 3) — thay cho nhãn cũ
# 'aiho_baochay' từng bị gán cứng dù đã chạy hạng mục nào. Giữ lại các nhãn
# cũ trong whitelist để không phá dữ liệu góp ý cũ đã lưu. Chặn giá trị tự do
# bất kỳ mà client có thể POST thẳng tới API để tránh phình dữ liệu rác/không
# phân loại được.
ALLOWED_FEATURES = {"aiho_baochay", "aiho_dienpccc", "aiho_ccnuoc", "aiho_bo_ho_so"}
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

    # Thuong gop y (Batch 5A sub-buoc 5) chi ap dung cho gop y co dang nhap va
    # dung dung "feature" cua luong Bo ho so — xem services/feedback_bonus.py.
    bonus_granted = False
    if user and feature == FEEDBACK_BONUS_FEATURE:
        bonus_granted = maybe_grant_feedback_bonus(user.id)

    return jsonify({"ok": True, "bonus_granted": bonus_granted})
