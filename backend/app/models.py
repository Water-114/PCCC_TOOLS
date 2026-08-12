from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .config import Config
from .extensions import db

# Tên dùng chung cho mọi lượt gọi AI đọc bản vẽ (báo cháy, điện PCCC, ...) —
# tất cả cùng tính vào 1 hạn mức "N lượt/ngày" duy nhất, không tách riêng theo hạng mục.
AIHO_API_NAME = "aiho_analysis"

# Quota riêng cho /api/ai/comment (diễn giải kết quả tính nước — trước đây chỉ
# MVP frontend/ React gọi tới, frontend/ đã bị gỡ khỏi source ở Batch 7A nên
# route hiện không còn caller nào trong source) — tách khỏi AIHO_API_NAME vì
# đây là tính năng khác, không liên quan tới đọc bản vẽ.
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
    # Batch 5A: null nghĩa là CHƯA từng xác thực email — kể cả tài khoản đã đăng
    # ký từ trước Batch 5A (theo hệ thống lượt/ngày cũ). KHÔNG có migration
    # backfill nào set cột này — tài khoản cũ phải tự xác thực lại y như người
    # dùng mới để nhận 1 Bộ hồ sơ, đúng quyết định của owner. Chỉ được set 1 LẦN
    # (xem services/email_verification.py) — lần xác thực lại sau đó (nếu có)
    # không set lại/không cấp thêm Bộ hồ sơ.
    email_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def effective_quota(self) -> int:
        return self.daily_quota if self.daily_quota is not None else Config.AIHO_DAILY_QUOTA

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "email_verified": self.email_verified_at is not None,
        }


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


class EmailVerificationToken(db.Model):
    """Token xác thực email một lần, có hạn sử dụng (Batch 5A). Chỉ lưu HASH của
    token thật (sha256) — không lưu bản rõ vào DB, để lộ DB không đồng nghĩa lộ
    được link xác thực còn hiệu lực của người khác."""

    __tablename__ = "email_verification_token"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)

    user = db.relationship("User")


class CreditLedger(db.Model):
    """Lịch sử đầy đủ các giao dịch "Bộ hồ sơ" (Batch 5A) — số dư hiện tại LUÔN
    tính từ SUM(delta) (xem services/credits.credit_balance), không lưu số dư
    rời rạc ở bảng khác để tránh 2 nguồn dữ liệu lệch nhau. `balance_after` lưu
    kèm mỗi dòng chỉ để hiển thị lịch sử nhanh (không phải nguồn sự thật)."""

    __tablename__ = "credit_ledger"
    __table_args__ = (
        db.Index("ix_credit_ledger_user_created", "user_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    delta = db.Column(db.Integer, nullable=False)  # duong: cap/hoan/nap; am: tru luc dung
    reason = db.Column(db.String(40), nullable=False)  # xem services/credits.py CREDIT_REASON_*
    balance_after = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)

    user = db.relationship("User")


class TopupRequest(db.Model):
    """Yêu cầu nạp thêm Bộ hồ sơ bằng chuyển khoản thủ công (Batch 5A). Sub-bước 1
    chỉ tạo schema; sub-bước 3 dùng thật qua routes/topup.py (tạo yêu cầu, user
    tự xác nhận đã chuyển khoản) và routes/admin.py (admin xác nhận/từ chối).

    State machine 3 trạng thái (sub-bước 3): 'cho_chuyen_khoan' (vừa tạo, user
    chưa xác nhận đã chuyển khoản — CHƯA vào hàng đợi admin) -> 'cho_xac_nhan'
    (user đã bấm "Tôi đã chuyển khoản", admin bắt đầu thấy trong danh sách) ->
    'da_xac_nhan' | 'tu_choi' (admin quyết định, trạng thái cuối cùng)."""

    __tablename__ = "topup_request"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    reference_code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    amount_vnd = db.Column(db.Integer, nullable=False, default=100000)
    credits_to_grant = db.Column(db.Integer, nullable=False, default=2)
    # 'cho_chuyen_khoan' | 'cho_xac_nhan' | 'da_xac_nhan' | 'tu_choi'
    status = db.Column(db.String(20), nullable=False, default="cho_chuyen_khoan")
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)
    # Ten trung lap (khong phai "confirmed_*") vi cot nay dung chung cho CA
    # hanh dong xac nhan LAN tu choi cua admin - xem services/topup.py.
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reviewed_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])
    reviewed_by_admin = db.relationship("User", foreign_keys=[reviewed_by_admin_id])


