from flask import Flask, jsonify
from flask_cors import CORS

from .config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, origins=[app.config["FRONTEND_ORIGIN"]])
    # Trang tĩnh index.html (mở qua file:// hoặc server khác) gọi tính năng AI đọc bản vẽ —
    # mở CORS riêng cho nhóm route này, phạm vi rộng hơn vì chỉ chạy local/demo.
    CORS(app, resources={r"/api/aiho/*": {"origins": "*"}})

    from .routes.water import bp as water_bp
    from .routes.ai import bp as ai_bp
    from .routes.tham_dinh import bp as tham_dinh_bp
    from .routes.drive import bp as drive_bp
    from .routes.aiho import bp as aiho_bp

    app.register_blueprint(water_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(tham_dinh_bp)
    app.register_blueprint(drive_bp)
    app.register_blueprint(aiho_bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app
