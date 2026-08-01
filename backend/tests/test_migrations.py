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
from flask_migrate import downgrade, upgrade

BATCH_5A_TABLES = {"credit_ledger", "email_verification_token", "topup_request"}


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

        # Batch 2: composite index cho truy van quota (count_usage_today)
        usage_log_indexes = {idx["name"] for idx in inspector.get_indexes("usage_log")}
        assert "ix_usage_log_user_api_created" in usage_log_indexes

        # Batch 5A: xac thuc email + ledger Bo ho so + yeu cau nap tien
        assert BATCH_5A_TABLES.issubset(tables)
        assert "email_verified_at" in user_columns


def test_batch_5a_migration_downgrades_and_reupgrades_cleanly(tmp_path):
    """Yeu cau rieng cua Batch 5A sub-buoc 1: chay thu upgrade/downgrade tren
    SQLite local giong cach da lam o Batch 2 (xem test_migrations_upgrade_
    cleanly_on_empty_database o tren, von chi kiem tra upgrade)."""
    db_path = tmp_path / "batch5a_migration_roundtrip_test.db"
    application = create_app(config_overrides={
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "TESTING": True,
        "SECRET_KEY": "test-secret-batch5a",
    })
    with application.app_context():
        upgrade()
        inspector = inspect(db.engine)
        assert BATCH_5A_TABLES.issubset(set(inspector.get_table_names()))

        downgrade(revision="7269076b80f2")  # 1 buoc truoc migration Batch 5A
        inspector = inspect(db.engine)
        tables_after_downgrade = set(inspector.get_table_names())
        assert not BATCH_5A_TABLES & tables_after_downgrade
        user_columns = {col["name"] for col in inspector.get_columns("users")}
        assert "email_verified_at" not in user_columns

        upgrade()
        inspector = inspect(db.engine)
        assert BATCH_5A_TABLES.issubset(set(inspector.get_table_names()))
        user_columns = {col["name"] for col in inspector.get_columns("users")}
        assert "email_verified_at" in user_columns
