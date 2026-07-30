from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

# Tên dùng chung cho mọi lượt gọi AI đọc bản vẽ (báo cháy, điện PCCC, ...) —
# tất cả cùng tính vào 1 hạn mức "N lượt/ngày" duy nhất, không tách riêng theo hạng mục.
AIHO_API_NAME = "aiho_analysis"


def _utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # 'user' | 'admin'
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def to_public_dict(self) -> dict:
        return {"id": self.id, "email": self.email, "role": self.role}


class UsageLog(db.Model):
    __tablename__ = "usage_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    api_name = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'success' | 'error' | 'quota_exceeded'
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False, index=True)

    user = db.relationship("User")


def count_usage_today(user_id: int, api_name: str) -> int:
    """So luot da dung hom nay (theo gio UTC) — tinh ca 'success' lan 'error', vi ca hai deu la
    1 lan da thuc su goi toi AI provider (khong tinh 'quota_exceeded', vi do chi la ban ghi bi chan)."""
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return UsageLog.query.filter(
        UsageLog.user_id == user_id,
        UsageLog.api_name == api_name,
        UsageLog.status.in_(("success", "error")),
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
