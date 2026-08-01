"""Test race condition cho _reserve_usage_slot (backend/app/routes/aiho.py) —
gọi hàm giữ-chỗ-quota nguyên tử từ nhiều luồng cùng lúc, xác nhận tổng số lượt
được chấp nhận không bao giờ vượt quá hạn mức, kể cả khi nhiều request "đua"
nhau gần như đồng thời.

Lưu ý trung thực: đây là bài test tốt nhất có thể làm mà không cần đổi sang
Postgres + SERIALIZABLE + retry (để dành Batch 2) — dùng SQLite file thật
(không phải in-memory, để nhiều luồng cùng thấy 1 database) và khoá ghi mặc
định của SQLite ở cấp file làm lớp bảo vệ chính.
"""

import os
import sys
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models import User
from app.routes.aiho import _reserve_usage_slot


def test_concurrent_quota_reservation_never_exceeds_limit(tmp_path):
    db_path = tmp_path / "quota_concurrency_test.db"
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

    limit = 5
    attempts = 20
    results = []
    results_lock = threading.Lock()

    def attempt():
        with application.app_context():
            reservation = _reserve_usage_slot(user_id, limit)
            with results_lock:
                results.append(reservation is not None)

    threads = [threading.Thread(target=attempt) for _ in range(attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successful = sum(1 for granted in results if granted)
    assert successful <= limit, (
        f"Cho phep {successful} luot trong khi han muc chi la {limit} "
        f"— race condition van con ton tai."
    )
    assert successful == limit, "Phai co dung du so luot duoc chap nhan khi co du request."
