"""
mergen_core.database
~~~~~~~~~~~~~~~~~~~~

Async PostgreSQL bağlantısı — SQLAlchemy 2.x + asyncpg.

DATABASE_URL ortam değişkeni postgresql+asyncpg:// şemasıyla verilmelidir.
Örnek:
    postgresql+asyncpg://mergen:mergen_secret@localhost:5432/mergen_db

Sync SessionLocal yalnızca Alembic env.py ve panel/api_server.py'daki
legacy sync endpoint'leri için korunmuştur. Yeni kod async_session_factory
kullanmalıdır.

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


# ---------------------------------------------------------------------------
# URL — .env dosyasından veya os.environ'dan oku
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

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://mergen:mergen_secret@127.0.0.1:5433/mergen_db",
)

# Alembic ve sync context için sync URL türet (asyncpg → psycopg2)
_SYNC_DATABASE_URL: str = DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)


# ---------------------------------------------------------------------------
# Declarative Base — tüm ORM modelleri bu Base'den türer.
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Async engine — uygulama runtime'ı için
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Sync engine — Alembic migration ve legacy sync endpoint'leri için
# ---------------------------------------------------------------------------

engine = create_engine(
    _SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)
