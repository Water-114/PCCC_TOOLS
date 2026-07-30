import os

import click
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_migrate import Migrate

from .config import Config
from .extensions import db

# Thư mục gốc của repo (chứa index.html, css/, js/) — 2 cấp trên package app/ này
# (backend/app/__init__.py -> backend/app -> backend -> gốc repo).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    Migrate(app, db)

    CORS(app, origins=[app.config["FRONTEND_ORIGIN"]])
    # Trang tĩnh index.html (mở qua file:// hoặc server khác) gọi các tính năng AI đọc bản vẽ,
    # đăng nhập/đăng ký, góp ý — mở CORS riêng rộng hơn cho các nhóm route này vì chỉ chạy local/demo.
    CORS(app, resources={
        r"/api/aiho/*": {"origins": "*"},
        r"/api/auth/*": {"origins": "*"},
        r"/api/feedback*": {"origins": "*"},
        r"/api/admin/*": {"origins": "*"},
    })

    from .routes.water import bp as water_bp
    from .routes.ai import bp as ai_bp
    from .routes.tham_dinh import bp as tham_dinh_bp
    from .routes.drive import bp as drive_bp
    from .routes.aiho import bp as aiho_bp
    from .routes.auth import bp as auth_bp
    from .routes.feedback import bp as feedback_bp
    from .routes.admin import bp as admin_bp

    app.register_blueprint(water_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(tham_dinh_bp)
    app.register_blueprint(drive_bp)
    app.register_blueprint(aiho_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(admin_bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    # Phục vụ luôn trang tĩnh (index.html/css/js) từ cùng service này khi deploy production
    # (vd. Render) — chỉ mở đúng 3 đường dẫn đã biết là an toàn, không dùng route bắt-hết-mọi-thứ
    # để tránh vô tình lộ file khác trong repo (vd. backend/.env).
    @app.get("/")
    def serve_index():
        return send_from_directory(_REPO_ROOT, "index.html")

    @app.get("/css/<path:filename>")
    def serve_css(filename):
        return send_from_directory(os.path.join(_REPO_ROOT, "css"), filename)

    @app.get("/js/<path:filename>")
    def serve_js(filename):
        return send_from_directory(os.path.join(_REPO_ROOT, "js"), filename)

    @app.cli.command("create-admin")
    @click.argument("email")
    @click.argument("password")
    def create_admin(email, password):
        """Tao (hoac nang cap) mot tai khoan admin: flask create-admin <email> <password>"""
        from .models import User

        email = email.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            user.role = "admin"
            user.set_password(password)
            click.echo(f"Da nang cap '{email}' thanh admin va cap nhat mat khau.")
        else:
            user = User(email=email, role="admin")
            user.set_password(password)
            db.session.add(user)
            click.echo(f"Da tao tai khoan admin moi: {email}")
        db.session.commit()

    return app
