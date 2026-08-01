"""Nạp thêm Bộ hồ sơ (Batch 5A, sub-bước 3) — user tạo yêu cầu nạp + xem số dư/
lịch sử ledger. Xác nhận/từ chối là việc của admin (xem routes/admin.py)."""

from flask import Blueprint, g, jsonify

from ..auth import login_required
from ..extensions import limiter
from ..models import CreditLedger
from ..services import credits, topup

bp = Blueprint("topup", __name__, url_prefix="/api/topup")

_LEDGER_MAX_ROWS = 200


@bp.post("/request")
@login_required
@limiter.limit("10/hour")
def create_topup_request():
    try:
        bank_info = topup.bank_transfer_info()
    except topup.BankInfoNotConfigured as exc:
        return jsonify({"error": str(exc)}), 503

    row = topup.create_topup_request(g.current_user.id)
    return jsonify({
        "id": row.id,
        "reference_code": row.reference_code,
        "amount_vnd": row.amount_vnd,
        "credits_to_grant": row.credits_to_grant,
        "status": row.status,
        "bank": bank_info,
    })


@bp.post("/<int:request_id>/confirm-transfer")
@login_required
def confirm_transfer(request_id):
    """Nút "Tôi đã chuyển khoản" — CHỈ đổi trạng thái sang 'cho_xac_nhan' (lúc
    này mới xuất hiện trong danh sách chờ của admin), KHÔNG tự cộng Bộ hồ sơ."""
    try:
        row = topup.confirm_transfer(request_id, g.current_user.id)
    except topup.TopupRequestNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"id": row.id, "status": row.status, "reference_code": row.reference_code})


@bp.get("/ledger")
@login_required
def ledger():
    user = g.current_user
    entries = (
        CreditLedger.query.filter_by(user_id=user.id)
        .order_by(CreditLedger.created_at.desc(), CreditLedger.id.desc())
        .limit(_LEDGER_MAX_ROWS)
        .all()
    )
    return jsonify({
        "bo_ho_so_con_lai": credits.credit_balance(user.id),
        "ledger": [{
            "id": e.id,
            "delta": e.delta,
            "reason": e.reason,
            "balance_after": e.balance_after,
            "note": e.note,
            "created_at": e.created_at.isoformat(),
        } for e in entries],
    })
