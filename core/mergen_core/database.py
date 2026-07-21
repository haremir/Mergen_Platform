"""
mergen_core.database
~~~~~~~~~~~~~~~~~~~~

Database initialization and session management using SQLAlchemy.
Defaults to local SQLite but is fully compatible with PostgreSQL.

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Default to local SQLite for zero-setup development, support override for PG/Supabase
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mergen_local.db")

# SQLite needs check_same_thread=False for async/multithreaded access
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Simple dynamic migration to add persona and telegram_token columns if missing
try:
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE tenants ADD COLUMN persona VARCHAR(100) DEFAULT 'friendly_energetic'"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE tenants ADD COLUMN telegram_token VARCHAR(100) NULL"))
            conn.commit()
        except Exception:
            pass
except Exception:
    pass
