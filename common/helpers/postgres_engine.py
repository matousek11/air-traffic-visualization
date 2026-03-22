"""Shared SQLAlchemy engine creation from DB_ environment variables."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from common.helpers.env import Env


def build_postgres_url_from_env(env: Env) -> str:
    """Build a PostgreSQL connection URL from DB_ keys.

    Args:
        env: Env instance.

    Returns:
        SQLAlchemy URL string using the psycopg2 driver.

    Raises:
        KeyError: When a required DB_ variable is missing.
    """
    user = env.req("DB_USER")
    password = env.req("DB_PASS")
    host = env.req("DB_HOST")
    port = env.req("DB_PORT")
    name = env.req("DB_NAME")
    return (
        f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    )


def create_postgres_engine_from_env() -> Engine:
    """Create an SQLAlchemy engine using DB from the environment.

    Instantiates ``Env`` once, builds the URL, and returns an engine.

    Returns:
        Configured SQLAlchemy ``Engine``.

    Raises:
        KeyError: When a required DB variable is missing.
    """
    env = Env()
    url = build_postgres_url_from_env(env)
    return create_engine(url, pool_pre_ping=True)
