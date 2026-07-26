"""
scripts/migrate_postgres.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pure PostgreSQL Migration & Database Provisioning Script:
1. Connects to PostgreSQL server using DATABASE_URL or environment parameters.
2. Creates database 'mergen_db' if it does not exist.
3. Creates all ORM tables (Base.metadata.create_all).
4. Provisions Super Admin (admin@mergen.com / Admin123!) and Pilot Tenant (pilot-dental-clinic-01 / ajans@dental.com / Ajans123!).
"""

import sys
import os
import re

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (_ROOT, os.path.join(_ROOT, "shared"), os.path.join(_ROOT, "core"), os.path.join(_ROOT, "packages"), os.path.join(_ROOT, "products")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mergen_core.database import Base
from mergen_core.db_models import DBTenant, DBAdminUser
from mergen_product_katip.models import KatipBrandGuide, KatipTopicQueue, KatipDraft, KatipDraftVersion, KatipFeedbackNote, KatipRevisionPattern
from panel.auth import get_password_hash


def parse_db_url(url: str):
    # e.g. postgresql+asyncpg://user:pass@host:port/dbname
    m = re.match(r"postgresql(?:\+[^:]+)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)", url)
    if m:
        return {
            "user": m.group(1),
            "password": m.group(2),
            "host": m.group(3),
            "port": int(m.group(4) or 5432),
            "dbname": m.group(5),
        }
    return None


def ensure_postgres_db(host, port, user, password, dbname):
    print(f"Connecting to PostgreSQL server at {host}:{port} as user '{user}'...")
    try:
        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname='postgres')
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(f'CREATE DATABASE "{dbname}"')
            print(f"  + Database '{dbname}' created successfully.")
        else:
            print(f"  + Database '{dbname}' already exists.")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        safe_msg = repr(e)
        print(f"  [ERROR] PostgreSQL server connection failed: {safe_msg}")
        return False


def run_migration():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env"))

    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/mergen_db")
    parsed = parse_db_url(db_url)

    if parsed:
        pg_host = parsed["host"]
        pg_port = parsed["port"]
        pg_user = parsed["user"]
        pg_pass = parsed["password"]
        pg_db = parsed["dbname"]
    else:
        pg_host = os.getenv("PG_HOST", "127.0.0.1")
        pg_port = int(os.getenv("PG_PORT", "5432"))
        pg_user = os.getenv("PG_USER", "postgres")
        pg_pass = os.getenv("PG_PASSWORD", "postgres")
        pg_db = os.getenv("PG_DBNAME", "mergen_db")

    success = ensure_postgres_db(pg_host, pg_port, pg_user, pg_pass, pg_db)
    if not success:
        print("\nCould not connect to PostgreSQL. Please verify PostgreSQL service is running and credentials are valid.")
        return False

    sync_url = f"postgresql+psycopg2://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    print(f"\n--- Initializing PostgreSQL Schema ({sync_url}) ---")
    engine = create_engine(sync_url, pool_pre_ping=True)

    Base.metadata.create_all(bind=engine)
    print("  + Base.metadata.create_all executed successfully.")

    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        # Seed Super Admin
        admin = db.query(DBAdminUser).filter(DBAdminUser.email == "admin@mergen.com").first()
        if not admin:
            admin = DBAdminUser(
                id="admin_main_id",
                email="admin@mergen.com",
                hashed_password=get_password_hash("Admin123!"),
            )
            db.add(admin)
            print("  + Super Admin created: admin@mergen.com / Admin123!")
        else:
            admin.hashed_password = get_password_hash("Admin123!")
            print("  + Super Admin updated: admin@mergen.com / Admin123!")

        # Seed Pilot Tenant
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
            print("  + Pilot Tenant created: pilot-dental-clinic-01 (ajans@dental.com / Ajans123!)")
        else:
            tenant.email = "ajans@dental.com"
            tenant.hashed_password = get_password_hash("Ajans123!")
            tenant.enabled_products = ["katip"]
            print("  + Pilot Tenant updated: pilot-dental-clinic-01 (ajans@dental.com / Ajans123!)")

        # Seed default KatipBrandGuide
        project = db.query(KatipBrandGuide).filter(KatipBrandGuide.tenant_id == "pilot-dental-clinic-01").first()
        if not project:
            project = KatipBrandGuide(
                tenant_id="pilot-dental-clinic-01",
                brand_name="DentSmile Klinik",
                sector="dental_clinic",
                tone_rules=["Profesyonel dil", "Kurumsal yaklaşım"],
                forbidden_words=["genellikle", "galiba"],
                is_default=True,
            )
            db.add(project)
            print("  + Default KatipBrandGuide created for pilot-dental-clinic-01")

        db.commit()
        print("\n[OK] Pure PostgreSQL database schema and initial data provisioned successfully!")
        return True
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
