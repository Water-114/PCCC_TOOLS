from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .config import Config
from .extensions import db

# Tên dùng chung cho mọi lượt gọi AI đọc bản vẽ (báo cháy, điện PCCC, ...) —
# tất cả cùng tính vào 1 hạn mức "N lượt/ngày" duy nhất, không tách riêng theo hạng mục.
AIHO_API_NAME = "aiho_analysis"

# Quota riêng cho /api/ai/comment (diễn giải kết quả tính nước — MVP frontend/) —
# tách khỏi AIHO_API_NAME vì đây là tính năng khác, không liên quan tới đọc bản vẽ.
AI_COMMENT_API_NAME = "ai_comment"


def _utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # 'user' | 'admin'
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)
    # Hạn mức lượt đọc bản vẽ/ngày riêng cho tài khoản này — null nghĩa là dùng
    # mức mặc định chung (Config.AIHO_DAILY_QUOTA), do admin đặt qua trang quản trị.
    daily_quota = db.Column(db.Integer, nullable=True)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def effective_quota(self) -> int:
        return self.daily_quota if self.daily_quota is not None else Config.AIHO_DAILY_QUOTA

    def to_public_dict(self) -> dict:
        return {"id": self.id, "email": self.email, "role": self.role}


class UsageLog(db.Model):
    __tablename__ = "usage_log"
    __table_args__ = (
        # count_usage_today() luon loc dong thoi ca 3 cot nay - composite index
        # giup Postgres tra loi truy van quota nhanh khi usage_log co nhieu du
        # lieu, thay vi chi co 2 index don le (user_id, created_at) nhu truoc.
        db.Index("ix_usage_log_user_api_created", "user_id", "api_name", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    api_name = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'success' | 'error' | 'quota_exceeded' | 'pending'
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False, index=True)

    user = db.relationship("User")


def _start_of_day_utc():
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def count_usage_today(user_id: int, api_name: str) -> int:
    """So luot da dung hom nay (theo gio UTC) — tinh ca 'success', 'error' va 'pending':
    'pending' la luot dang duoc "giu cho" ngay khi request bat dau (truoc khi goi AI xong),
    de nhieu request dong thoi khong the cung luc "lot qua" kiem tra hen muc truoc khi bat
    ky request nao kip ghi nhan (xem _reserve_usage_slot o routes/aiho.py). Khong tinh
    'quota_exceeded' vi do chi la ban ghi bi chan, khong phai 1 luot da dung."""
    start_of_day = _start_of_day_utc()
    return UsageLog.query.filter(
        UsageLog.user_id == user_id,
        UsageLog.api_name == api_name,
        UsageLog.status.in_(("success", "error", "pending")),
        UsageLog.created_at >= start_of_day,
    ).count()


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    feature = db.Column(db.String(80), nullable=False)
    rating = db.Column(db.Integer, nullable=True)  # 1-5
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)

    user = db.relationship("User")
