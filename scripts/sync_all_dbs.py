"""
scripts/sync_all_dbs.py
~~~~~~~~~~~~~~~~~~~~~~~
Synchronizes schemas, migrations, and development credentials across BOTH:
1. Local SQLite (mergen_local.db)
2. PostgreSQL (127.0.0.1:5433/mergen_db if available)

Ensures admin@mergen.com (Admin123!) and ajans@dental.com (Ajans123!) exist in both databases!
"""

import sys
import os

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (_ROOT, os.path.join(_ROOT, "shared"), os.path.join(_ROOT, "core"), os.path.join(_ROOT, "packages"), os.path.join(_ROOT, "products")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from mergen_core.database import Base
from mergen_core.db_models import DBTenant, DBAdminUser
from mergen_product_katip.models import KatipBrandGuide, KatipTopicQueue, KatipDraft, KatipDraftVersion, KatipFeedbackNote, KatipRevisionPattern
from panel.auth import get_password_hash


def sync_db(db_url: str, label: str):
    print(f"\n--- Synchronizing {label} ({db_url}) ---")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    try:
        if "sqlite" in sync_url:
            engine = create_engine(sync_url, connect_args={"check_same_thread": False})
        else:
            engine = create_engine(sync_url, pool_pre_ping=True)

        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        # 1. Admin User
        admin = db.query(DBAdminUser).filter(DBAdminUser.email == "admin@mergen.com").first()
        if not admin:
            admin = DBAdminUser(
                id="admin_main_id",
                email="admin@mergen.com",
                hashed_password=get_password_hash("Admin123!"),
            )
            db.add(admin)
            print(f"  + Created admin@mergen.com in {label}")
        else:
            admin.hashed_password = get_password_hash("Admin123!")
            print(f"  + Updated admin@mergen.com password in {label}")

        # 2. Pilot Tenant
        tenant = db.query(DBTenant).filter(DBTenant.id == "pilot-dental-clinic-01").first()
        if not tenant:
            tenant = DBTenant(
                id="pilot-dental-clinic-01",
                business_name="DentSmile Klinik",
                email="ajans@dental.com",
                hashed_password=get_password_hash("Ajans123!"),
                sector="dental_clinic",
                plan="agency",
                enabled_products=["katip"],
            )
            db.add(tenant)
            print(f"  + Created pilot-dental-clinic-01 in {label}")
        else:
            tenant.email = "ajans@dental.com"
            tenant.hashed_password = get_password_hash("Ajans123!")
            tenant.enabled_products = ["katip"]
            print(f"  + Updated pilot-dental-clinic-01 in {label}")

        db.commit()
        db.close()
        print(f"[OK] {label} synchronized successfully!")

    except Exception as err:
        print(f"[WARN] Failed to connect/sync {label}: {err}")


def main():
    # 1. SQLite
    sqlite_url = "sqlite:///./mergen_local.db"
    sync_db(sqlite_url, "SQLite (mergen_local.db)")

    # 2. PostgreSQL from .env if present
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env"))
    pg_url = os.getenv("DATABASE_URL")
    if pg_url and "postgresql" in pg_url:
        sync_db(pg_url, "PostgreSQL")


if __name__ == "__main__":
    main()
