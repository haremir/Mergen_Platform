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
