"""Phiên "Bộ hồ sơ" (Batch 5A, sub-bước 2) — gộp nhiều lần gọi AI đọc bản vẽ
(nhiều hạng mục của CÙNG 1 công trình) vào đúng 1 lượt trừ Bộ hồ sơ.

Tái dùng đúng ý tưởng "giữ chỗ nguyên tử" đã có ở Batch 1 (_reserve_usage_slot/
_finalize_usage trên UsageLog) nhưng áp ở CẤP PHIÊN thay vì cấp từng lần gọi
AI: mở phiên = kiểm tra + trừ ngay 1 Bộ hồ sơ (ghi CreditLedger delta=-1) trong
cùng 1 transaction với việc tạo HoSoSession — không có khái niệm "giữ chỗ" tách
biệt khỏi ledger. Đóng phiên: giữ nguyên nếu có ≥1 lần gọi AI thành công trong
phiên, hoàn lại (+1) nếu không có lần nào thành công.

Race giữa nhiều request đồng thời (double-click, 2 tab) được thu hẹp bằng
"BEGIN IMMEDIATE" trên SQLite (đã bật toàn app từ Batch 1, xem app/__init__.py)
— CHƯA phải khoá SERIALIZABLE tuyệt đối cho Postgres (để dành khi cần, đúng
mức độ bảo vệ mà _reserve_usage_slot gốc cũng chỉ đạt tới, không siết chặt hơn
ở đây để giữ nhất quán).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import update as sa_update

from ..extensions import db
from ..models import HoSoSession
from . import credits

SESSION_TIMEOUT_MINUTES = 60
MAX_FILES_PER_SESSION = 5
MAX_FORMS_PER_SESSION = 7


class HoSoSessionError(Exception):
    pass


class InsufficientCredits(HoSoSessionError):
    pass


class SessionNotFound(HoSoSessionError):
    pass


class SessionNotOpen(HoSoSessionError):
    pass


class SessionCapExceeded(HoSoSessionError):
    pass


def _utcnow():
    return datetime.now(timezone.utc)


def _as_aware_utc(dt):
    # Cung 1 ly do nhu email_verification.py: SQLite khong giu duoc tzinfo qua
    # DateTime(timezone=True), doc lai la naive - coi la UTC truoc khi so sanh.
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _is_stale(session: HoSoSession) -> bool:
    return _as_aware_utc(session.opened_at) < _utcnow() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)


def _finalize(session: HoSoSession) -> None:
    """Dong 1 phien dang 'open' (chua commit) - dung khi user chu dong dong hoac
    khi phat hien phien cu bi bo quen (lazy timeout) luc mo phien moi."""
    if session.success_count > 0:
        session.status = "closed_used"
    else:
        session.status = "closed_refunded"
        db.session.add(credits.build_ledger_entry(
            session.user_id, 1, credits.CREDIT_REASON_REFUND_TECHNICAL_ERROR,
            note=f"Hoàn Bộ hồ sơ — phiên #{session.id} không có lần đọc bản vẽ nào thành công",
        ))
    session.closed_at = _utcnow()


def open_session(user_id: int) -> HoSoSession:
    """Mo 1 phien moi, tru ngay 1 Bo ho so. Neu user dang co san 1 phien 'open'
    CHUA het han: tra ve chinh phien do (idempotent - double-click/2 tab khong
    tao phien moi/khong tru them). Neu phien cu da qua han (SESSION_TIMEOUT_MINUTES,
    bi bo quen do crash/mat mang): tu dong dong no truoc (dung/hoan tuy
    success_count) roi moi mo phien moi. Raise InsufficientCredits neu het Bo ho so."""
    existing = HoSoSession.query.filter_by(user_id=user_id, status="open").first()
    if existing is not None:
        if not _is_stale(existing):
            return existing
        _finalize(existing)
        db.session.commit()

    balance = credits.credit_balance(user_id)
    if balance < 1:
        raise InsufficientCredits(f"Đã dùng hết Bộ hồ sơ — số dư hiện tại: {balance}.")

    ledger_entry = credits.build_ledger_entry(
        user_id, -1, credits.CREDIT_REASON_USAGE_DEDUCTION, note="Mở phiên Bộ hồ sơ",
    )
    db.session.add(ledger_entry)
    db.session.flush()  # can ledger_entry.id truoc khi gan vao session moi

    session = HoSoSession(user_id=user_id, status="open", ledger_entry_id=ledger_entry.id)
    db.session.add(session)
    db.session.commit()
    return session


def get_open_session_for_user(user_id: int, session_id: int) -> HoSoSession:
    """Dung o dau moi lan goi 1 hang muc AI - xac nhan session_id thuoc dung user
    va dang 'open'. Neu phien vua het han (qua SESSION_TIMEOUT_MINUTES): tu dong
    dong no (lazy) roi bao loi ro rang, khong am tham xu ly tiep."""
    session = HoSoSession.query.get(session_id)
    if session is None or session.user_id != user_id:
        raise SessionNotFound("Không tìm thấy phiên Bộ hồ sơ — vui lòng bắt đầu phân tích lại.")
    if session.status != "open":
        raise SessionNotOpen("Phiên Bộ hồ sơ này đã đóng — vui lòng bắt đầu phân tích lại.")
    if _is_stale(session):
        _finalize(session)
        db.session.commit()
        raise SessionNotOpen("Phiên Bộ hồ sơ đã hết hạn (quá 60 phút) — vui lòng bắt đầu phân tích lại.")
    return session


def reserve_slot(session: HoSoSession, files_delta: int, forms_delta: int) -> None:
    """Kiem tra + tang files_used/forms_used TRUOC khi goi AI - chan ngay neu vuot
    gioi han 5 file/7 form (khong ton 1 lan goi AI cho yeu cau chac chan bi tu
    choi). KHONG hoan lai file/form da tang neu AI sau do loi ky thuat (khac voi
    hoan Bo ho so o cap phien) - giu don gian, dung UI hien tai khong co duong
    nao "thu lai dung hang muc trong cung 1 phien" sau khi loi.

    NGUYEN TU O TANG SQL — KHONG doc-roi-ghi: truoc day ham nay doc
    session.files_used vao bien Python, cong, roi commit — neu 2+ hang muc
    trong CUNG 1 phien chay dong thoi (vd nut "Dung 1 file cho nhieu hang muc"),
    moi request co the doc trung 1 gia tri CU truoc khi request kia kip commit,
    khien request sau GHI DE mat phan tang cua request truoc (lost update) —
    dem thieu files_used/forms_used, co the cho vuot han muc that.
    Ban sua: dieu kien "khong vuot han muc" nam NGAY TRONG WHERE cua 1 cau
    UPDATE DUY NHAT, so sanh voi gia tri COT hien tai trong DB (khong phai bien
    Python `session` co the da cu) — Postgres (production) tu khoa dong ay o
    muc row-level cho moi UPDATE nhu vay, cac request dong thoi tu xep hang o
    tang SQL thay vi tranh chap tren du lieu Python da doc truoc do. rowcount==0
    nghia la KHONG co dong nao khop dieu kien (da vuot gioi han tai thoi diem
    THUC THI) — refresh() lai `session` de doc dung gia tri that tu DB truoc khi
    quyet dinh thong bao loi nao (chi de CHON DUNG THONG BAO, khong anh huong
    toi quyet dinh chan/cho — quyet dinh that da nam trong cau UPDATE o tren).
    """
    stmt = (
        sa_update(HoSoSession)
        .where(
            HoSoSession.id == session.id,
            HoSoSession.files_used + files_delta <= MAX_FILES_PER_SESSION,
            HoSoSession.forms_used + forms_delta <= MAX_FORMS_PER_SESSION,
        )
        .values(
            files_used=HoSoSession.files_used + files_delta,
            forms_used=HoSoSession.forms_used + forms_delta,
        )
    )
    result = db.session.execute(stmt)
    db.session.commit()

    if result.rowcount == 0:
        db.session.refresh(session)
        if session.files_used + files_delta > MAX_FILES_PER_SESSION:
            raise SessionCapExceeded(f"Vượt quá giới hạn {MAX_FILES_PER_SESSION} file bản vẽ/Bộ hồ sơ.")
        if session.forms_used + forms_delta > MAX_FORMS_PER_SESSION:
            raise SessionCapExceeded(f"Vượt quá giới hạn {MAX_FORMS_PER_SESSION} form MĐC/Bộ hồ sơ.")
        raise SessionCapExceeded(
            f"Vượt quá giới hạn {MAX_FILES_PER_SESSION} file bản vẽ hoặc {MAX_FORMS_PER_SESSION} form MĐC/Bộ hồ sơ."
        )

    db.session.refresh(session)


def mark_success(session: HoSoSession) -> None:
    session.success_count += 1
    db.session.commit()


def close_session(user_id: int, session_id: int) -> HoSoSession:
    """Dong 1 phien - idempotent (goi lai voi phien da dong truoc do khong loi,
    tra ve nguyen trang thai hien tai) vi client co the goi close 2 lan (vd retry
    mang)."""
    session = HoSoSession.query.get(session_id)
    if session is None or session.user_id != user_id:
        raise SessionNotFound("Không tìm thấy phiên Bộ hồ sơ.")
    if session.status != "open":
        return session
    _finalize(session)
    db.session.commit()
    return session