class HoSoSession(db.Model):
    """1 phiên "Bộ hồ sơ" (Batch 5A, sub-bước 2) — gộp nhiều lần gọi AI đọc bản vẽ
    (nhiều hạng mục của CÙNG 1 công trình) vào đúng 1 lượt trừ Bộ hồ sơ, thay vì
    mỗi lần gọi AI trừ riêng. Mở phiên = trừ ngay 1 Bộ hồ sơ (ghi CreditLedger
    delta=-1); đóng phiên = giữ nguyên nếu có ít nhất 1 lần gọi thành công, hoàn
    lại (+1) nếu toàn bộ đều lỗi kỹ thuật hoặc phiên không dùng gì cả. Xem
    services/ho_so_session.py để biết toàn bộ logic mở/đóng/kiểm tra giới hạn."""

    __tablename__ = "ho_so_session"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="open")  # 'open' | 'closed_used' | 'closed_refunded'
    files_used = db.Column(db.Integer, nullable=False, default=0)
    forms_used = db.Column(db.Integer, nullable=False, default=0)
    success_count = db.Column(db.Integer, nullable=False, default=0)
    ledger_entry_id = db.Column(db.Integer, db.ForeignKey("credit_ledger.id"), nullable=True)
    opened_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User")
    ledger_entry = db.relationship("CreditLedger")


class HoSoSessionQuyMo(db.Model):
    """Dữ liệu "Quy mô" (Form A) của 1 phiên Bộ hồ sơ — 1-1 với HoSoSession,
    lưu tách bảng riêng vì chỉ dùng khi user CÓ đính hạng mục Quy mô (không
    bắt buộc). Tên cột giữ ĐÚNG tên field mà tham_dinh.py/he_thong_bat_buoc.py/
    phuong_tien.py dùng (qua to_dict()) để truyền thẳng vào evaluate_*() không
    cần lớp chuyển đổi tên. source: 'ai' | 'manual'. Xem quy_mo_store.py."""

    __tablename__ = "ho_so_session_quy_mo"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("ho_so_session.id"), nullable=False, unique=True, index=True)
    source = db.Column(db.String(10), nullable=False)  # 'ai' | 'manual'
    occ = db.Column(db.String(30), nullable=True)
    floors = db.Column(db.Integer, nullable=True)
    basements = db.Column(db.Integer, nullable=True)
    semi_basements = db.Column(db.Integer, nullable=True)
    area_floor = db.Column(db.Float, nullable=True)
    total_area = db.Column(db.Float, nullable=True)
    volume = db.Column(db.Float, nullable=True)
    h_fire = db.Column(db.Float, nullable=True)
    kids = db.Column(db.Integer, nullable=True)
    seats = db.Column(db.Integer, nullable=True)
    hazard = db.Column(db.String(1), nullable=True)
    gara_kin = db.Column(db.String(10), nullable=True)
    gara_kc12 = db.Column(db.String(10), nullable=True)
    gara_bcl = db.Column(db.String(10), nullable=True)
    gara_cap_s = db.Column(db.String(10), nullable=True)
    ppl_floor = db.Column(db.Integer, nullable=True)
    ext_level = db.Column(db.String(10), nullable=True)
    hanh_lang_dai_nhat = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    session = db.relationship("HoSoSession")

    def to_dict(self):
        """Trả về dict dùng ĐÚNG tên field của QuyMoFields/evaluate_*() (camelCase),
        KHÔNG phải tên cột snake_case — để pass-through thẳng vào evaluate_*()."""
        return {
            "occ": self.occ,
            "floors": self.floors,
            "basements": self.basements,
            "semiBasements": self.semi_basements,
            "areaFloor": self.area_floor,
            "totalArea": self.total_area,
            "volume": self.volume,
            "hFire": self.h_fire,
            "kids": self.kids,
            "seats": self.seats,
            "hazard": self.hazard,
            "garaKin": self.gara_kin,
            "garaKC12": self.gara_kc12,
            "garaBcl": self.gara_bcl,
            "garaCapS": self.gara_cap_s,
            "pplFloor": self.ppl_floor,
            "extLevel": self.ext_level,
            "hanhLangDaiNhat": self.hanh_lang_dai_nhat,
        }
