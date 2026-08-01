"""Fixture dùng chung cho toàn bộ test — Batch 0 (baseline) + Batch 1 (security/validation).

Database test hoàn toàn tách biệt: SQLite in-memory, không đụng backend/app.db
thật. Không gọi API AI trả phí ở bất kỳ test nào trong bộ này.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app import create_app
from app.extensions import db, limiter


@pytest.fixture
def app():
    application = create_app(config_overrides={
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "TESTING": True,
        "SECRET_KEY": "test-secret-batch0",
        # Flask mặc định "propagate" exception thô ra ngoài test process khi TESTING=True,
        # thay vì trả về response 500 thật như server production — tắt hẳn để các test
        # "ghi nhận lỗi 500 đã biết" (test_water.py/test_tham_dinh.py) thấy đúng status_code
        # 500 như người dùng thật sẽ thấy, thay vì làm pytest tự sập vì exception chưa bắt.
        "PROPAGATE_EXCEPTIONS": False,
    })
    with application.app_context():
        db.create_all()
        # limiter dùng storage in-memory CHUNG cho ca qua trinh pytest (Limiter la
        # singleton o extensions.py, khong tao lai theo tung app) - reset truoc moi
        # test de tranh 1 test bi tinh nham luot rate-limit tu test truoc do (cung
        # 1 dia chi IP gia lap "127.0.0.1" cua test client).
        limiter.reset()
        yield application
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()
