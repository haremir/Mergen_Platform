"""
scripts/reset_db_passwords.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Resets DB credentials in local database to secure randomly generated hashes or removes hardcoded test passwords.
"""
import sys
import os
import secrets

os.environ["FORCE_SQLITE"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///./mergen_local.db"

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (_ROOT, os.path.join(_ROOT, "shared"), os.path.join(_ROOT, "core"), os.path.join(_ROOT, "packages"), os.path.join(_ROOT, "products")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mergen_core.database import SessionLocal
from mergen_core.db_models import DBTenant, DBAdminUser
from panel.auth import get_password_hash

def reset_passwords():
    db = SessionLocal()
    try:
        # 1. Admin reset
        new_admin_pass = os.getenv("PROD_ADMIN_PASSWORD", secrets.token_urlsafe(16))
        admin = db.query(DBAdminUser).filter(DBAdminUser.email == "admin@mergen.com").first()
        if admin:
            admin.hashed_password = get_password_hash(new_admin_pass)
            db.commit()
            print(f"[OK] Reset admin@mergen.com password hash in mergen_local.db (Length: {len(new_admin_pass)})")

        # 2. Pilot tenant reset
        new_tenant_pass = os.getenv("PROD_TENANT_PASSWORD", secrets.token_urlsafe(16))
        tenant = db.query(DBTenant).filter(DBTenant.id == "pilot-dental-clinic-01").first()
        if tenant:
            tenant.hashed_password = get_password_hash(new_tenant_pass)
            db.commit()
            print(f"[OK] Reset pilot-dental-clinic-01 password hash in mergen_local.db (Length: {len(new_tenant_pass)})")

    finally:
        db.close()

if __name__ == "__main__":
    reset_passwords()
