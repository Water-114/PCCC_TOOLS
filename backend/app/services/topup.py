"""Nạp thêm Bộ hồ sơ bằng chuyển khoản ngân hàng thủ công (Batch 5A, sub-bước
3) — tạo yêu cầu với mã giao dịch riêng để đối chiếu thủ công, admin xác
nhận/từ chối. KHÔNG tích hợp cổng thanh toán tự động nào (payOS/VNPAY/webhook)
— đúng chính sách đã chốt, toàn bộ xác nhận là thủ công do admin thực hiện.

State machine 3 trạng thái:
  cho_chuyen_khoan --(user: confirm_transfer)--> cho_xac_nhan
  cho_xac_nhan --(admin: confirm_topup_request)--> da_xac_nhan
  cho_xac_nhan --(admin: reject_topup_request)--> tu_choi
'cho_chuyen_khoan' là nháp — CHƯA vào hàng đợi admin (GET /api/admin/topup-requests
mặc định chỉ lọc 'cho_xac_nhan', xem routes/admin.py).
"""

import secrets
from datetime import datetime, timezone

from flask import current_app

from ..extensions import db
from ..models import TopupRequest
from . import credits

# Bo cac ky tu de nham lan khi doi chieu bang tay (0/O, 1/I/L) - ma giao dich
# nay se duoc nguoi dung go vao noi dung chuyen khoan ngan hang that.
_REFERENCE_CODE_CHARS = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_REFERENCE_CODE_LEN = 8
_MAX_REFERENCE_CODE_ATTEMPTS = 5


class TopupRequestError(Exception):
    pass


class BankInfoNotConfigured(TopupRequestError):
    pass


class TopupRequestNotFound(TopupRequestError):
    pass


class InvalidTopupStatusTransition(TopupRequestError):
    pass


def _utcnow():
    return datetime.now(timezone.utc)


def _generate_reference_code() -> str:
    suffix = "".join(secrets.choice(_REFERENCE_CODE_CHARS) for _ in range(_REFERENCE_CODE_LEN))
    return f"BHS-{suffix}"


def bank_transfer_info() -> dict:
    """Đọc thông tin nhận chuyển khoản từ biến môi trường. Raise
    BankInfoNotConfigured nếu thiếu bất kỳ biến BẮT BUỘC nào (số TK/tên chủ
    TK/ngân hàng) — KHÔNG trả chuỗi rỗng ra UI như thể đó là thông tin thật."""
    cfg = current_app.config
    account_number = cfg.get("BANK_ACCOUNT_NUMBER")
    account_name = cfg.get("BANK_ACCOUNT_NAME")
    bank_name = cfg.get("BANK_NAME")
    if not (account_number and account_name and bank_name):
        raise BankInfoNotConfigured(
            "Chưa cấu hình đủ thông tin nhận chuyển khoản — liên hệ quản trị viên."
        )
    return {
        "account_number": account_number,
        "account_name": account_name,
        "bank_name": bank_name,
        "qr_url": cfg.get("BANK_QR_URL") or None,
    }


def create_topup_request(user_id: int) -> TopupRequest:
    """Tạo 1 yêu cầu nạp với mã giao dịch riêng (unique, dễ đối chiếu thủ công),
    trạng thái 'cho_chuyen_khoan' (nháp) — CHƯA vào hàng đợi admin cho tới khi
    user gọi confirm_transfer() báo đã chuyển khoản xong."""
    for _ in range(_MAX_REFERENCE_CODE_ATTEMPTS):
        code = _generate_reference_code()
        if not TopupRequest.query.filter_by(reference_code=code).first():
            break
    else:
        raise TopupRequestError("Không tạo được mã giao dịch — vui lòng thử lại.")

    row = TopupRequest(
        user_id=user_id,
        reference_code=code,
        amount_vnd=100000,
        credits_to_grant=5,
        status="cho_chuyen_khoan",
    )
    db.session.add(row)
    db.session.commit()
    return row


def confirm_transfer(request_id: int, user_id: int) -> TopupRequest:
    """User tự báo đã chuyển khoản — chuyển 'cho_chuyen_khoan' -> 'cho_xac_nhan'
    (lúc này mới xuất hiện trong danh sách chờ của admin). Chỉ chính chủ yêu
    cầu mới gọi được (khác user hoặc không tồn tại đều coi là không tìm thấy —
    không lộ sự tồn tại của yêu cầu người khác). Idempotent: gọi lại khi đã
    qua khỏi 'cho_chuyen_khoan' (kể cả đã bị admin xử lý) thì trả về nguyên
    trạng, không lỗi."""
    row = TopupRequest.query.get(request_id)
    if row is None or row.user_id != user_id:
        raise TopupRequestNotFound("Không tìm thấy yêu cầu nạp.")
    if row.status != "cho_chuyen_khoan":
        return row
    row.status = "cho_xac_nhan"
    db.session.commit()
    return row


def confirm_topup_request(request_id: int, admin_user_id: int) -> TopupRequest:
    """Idempotent: yêu cầu đã 'da_xac_nhan' thì trả về nguyên trạng, KHÔNG ghi
    ledger thêm (không cộng 2 lần). Chỉ hợp lệ khi đang 'cho_xac_nhan' — yêu
    cầu còn 'cho_chuyen_khoan' (user chưa xác nhận đã chuyển khoản) hoặc đã
    'tu_choi' đều bị từ chối xác nhận rõ ràng."""
    row = TopupRequest.query.get(request_id)
    if row is None:
        raise TopupRequestNotFound("Không tìm thấy yêu cầu nạp.")
    if row.status == "da_xac_nhan":
        return row
    if row.status == "cho_chuyen_khoan":
        raise InvalidTopupStatusTransition(
            "Yêu cầu này chưa được người dùng xác nhận đã chuyển khoản — chưa thể xác nhận."
        )
    if row.status == "tu_choi":
        raise InvalidTopupStatusTransition("Yêu cầu này đã bị từ chối — không thể xác nhận.")

    row.status = "da_xac_nhan"
    row.reviewed_at = _utcnow()
    row.reviewed_by_admin_id = admin_user_id
    db.session.add(credits.build_ledger_entry(
        row.user_id, row.credits_to_grant, credits.CREDIT_REASON_TOPUP_CONFIRMED,
        note=f"Xác nhận chuyển khoản — mã {row.reference_code}",
    ))
    db.session.commit()
    return row


def reject_topup_request(request_id: int, admin_user_id: int) -> TopupRequest:
    """Idempotent: yêu cầu đã 'tu_choi' thì trả về nguyên trạng. Chỉ hợp lệ khi
    đang 'cho_xac_nhan' — yêu cầu còn 'cho_chuyen_khoan' hoặc đã 'da_xac_nhan'
    đều bị từ chối thao tác rõ ràng (không tự đảo ngược 1 xác nhận đã cộng
    Bộ hồ sơ)."""
    row = TopupRequest.query.get(request_id)
    if row is None:
        raise TopupRequestNotFound("Không tìm thấy yêu cầu nạp.")
    if row.status == "tu_choi":
        return row
    if row.status == "cho_chuyen_khoan":
        raise InvalidTopupStatusTransition(
            "Yêu cầu này chưa được người dùng xác nhận đã chuyển khoản — chưa thể từ chối."
        )
    if row.status == "da_xac_nhan":
        raise InvalidTopupStatusTransition("Yêu cầu này đã được xác nhận — không thể từ chối.")

    row.status = "tu_choi"
    row.reviewed_at = _utcnow()
    row.reviewed_by_admin_id = admin_user_id
    db.session.commit()
    return row
