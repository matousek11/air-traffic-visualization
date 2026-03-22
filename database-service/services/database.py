"""Database connection and session management."""

from sqlalchemy.orm import sessionmaker

from common.helpers.postgres_engine import create_postgres_engine_from_env

engine = create_postgres_engine_from_env()
DATABASE_URL = str(engine.url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
