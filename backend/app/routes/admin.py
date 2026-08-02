from flask import Blueprint, g, jsonify, request
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ..auth import admin_required
from ..config import Config
from ..extensions import db
from ..models import AIHO_API_NAME, CreditLedger, Feedback, TopupRequest, User, UsageLog, _start_of_day_utc, count_usage_today
from ..services import credits, topup

bp = Blueprint("admin", __name__, url_prefix="/api/admin")

# Chan trang admin lo mot luong khong gioi han (vd. bang users/feedback phinh
# to theo thoi gian) - gioi han so dong tra ve moi trang, co the tang qua
# ?per_page= nhung khong vuot muc tran nay.
_MAX_PER_PAGE = 300
_DEFAULT_PER_PAGE = 100


def _pagination_params():
    page = request.args.get("page", 1, type=int) or 1
    per_page = request.args.get("per_page", _DEFAULT_PER_PAGE, type=int) or _DEFAULT_PER_PAGE
    return max(1, page), max(1, min(per_page, _MAX_PER_PAGE))


@bp.get("/stats")
@admin_required
def stats():
    total_users = User.query.count()
    total_calls = UsageLog.query.filter(UsageLog.status.in_(("success", "error"))).count()
    start_of_day = _start_of_day_utc()
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
    page, per_page = _pagination_params()
    pagination = User.query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    rows = pagination.items

    # 1 truy van tong hop cho ca trang (group by user_id) thay vi goi
    # count_usage_today() rieng cho tung user — tranh N+1 khi so user tang.
    user_ids = [u.id for u in rows]
    usage_counts = {}
    if user_ids:
        start_of_day = _start_of_day_utc()
        usage_counts = dict(
            db.session.query(UsageLog.user_id, func.count(UsageLog.id))
            .filter(
                UsageLog.user_id.in_(user_ids),
                UsageLog.api_name == AIHO_API_NAME,
                UsageLog.status.in_(("success", "error", "pending")),
                UsageLog.created_at >= start_of_day,
            )
            .group_by(UsageLog.user_id)
            .all()
        )

    # So du Bo ho so THAT (khac han "used_today" - do la han muc goi AI/ngay).
    # 2 truy van group-by rieng cho ca trang, tranh N+1 giong usage_counts o tren.
    credit_balances = {}
    usage_deduction_counts = {}
    if user_ids:
        credit_balances = dict(
            db.session.query(CreditLedger.user_id, func.coalesce(func.sum(CreditLedger.delta), 0))
            .filter(CreditLedger.user_id.in_(user_ids))
            .group_by(CreditLedger.user_id)
            .all()
        )
        usage_deduction_counts = dict(
            db.session.query(CreditLedger.user_id, func.count(CreditLedger.id))
            .filter(
                CreditLedger.user_id.in_(user_ids),
                CreditLedger.reason == credits.CREDIT_REASON_USAGE_DEDUCTION,
            )
            .group_by(CreditLedger.user_id)
            .all()
        )

    data = []
    for u in rows:
        used = usage_counts.get(u.id, 0)
        limit = u.effective_quota()
        data.append({
            **u.to_public_dict(),
            "created_at": u.created_at.isoformat(),
            "daily_quota": u.daily_quota,
            "default_quota": Config.AIHO_DAILY_QUOTA,
            "used_today": used,
            "remaining_today": max(0, limit - used),
            "bo_ho_so_con_lai": int(credit_balances.get(u.id, 0)),
            "bo_ho_so_da_dung": usage_deduction_counts.get(u.id, 0),
        })
    return jsonify({
        "users": data,
        "page": pagination.page,
        "per_page": per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    })


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
    page, per_page = _pagination_params()
    # joinedload(Feedback.user): lay email nguoi gui bang 1 JOIN duy nhat thay
    # vi lazy-load rieng tung dong khi truy cap f.user.email ben duoi.
    pagination = (
        Feedback.query.options(joinedload(Feedback.user))
        .order_by(Feedback.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    data = [{
        "id": f.id,
        "feature": f.feature,
        "rating": f.rating,
        "comment": f.comment,
        "user_email": f.user.email if f.user else None,
        "created_at": f.created_at.isoformat(),
    } for f in pagination.items]
    return jsonify({
        "feedback": data,
        "page": pagination.page,
        "per_page": per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    })


def _topup_request_dict(r: TopupRequest) -> dict:
    return {
        "id": r.id,
        "reference_code": r.reference_code,
        "amount_vnd": r.amount_vnd,
        "credits_to_grant": r.credits_to_grant,
        "status": r.status,
        "user_email": r.user.email if r.user else None,
        "created_at": r.created_at.isoformat(),
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
    }


@bp.get("/topup-requests")
@admin_required
def topup_requests():
    # Mac dinh chi hien "dang cho" (dung yeu cau goc: "danh sach yeu cau nap
    # dang cho") - cho phep xem trang thai khac/tat ca qua ?status= khi can doi
    # chieu lich su, khong can them endpoint rieng.
    status_filter = request.args.get("status", "cho_xac_nhan")
    page, per_page = _pagination_params()
    query = TopupRequest.query.options(joinedload(TopupRequest.user))
    if status_filter and status_filter != "all":
        query = query.filter_by(status=status_filter)
    pagination = query.order_by(TopupRequest.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "topup_requests": [_topup_request_dict(r) for r in pagination.items],
        "page": pagination.page,
        "per_page": per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    })


@bp.post("/topup-requests/<int:request_id>/confirm")
@admin_required
def confirm_topup_request(request_id):
    try:
        row = topup.confirm_topup_request(request_id, g.current_user.id)
    except topup.TopupRequestNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except topup.InvalidTopupStatusTransition as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_topup_request_dict(row))


@bp.post("/topup-requests/<int:request_id>/reject")
@admin_required
def reject_topup_request(request_id):
    try:
        row = topup.reject_topup_request(request_id, g.current_user.id)
    except topup.TopupRequestNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except topup.InvalidTopupStatusTransition as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_topup_request_dict(row))
