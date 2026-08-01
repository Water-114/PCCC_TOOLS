"""Kiểm tra thật 2 migration Alembic hiện có chạy được trên 1 database
SQLite trống mới tinh (khác hẳn conftest.py's in-memory app fixture — test
này cần 1 file sqlite thật trên đĩa vì Alembic/Flask-Migrate thao tác qua
đường dẫn file, không dùng chung fixture `app`/`client` của các test khác).
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from flask_migrate import upgrade


def test_migrations_upgrade_cleanly_on_empty_database(tmp_path):
    db_path = tmp_path / "batch0_migration_test.db"
    application = create_app(config_overrides={
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "TESTING": True,
        "SECRET_KEY": "test-secret-batch0",
    })
    with application.app_context():
        upgrade()

        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        assert {"users", "usage_log", "feedback"}.issubset(tables)

        user_columns = {col["name"] for col in inspector.get_columns("users")}
        assert "daily_quota" in user_columns
