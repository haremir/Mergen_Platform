"""
mergen_core.database
~~~~~~~~~~~~~~~~~~~~

Pure PostgreSQL database engine module — SQLAlchemy 2.x + asyncpg (async) / psycopg2 (sync).

DATABASE_URL environment variable must use postgresql+asyncpg:// schema.
Example:
    postgresql+asyncpg://postgres:postgres@localhost:5432/mergen_db

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ---------------------------------------------------------------------------
# URL — Read from environment or .env file
# ---------------------------------------------------------------------------
if "DATABASE_URL" not in os.environ:
    _env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if os.path.exists(_env_path):
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line.startswith("DATABASE_URL="):
                    os.environ["DATABASE_URL"] = _line.split("=", 1)[1].strip()
                    break

raw_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/mergen_db",
)

# Normalize raw_url to asyncpg schema for async_engine
if raw_url.startswith("postgresql://"):
    DATABASE_URL: str = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif raw_url.startswith("postgresql+psycopg2://"):
    DATABASE_URL: str = raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
else:
    DATABASE_URL: str = raw_url

# Derived sync URL for psycopg2 (Alembic & sync Sessions)
_SYNC_DATABASE_URL: str = DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://", 1
)

# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass

# ---------------------------------------------------------------------------
# PostgreSQL Engines & Sessions
# ---------------------------------------------------------------------------
engine = create_engine(
    _SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_factory: sessionmaker[AsyncSession] = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)
