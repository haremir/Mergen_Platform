"""
scripts/set_dev_passwords.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sets clean development passwords for manual testing:
- Super Admin: admin@mergen.com / Admin123!
- Pilot Tenant: ajans@dental.com / Ajans123!
"""
import sys
import os

os.environ["FORCE_SQLITE"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///./mergen_local.db"

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (_ROOT, os.path.join(_ROOT, "shared"), os.path.join(_ROOT, "core"), os.path.join(_ROOT, "packages"), os.path.join(_ROOT, "products")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mergen_core.database import SessionLocal, Base, engine
from mergen_core.db_models import DBTenant, DBAdminUser
from panel.auth import get_password_hash

def set_dev_passwords():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Admin
        admin = db.query(DBAdminUser).filter(DBAdminUser.email == "admin@mergen.com").first()
        if not admin:
            admin = DBAdminUser(
                id="admin_main_id",
                email="admin@mergen.com",
                hashed_password=get_password_hash("Admin123!"),
            )
            db.add(admin)
        else:
            admin.hashed_password = get_password_hash("Admin123!")

        # Pilot Tenant
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
        else:
            tenant.email = "ajans@dental.com"
            tenant.hashed_password = get_password_hash("Ajans123!")
            tenant.enabled_products = ["katip"]

        db.commit()
        print("[OK] Development passwords configured successfully!")
        print("     1. Super Admin:  admin@mergen.com / Admin123!")
        print("     2. Pilot Tenant: ajans@dental.com / Ajans123!")
    finally:
        db.close()

if __name__ == "__main__":
    set_dev_passwords()
