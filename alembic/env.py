"""
alembic/env.py
~~~~~~~~~~~~~~

Async-native Alembic environment configuration for Mergen Platform.

Desteklenen migration komutları:
    uv run alembic revision --autogenerate -m "description"
    uv run alembic upgrade head
    uv run alembic downgrade -1
    uv run alembic history

DATABASE_URL ortam değişkeni postgresql+asyncpg:// şemasında olmalıdır.
Örnek:
    DATABASE_URL=postgresql+asyncpg://mergen:mergen_secret@localhost:5432/mergen_db
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# sys.path — monorepo kök dizinindeki paketleri çözümle
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent          # alembic/
_ROOT = _HERE.parent                             # Mergen_Platform/

for _pkg_dir in ("core", "packages", "products", "shared"):
    _path = str(_ROOT / _pkg_dir)
    if _path not in sys.path:
        sys.path.insert(0, _path)

# ---------------------------------------------------------------------------
# Logging — alembic.ini'deki [loggers] bloğunu devreye al
# ---------------------------------------------------------------------------

_alembic_config = context.config
if _alembic_config.config_file_name is not None:
    fileConfig(_alembic_config.config_file_name)

# ---------------------------------------------------------------------------
# Metadata — tüm ORM modellerini Base'e yükle, ardından metadata'yı al
# ---------------------------------------------------------------------------

# Core modeller
import mergen_core.db_models  # noqa: F401, E402  — Base'e core tablolarını tanıt

# Kâtip modelleri
try:
    import mergen_product_katip.models  # noqa: F401, E402
except ImportError:
    pass  # Kâtip paketi opsiyonel; kurulu değilse katip_* tabloları migration'a girmez

from mergen_core.database import Base  # noqa: E402

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# DATABASE_URL — .env / ortam değişkeninden oku, varsayılan yok
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.environ["DATABASE_URL"]


# ---------------------------------------------------------------------------
# Offline migration — gerçek DB bağlantısı olmadan SQL script üretir
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """
    'Offline' modda migration: alembic SQL script üretir, DB'ye bağlanmaz.
    Üretilen SQL daha sonra DBA tarafından elle uygulanabilir.
    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # pgvector tipi için compare_type etkin
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migration — async engine üzerinden gerçek DB'ye uygular
# ---------------------------------------------------------------------------

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        # pgvector eklentisini migration öncesi garantile
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        context.run_migrations()


async def run_async_migrations() -> None:
    """Async engine oluştur, sync bağlantıya köprüle, migration'ı çalıştır."""
    connectable = create_async_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,  # migration sırasında connection pooling istemiyoruz
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Giriş noktası
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
