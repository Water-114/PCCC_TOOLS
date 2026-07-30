from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from ..auth import admin_required
from ..config import Config
from ..extensions import db
from ..models import AIHO_API_NAME, Feedback, User, UsageLog, count_usage_today

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/stats")
@admin_required
def stats():
    total_users = User.query.count()
    total_calls = UsageLog.query.filter(UsageLog.status.in_(("success", "error"))).count()
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    calls_today = UsageLog.query.filter(
        UsageLog.status.in_(("success", "error")), UsageLog.created_at >= start_of_day
    ).count()
    total_feedback = Feedback.query.count()

    return jsonify({
        "total_users": total_users,
        "total_calls": total_calls,
        "calls_today": calls_today,
        "total_feedback": total_feedback,
        "daily_quota": Config.AIHO_DAILY_QUOTA,
    })


@bp.get("/users")
@admin_required
def users():
    rows = User.query.order_by(User.created_at.desc()).all()
    data = []
    for u in rows:
        used = count_usage_today(u.id, AIHO_API_NAME)
        limit = u.effective_quota()
        data.append({
            **u.to_public_dict(),
            "created_at": u.created_at.isoformat(),
            "daily_quota": u.daily_quota,
            "default_quota": Config.AIHO_DAILY_QUOTA,
            "used_today": used,
            "remaining_today": max(0, limit - used),
        })
    return jsonify({"users": data})


@bp.patch("/users/<int:user_id>/quota")
@admin_required
def set_user_quota(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Không tìm thấy tài khoản."}), 404

    payload = request.get_json(silent=True) or {}
    raw = payload.get("daily_quota", None)

    if raw is None or raw == "":
        user.daily_quota = None
    else:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return jsonify({"error": "Hạn mức phải là một số nguyên."}), 400
        if value < 0:
            return jsonify({"error": "Hạn mức không thể âm."}), 400
        user.daily_quota = value

    db.session.commit()
    used = count_usage_today(user.id, AIHO_API_NAME)
    limit = user.effective_quota()
    return jsonify({
        **user.to_public_dict(),
        "daily_quota": user.daily_quota,
        "default_quota": Config.AIHO_DAILY_QUOTA,
        "used_today": used,
        "remaining_today": max(0, limit - used),
    })


@bp.get("/feedback")
@admin_required
def feedback():
    rows = Feedback.query.order_by(Feedback.created_at.desc()).all()
    data = [{
        "id": f.id,
        "feature": f.feature,
        "rating": f.rating,
        "comment": f.comment,
        "user_email": f.user.email if f.user else None,
        "created_at": f.created_at.isoformat(),
    } for f in rows]
    return jsonify({"feedback": data})
