import re

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from ..auth import create_token, login_required
from ..extensions import db, limiter
from ..models import AIHO_API_NAME, User, count_usage_today

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Loại trừ thêm <>"' (ký tự đặc biệt HTML) khỏi local-part/domain — email hợp lệ
# thông thường không bao giờ cần các ký tự này; chặn thêm 1 lớp phòng thủ cho
# XSS lưu trữ qua trường email (được escape đúng ở phía hiển thị — đây chỉ là
# lớp bổ sung, không phải chỗ chặn chính).
EMAIL_RE = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+$")


def _user_payload(user: User) -> dict:
    used = count_usage_today(user.id, AIHO_API_NAME)
    limit = user.effective_quota()
    return {
        **user.to_public_dict(),
        "quota": {
            "limit": limit,
            "used_today": used,
            "remaining_today": max(0, limit - used),
        },
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
