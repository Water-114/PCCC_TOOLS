import os
from dotenv import load_dotenv

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Chỉ đích danh file .env theo vị trí của chính config.py — không dựa vào việc
# tự dò tìm theo thư mục làm việc hiện tại (cwd), vốn có thể khác nhau tuỳ cách
# khởi động backend (python run.py / flask run / reloader...) và từng gây lỗi
# "Chưa cấu hình ANTHROPIC_API_KEY" dù .env đã có key.
load_dotenv(os.path.join(_BASE_DIR, ".env"))


def _normalize_db_url(url: str) -> str:
    # Nhiều nền tảng hosting (Render, Heroku...) cấp connection string Postgres bắt đầu bằng
    # "postgres://" — SQLAlchemy 1.4+ chỉ chấp nhận "postgresql://", nên tự đổi lại cho khớp.
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


class Config:
    AI_PROVIDER = os.getenv("AI_PROVIDER", "claude")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

    SECRET_KEY = os.getenv("SECRET_KEY", "doi-chuoi-nay-truoc-khi-dung-that-o-production")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(_BASE_DIR, 'app.db')}"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    AIHO_DAILY_QUOTA = int(os.getenv("AIHO_DAILY_QUOTA", "5"))
