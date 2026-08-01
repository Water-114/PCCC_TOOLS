"""Test cho app/config.py — Batch 2: SQLALCHEMY_ENGINE_OPTIONS phải khác nhau
giữa SQLite (dev/test) và PostgreSQL (staging/production), vì pool_size/
max_overflow chỉ hợp lệ với QueuePool (Postgres) — truyền nhầm cho SQLite sẽ lỗi."""

from app.config import _build_engine_options


def test_engine_options_for_sqlite_has_no_pool_size():
    options = _build_engine_options("sqlite:///app.db")
    assert options == {"pool_pre_ping": True, "connect_args": {"timeout": 30}}


def test_engine_options_for_postgres_has_pool_settings():
    options = _build_engine_options("postgresql://user:pass@host/db")
    assert options["pool_pre_ping"] is True
    assert options["pool_size"] == 5
    assert options["max_overflow"] == 10
    assert options["pool_recycle"] == 280
