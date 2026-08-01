"""Test race condition cho ho_so_session.open_session() (Batch 5A sub-bước 2,
thay cho _reserve_usage_slot cũ ở Batch 1/backend/app/routes/aiho.py đã bị gỡ
khi đổi sang mô hình Bộ hồ sơ) — gọi hàm mở phiên nguyên tử từ nhiều luồng
cùng lúc, xác nhận CHỈ 1 phiên 'open' duy nhất được tạo và CHỈ trừ đúng 1 Bộ
hồ sơ, dù nhiều request "đua" nhau gần như đồng thời (double-click/2 tab).

Lưu ý trung thực: đây là bài test tốt nhất có thể làm mà không cần đổi sang
Postgres + SERIALIZABLE + retry (để dành sau) — dùng SQLite file thật (không
phải in-memory, để nhiều luồng cùng thấy 1 database) và khoá ghi mặc định của
SQLite (BEGIN IMMEDIATE, bật toàn app từ Batch 1) ở cấp file làm lớp bảo vệ chính.

QUAN TRỌNG về cách viết test này: Flask-SQLAlchemy 3.x scope session theo
id(app_context) (mặc định "scopefunc" — xem SQLAlchemy._make_scoped_session).
Nếu tạo/huỷ nhiều app context dồn dập ở nhiều luồng mà KHÔNG giữ tham chiếu
sống, Python có thể tái sử dụng cùng 1 địa chỉ bộ nhớ cho 2 app context KHÁC
NHAU ở 2 luồng khác nhau (id() trùng do garbage-collect) — khiến 2 luồng vô
tình dùng chung 1 scoped session, gây lỗi ngẫu nhiên "DetachedInstanceError"/
"database is locked". Đã xác nhận bằng thực nghiệm: cùng đoạn code, không giữ
tham chiếu app context thì lỗi ngẫu nhiên (~1/5 lần chạy); giữ tham chiếu
(_keep_alive) thì sạch 10/10 lần chạy thử. Vì vậy MỌI test dưới đây đều giữ
tham chiếu app context còn sống suốt vòng đời thread trong list `_keep_alive`.
"""

import os
import sys
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models import HoSoSession, User
from app.services import credits, ho_so_session


def test_concurrent_session_open_never_creates_duplicate_or_overdeducts(tmp_path):
    db_path = tmp_path / "session_open_concurrency_test.db"
    application = create_app(config_overrides={
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "TESTING": True,
        "SECRET_KEY": "test-secret",
    })
    with application.app_context():
        db.create_all()
        user = User(email="concur@pccc.local", role="user")
        user.set_password("matkhau123")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        credits.grant_credits(user_id, 5, credits.CREDIT_REASON_EMAIL_VERIFICATION, note="test")

    attempts = 20
    results = []
    results_lock = threading.Lock()
    _keep_alive = []  # xem docstring dau file - chan id(app_context) bi tai su dung giua cac thread

    def attempt():
        ctx = application.app_context()
        _keep_alive.append(ctx)
        with ctx:
            session = ho_so_session.open_session(user_id)
            session_id = session.id
            with results_lock:
                results.append(session_id)

    threads = [threading.Thread(target=attempt) for _ in range(attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == attempts
    # 20 request "dua" nhau nhung phai cung tra ve DUY NHAT 1 session_id - khong
    # duoc tao nhieu phien 'open' song song cho cung 1 user (double-click/2 tab).
    assert len(set(results)) == 1, (
        f"Ky vong ca {attempts} lan goi dong thoi tra ve cung 1 session_id, "
        f"nhung thuc te co {len(set(results))} session_id khac nhau — race condition."
    )

    with application.app_context():
        open_sessions = HoSoSession.query.filter_by(user_id=user_id, status="open").count()
        assert open_sessions == 1
        # Chi tru DUNG 1 Bo ho so (khong phai 20 lan) du 20 request dong thoi.
        assert credits.credit_balance(user_id) == 4


def test_concurrent_session_open_when_zero_balance_never_grants_any(tmp_path):
    db_path = tmp_path / "session_open_concurrency_zero_balance_test.db"
    application = create_app(config_overrides={
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "TESTING": True,
        "SECRET_KEY": "test-secret-2",
    })
    with application.app_context():
        db.create_all()
        user = User(email="concur0@pccc.local", role="user")
        user.set_password("matkhau123")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        # Khong cap Bo ho so nao - so du = 0.

    attempts = 10
    results = []
    results_lock = threading.Lock()
    _keep_alive = []

    def attempt():
        ctx = application.app_context()
        _keep_alive.append(ctx)
        with ctx:
            try:
                ho_so_session.open_session(user_id)
                granted = True
            except ho_so_session.InsufficientCredits:
                granted = False
            with results_lock:
                results.append(granted)

    threads = [threading.Thread(target=attempt) for _ in range(attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not any(results), "Khong duoc mo bat ky phien nao khi so du Bo ho so la 0."
    with application.app_context():
        assert credits.credit_balance(user_id) == 0
        assert HoSoSession.query.filter_by(user_id=user_id).count() == 0
