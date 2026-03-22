"""Tests for common.helpers.postgres_engine."""

from common.helpers.env import Env
from common.helpers.postgres_engine import build_postgres_url_from_env


def test_build_postgres_url_from_env_format(monkeypatch) -> None:
    """build_postgres_url_from_env produces the expected driver URL."""
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASS", "secret")
    monkeypatch.setenv("DB_HOST", "db.example.com")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "appdb")
    env = Env()
    url = build_postgres_url_from_env(env)
    assert url == (
        "postgresql+psycopg2://user:secret@db.example.com:5432/appdb"
    )
