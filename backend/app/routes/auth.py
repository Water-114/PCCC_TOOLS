import re

from flask import Blueprint, g, jsonify, request

from ..auth import create_token, login_required
from ..config import Config
from ..extensions import db
from ..models import AIHO_API_NAME, User, count_usage_today

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _user_payload(user: User) -> dict:
    used = count_usage_today(user.id, AIHO_API_NAME)
    return {
        **user.to_public_dict(),
        "quota": {
            "limit": Config.AIHO_DAILY_QUOTA,
            "used_today": used,
            "remaining_today": max(0, Config.AIHO_DAILY_QUOTA - used),
        },
    }


@bp.post("/register")
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
    db.session.commit()

    return jsonify({"token": create_token(user.id), "user": _user_payload(user)})


@bp.post("/login")
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
