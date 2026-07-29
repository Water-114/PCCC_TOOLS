from flask import Flask, jsonify
from flask_cors import CORS

from .config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, origins=[app.config["FRONTEND_ORIGIN"]])

    from .routes.water import bp as water_bp
    from .routes.ai import bp as ai_bp
    from .routes.tham_dinh import bp as tham_dinh_bp

    app.register_blueprint(water_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(tham_dinh_bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app
