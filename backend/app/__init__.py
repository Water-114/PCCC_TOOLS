import os

import click
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_migrate import Migrate
from sqlalchemy import text

from .config import Config
from .extensions import db, limiter

# Thư mục gốc của repo (chứa index.html, css/, js/) — 2 cấp trên package app/ này
# (backend/app/__init__.py -> backend/app -> backend -> gốc repo).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Render tự set biến này cho mọi service chạy trên nền tảng của họ — dùng làm
# tín hiệu đáng tin cậy để biết "đang chạy production" mà không cần thêm biến
# môi trường mới người dùng phải nhớ cấu hình.
_IS_RENDER = bool(os.getenv("RENDER"))

_INSECURE_SECRET_KEY_FALLBACK = "doi-chuoi-nay-truoc-khi-dung-that-o-production"


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    # Chặn cứng nếu chạy trên Render (production) mà SECRET_KEY vẫn là chuỗi
    # fallback công khai (đã commit trong backend/.env.example) — chuỗi này ký
    # được token đăng nhập giả mạo bất kỳ tài khoản nào nếu ai đó biết trước.
    if _IS_RENDER and app.config.get("SECRET_KEY") == _INSECURE_SECRET_KEY_FALLBACK:
        raise RuntimeError(
            "SECRET_KEY đang dùng giá trị mặc định không an toàn trên môi trường "
            "Render — phải đặt biến môi trường SECRET_KEY thật (vd. generateValue "
            "trong render.yaml) trước khi khởi động."
        )

    db.init_app(app)
    Migrate(app, db)
    limiter.init_app(app)

    with app.app_context():
        if db.engine.dialect.name == "sqlite":
            # Mac dinh, pysqlite tri hoan viec khoa ghi cho toi cau lenh ghi DAU
            # TIEN trong transaction (thay vi ngay khi transaction bat dau) - nghia
            # la nhieu transaction co the cung doc (SELECT COUNT) truoc khi bat ky
            # transaction nao kip ghi, gay rang buoc kiem tra-roi-ghi (quota
            # reservation o routes/aiho.py) khong nguyen tu that su. Bat "BEGIN
            # IMMEDIATE" cho MOI transaction tren SQLite de khoa ghi ngay tu dau,
            # buoc cac transaction dong thoi phai xep hang - day la khuyen nghi
            # chinh thuc cua SQLAlchemy cho pysqlite khi can transaction dang tin
            # cay duoi tai da luong/da tien trinh.
            from sqlalchemy import event

            @event.listens_for(db.engine, "connect")
            def _sqlite_disable_pysqlite_autobegin(dbapi_connection, connection_record):
                dbapi_connection.isolation_level = None

            @event.listens_for(db.engine, "begin")
            def _sqlite_begin_immediate(conn):
                conn.exec_driver_sql("BEGIN IMMEDIATE")

    CORS(app, origins=[app.config["FRONTEND_ORIGIN"]])
    # Trang tĩnh index.html (mở qua file:// hoặc server khác) gọi các tính năng AI đọc bản vẽ,
    # đăng nhập/đăng ký, góp ý — mở CORS riêng rộng hơn cho các nhóm route này khi chạy dev
    # local (server tĩnh cổng khác). Trên Render (production, cùng origin với frontend nên
    # trình duyệt không cần CORS cho người dùng thật), thắt lại theo đúng FRONTEND_ORIGIN
    # thay vì "*" — an toàn hơn cho các route auth/admin/aiho/feedback.
    _wide_cors_origins = [app.config["FRONTEND_ORIGIN"]] if _IS_RENDER else "*"
    CORS(app, resources={
        r"/api/aiho/*": {"origins": _wide_cors_origins},
        r"/api/auth/*": {"origins": _wide_cors_origins},
        r"/api/feedback*": {"origins": _wide_cors_origins},
        r"/api/admin/*": {"origins": _wide_cors_origins},
    })

    @app.after_request
    def _set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src *; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response

    @app.errorhandler(Exception)
    def _handle_uncaught_exception(exc):
        # Luoi an toan cuoi cung cho MOI exception khong duoc route nao tu bat
        # rieng (vd. loi DB bat ngo o admin.py) - log day du server-side, chi
        # tra ve client 1 thong bao chung chung, khong lo noi dung exception
        # that (co the chua chi tiet noi bo) ra ngoai.
        from werkzeug.exceptions import HTTPException

        if isinstance(exc, HTTPException):
            return exc
        app.logger.exception("Loi khong duoc xu ly rieng: %s", exc)
        return jsonify({"error": "Đã có lỗi xảy ra, vui lòng thử lại sau."}), 500

    from .routes.water import bp as water_bp
    from .routes.ai import bp as ai_bp
    from .routes.tham_dinh import bp as tham_dinh_bp
    from .routes.he_thong_bat_buoc import bp as he_thong_bat_buoc_bp
    from .routes.drive import bp as drive_bp
    from .routes.aiho import bp as aiho_bp
    from .routes.auth import bp as auth_bp
    from .routes.feedback import bp as feedback_bp
    from .routes.admin import bp as admin_bp

    app.register_blueprint(water_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(tham_dinh_bp)
    app.register_blueprint(he_thong_bat_buoc_bp)
    app.register_blueprint(drive_bp)
    app.register_blueprint(aiho_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(admin_bp)

    @app.get("/api/health")
    def health():
        # Kiem tra ket noi database that (khong chi tra "ok" tinh) - de Render
        # (hoac giam sat khac) phat hien duoc khi Postgres khong ket noi duoc,
        # thay vi bao "khoe" trong khi request that se loi database.
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            app.logger.exception("Health check: khong ket noi duoc database")
            return jsonify({"status": "error", "database": "error"}), 503
        return jsonify({"status": "ok", "database": "ok"})

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
