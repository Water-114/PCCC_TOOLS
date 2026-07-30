"""Xac thuc bang token (khong dung cookie) - phu hop vi index.html co the mo qua
file:// hoac cong khac Flask, cookie phien dang nhap kieu thuong se bi trinh
duyet chan (CORS/SameSite)."""

from functools import wraps

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .models import User

TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # 7 ngay


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="auth-token")


def create_token(user_id: int) -> str:
    return _serializer().dumps({"uid": user_id})


def verify_token(token: str):
    try:
        data = _serializer().loads(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return User.query.get(data.get("uid"))


def extract_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):].strip()
    return None


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = extract_token()
        user = verify_token(token) if token else None
        if not user:
            return jsonify({"error": "Chưa đăng nhập hoặc phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại."}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = extract_token()
        user = verify_token(token) if token else None
        if not user:
            return jsonify({"error": "Chưa đăng nhập hoặc phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại."}), 401
        if user.role != "admin":
            return jsonify({"error": "Tài khoản không có quyền quản trị."}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return wrapper
