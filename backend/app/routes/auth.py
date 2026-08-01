import re

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from ..auth import create_token, login_required
from ..extensions import db, limiter
from ..models import User
from ..services import credits, email_verification, mailer

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Loại trừ thêm <>"' (ký tự đặc biệt HTML) khỏi local-part/domain — email hợp lệ
# thông thường không bao giờ cần các ký tự này; chặn thêm 1 lớp phòng thủ cho
# XSS lưu trữ qua trường email (được escape đúng ở phía hiển thị — đây chỉ là
# lớp bổ sung, không phải chỗ chặn chính).
EMAIL_RE = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+$")


def _user_payload(user: User) -> dict:
    # Batch 5A sub-buoc 2: doi "quota" (luot/ngay cu, aiho.py khong con dung nua)
    # sang so du "Bo ho so" - nguon su that duy nhat la CreditLedger.
    return {
        **user.to_public_dict(),
        "bo_ho_so": {"con_lai": credits.credit_balance(user.id)},
    }


@bp.post("/register")
@limiter.limit("5/hour")
def register():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not EMAIL_RE.match(email):
        return jsonify({"error": "Email không hợp lệ."}), 400
    if len(password) < 6:
        return jsonify({"error": "Mật khẩu cần ít nhất 6 ký tự."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email này đã đăng ký tài khoản rồi — thử đăng nhập."}), 409

    user = User(email=email, role="user")
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        # Phong rang buoc unique bi vi pham do 2 request dang ky cung email
        # gan nhu dong thoi (kiem tra o dong 37 khong nguyen tu voi insert nay).
        db.session.rollback()
        current_app.logger.warning("Dang ky trung email do race condition: %s", email)
        return jsonify({"error": "Email này đã đăng ký tài khoản rồi — thử đăng nhập."}), 409

    return jsonify({"token": create_token(user.id), "user": _user_payload(user)})


@bp.post("/login")
@limiter.limit("10/minute")
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Email hoặc mật khẩu không đúng."}), 401

    return jsonify({"token": create_token(user.id), "user": _user_payload(user)})


@bp.get("/me")
@login_required
def me():
    return jsonify({"user": _user_payload(g.current_user)})


def _verification_email_content(token: str) -> tuple[str, str]:
    verify_url = f"{current_app.config['FRONTEND_ORIGIN']}/?verify-email={token}"
    subject = "Xác thực email — Tư vấn PCCC"
    body = (
        "Chào anh/chị,\n\n"
        "Vui lòng bấm vào liên kết dưới đây để xác thực email và nhận 2 Bộ hồ sơ dùng thử:\n"
        f"{verify_url}\n\n"
        f"Liên kết có hiệu lực trong {email_verification.TOKEN_TTL_HOURS} giờ.\n"
        "Nếu anh/chị không yêu cầu xác thực, vui lòng bỏ qua email này."
    )
    return subject, body


@bp.post("/send-verification-email")
@login_required
@limiter.limit("5/hour")
def send_verification_email():
    user = g.current_user
    if user.email_verified_at is not None:
        return jsonify({"error": "Email này đã được xác thực rồi."}), 409

    token = email_verification.create_email_verification_token(user.id)
    subject, body = _verification_email_content(token)
    mailer.send_email(user.email, subject, body)
    return jsonify({"message": "Đã gửi email xác thực — vui lòng kiểm tra hộp thư."})


@bp.post("/verify-email")
@limiter.limit("10/hour")
def verify_email():
    payload = request.get_json(silent=True) or {}
    token = (payload.get("token") or "").strip()
    if not token:
        return jsonify({"error": "Thiếu token xác thực."}), 400

    try:
        user, granted = email_verification.consume_email_verification_token(token)
    except email_verification.InvalidVerificationToken as exc:
        return jsonify({"error": str(exc)}), 400

    message = "Xác thực email thành công!"
    if granted:
        message += f" Đã cộng {email_verification.EMAIL_VERIFICATION_CREDITS} Bộ hồ sơ dùng thử."
    return jsonify({
        "message": message,
        "credits_granted": email_verification.EMAIL_VERIFICATION_CREDITS if granted else 0,
        "user": _user_payload(user),
    })
