"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from objects.env import Env

env = Env()

# Database connection
DB_USER = env.req("DB_USER")
DB_PASS = env.req("DB_PASS")
DB_HOST = env.req("DB_HOST")
DB_PORT = env.req("DB_PORT")
DB_NAME = env.req("DB_NAME")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
