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


def _build_engine_options(db_url: str) -> dict:
    # pool_pre_ping: kiem tra connection con song truoc khi dung (an toan cho moi
    # loai pool) - tranh loi "connection da chet" khi Postgres/Render tu dong
    # ngat ket noi idle. pool_size/max_overflow chi hop le voi QueuePool (Postgres);
    # SQLite dung SingletonThreadPool/NullPool nen khong nhan 2 tham so nay.
    if db_url.startswith("postgresql"):
        return {
            "pool_pre_ping": True,
            "pool_recycle": 280,
            "pool_size": 5,
            "max_overflow": 10,
        }
    # connect_args timeout: so giay 1 connection SQLite CHO (block, tu dong thu
    # lai o tang driver) truoc khi nem "database is locked", thay vi mac dinh
    # 5s cua sqlite3 - qua ngan khi nhieu request dong thoi cung xep hang qua
    # "BEGIN IMMEDIATE" (co chu dich, xem app/__init__.py) cho 1 transaction
    # nhieu buoc (vd mo phien Bo ho so: kiem tra so du + ghi ledger + ghi phien).
    return {"pool_pre_ping": True, "connect_args": {"timeout": 30}}


class Config:
    AI_PROVIDER = os.getenv("AI_PROVIDER", "claude")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # Dung cho 2 viec: (1) CORS cho cac nhom route auth/admin/aiho/feedback/topup
    # tren production (xem app/__init__.py), (2) dung link xac thuc email
    # (routes/auth.py). Production tren Render la 1 service Flask duy nhat phuc
    # vu ca API lan static UI cung origin nen gia tri that duoc dat qua bien moi
    # truong o Render Dashboard; mac dinh local duoi day tro thang toi Flask dev
    # server (http://127.0.0.1:5000, xem README) — KHONG con tro toi Vite (5173)
    # vi frontend/ (React MVP rieng) da bi go khoi source.
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5000")

    SECRET_KEY = os.getenv("SECRET_KEY", "doi-chuoi-nay-truoc-khi-dung-that-o-production")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(_BASE_DIR, 'app.db')}"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _build_engine_options(SQLALCHEMY_DATABASE_URI)

    AIHO_DAILY_QUOTA = int(os.getenv("AIHO_DAILY_QUOTA", "5"))

    # Batch 5A: gui email xac thuc qua SMTP - hoan toan cau hinh qua bien moi
    # truong, KHONG hardcode provider/thong tin dang nhap nao trong code. Neu
    # SMTP_HOST rong (vd moi truong dev local chua thiet lap): services/mailer.py
    # se KHONG gui that, chi log ra console - tranh chan dung luong dang
    # ky/xac thuc chi vi thieu cau hinh SMTP luc dev/test.
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")

    # Batch 5A sub-buoc 3: thong tin nhan chuyen khoan thu cong, CHI cau hinh
    # qua bien moi truong - TUYET DOI khong dat gia tri vi du/placeholder nao o
    # day hay trong .env.example (kem ca luc deploy that). Neu thieu bat ky bien
    # nao trong 3 bien bat buoc (so TK/ten chu TK/ngan hang), routes/topup.py se
    # tra loi ro rang thay vi lo chuoi rong ra UI nhu the la thong tin that.
    BANK_ACCOUNT_NUMBER = os.getenv("BANK_ACCOUNT_NUMBER", "")
    BANK_ACCOUNT_NAME = os.getenv("BANK_ACCOUNT_NAME", "")
    BANK_NAME = os.getenv("BANK_NAME", "")
    BANK_QR_URL = os.getenv("BANK_QR_URL", "")  # tuy chon - anh QR (neu co)

    # Gioi han kich thuoc toan bo request body o tang Flask/Werkzeug — chan som (413)
    # truoc khi buffer het vao RAM, thay vi chi dua vao kiem tra thu cong sau khi da
    # doc het file trong aiho.py. Phai >= gioi han file LON NHAT trong toan app +
    # bien du cho multipart overhead: ca 3 luong dinh file (7 route rieng le, multi-
    # attach, va /read-merged) deu dung chung muc PDF toi da 22MB (SINGLE_MAX_BYTES_PDF/
    # MERGED_MAX_BYTES_PDF, xem routes/aiho.py) — 26MB de con ~4MB bien, giu dung ty le
    # bien nhu truoc (24MB cho 20MB file -> 26MB cho 22MB file).
    MAX_CONTENT_LENGTH = 26 * 1024 * 1024
