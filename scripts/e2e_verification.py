"""
scripts/e2e_verification.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
End-to-End verification script for Mergen Platform:
1. Dynamically generates or reads test credentials from environment.
2. Idempotent execution (handles pre-existing admin & tenant records gracefully).
3. Verifies full lifecycle: Admin Auth -> Tenant Password Provisioning -> Tenant Auth -> Projects -> Topics -> One-Click Generation -> Drafts -> Feedback -> Admin Tenant Inspection.
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

from fastapi.testclient import TestClient
from panel.api_server import app
from mergen_core.database import SessionLocal, Base, engine
from mergen_core.db_models import DBTenant, DBAdminUser
from mergen_product_katip.models import KatipTopicQueue, KatipDraft
from panel.auth import get_password_hash

client = TestClient(app)


def run_e2e_test():
    print("=== STARTING E2E IDEMPOTENT VERIFICATION ===")

    # Generate dynamic ephemeral credentials per run unless set in env
    admin_email = os.getenv("E2E_ADMIN_EMAIL", "admin@mergen.com")
    admin_password = os.getenv("E2E_ADMIN_PASSWORD", f"Adm_{secrets.token_urlsafe(12)}")

    tenant_id = os.getenv("E2E_TENANT_ID", "pilot-dental-clinic-01")
    tenant_email = os.getenv("E2E_TENANT_EMAIL", "ajans@dental.com")
    tenant_password = os.getenv("E2E_TENANT_PASSWORD", f"Tnt_{secrets.token_urlsafe(12)}")

    # 1. Setup DB Idempotently
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed or Update Super Admin
        admin = db.query(DBAdminUser).filter(DBAdminUser.email == admin_email).first()
        if not admin:
            admin = DBAdminUser(
                id=f"admin_{secrets.token_hex(4)}",
                email=admin_email,
                hashed_password=get_password_hash(admin_password),
            )
            db.add(admin)
            db.commit()
            print(f"[OK] Created new Super Admin: {admin_email}")
        else:
            admin.hashed_password = get_password_hash(admin_password)
            db.commit()
            print(f"[OK] Updated existing Super Admin credentials: {admin_email}")

        # Seed or Update Pilot Tenant
        tenant = db.query(DBTenant).filter(DBTenant.id == tenant_id).first()
        if not tenant:
            tenant = DBTenant(
                id=tenant_id,
                business_name="DentSmile Klinik",
                email=tenant_email,
                hashed_password=get_password_hash(tenant_password),
                sector="dental_clinic",
                plan="agency",
                enabled_products=["katip"],
            )
            db.add(tenant)
            db.commit()
            print(f"[OK] Created new Pilot Tenant: {tenant_id}")
        else:
            tenant.email = tenant_email
            tenant.hashed_password = get_password_hash(tenant_password)
            tenant.enabled_products = ["katip"]
            db.commit()
            print(f"[OK] Updated existing Pilot Tenant: {tenant_id}")

    finally:
        db.close()

    # 2. Test Admin Login
    res = client.post("/api/auth/login", json={"email": admin_email, "password": admin_password})
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    admin_token = res.json()["access_token"]
    print("[OK] Super Admin Login HTTP 200 OK (JWT acquired)")

    # 3. Test Admin Set Tenant Password
    res = client.post(
        f"/api/admin/tenants/{tenant_id}/set-password",
        json={"email": tenant_email, "password": tenant_password},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200, f"Set password failed: {res.text}"
    print("[OK] Admin Set Tenant Password HTTP 200 OK")

    # 4. Test Katip Tenant Login
    res = client.post("/api/auth/login", json={"email": tenant_email, "password": tenant_password})
    assert res.status_code == 200, f"Tenant login failed: {res.text}"
    tenant_token = res.json()["access_token"]
    print("[OK] Katip Tenant Login HTTP 200 OK (JWT acquired)")

    # 5. Test Katip Projects Listing
    res = client.get("/api/katip/projects", headers={"Authorization": f"Bearer {tenant_token}"})
    assert res.status_code == 200
    projects = res.json()["items"]
    assert len(projects) >= 1
    project_id = projects[0]["id"]
    print(f"[OK] Katip Projects Listing HTTP 200 OK (Project ID: {project_id})")

    # 6. Test Katip Topic Creation
    topic_title = f"2026 Dis Implanti Trendleri #{secrets.token_hex(2)}"
    res = client.post(
        "/api/katip/topics",
        json={
          "topic_title": topic_title,
          "brand_guide_id": project_id,
          "target_keywords": ["implant", "dis hekimligi", "zirkonyum"],
          "priority": 8
        },
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert res.status_code == 201
    topic_id = res.json()["topic_id"]
    print(f"[OK] Katip Topic Creation HTTP 201 Created (Topic ID: {topic_id})")

    # 7. Test One-Click Draft Generation
    res = client.post(
        "/api/katip/drafts/generate",
        json={"topic_id": topic_id},
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert res.status_code == 200
    draft_id = res.json()["draft_id"]
    print(f"[OK] Katip One-Click Draft Generation HTTP 200 OK (Draft ID: {draft_id})")

    # 8. Test Draft Detail Fetching
    res = client.get(f"/api/katip/drafts/{draft_id}", headers={"Authorization": f"Bearer {tenant_token}"})
    assert res.status_code == 200
    assert res.json()["draft_id"] == draft_id
    print("[OK] Katip Draft Detail Fetch HTTP 200 OK")

    # 9. Test Feedback Note Submission
    res = client.post(
        f"/api/katip/drafts/{draft_id}/feedback",
        json={"note": "Giris paragrafina implant avantajlarini ozetleyen bir madde ekle.", "author_label": "Klinik Bashekimi"},
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert res.status_code == 201
    print("[OK] Katip Feedback Submission HTTP 201 Created")

    # 10. Test Super Admin Tenant Inspection (Drafts & Details)
    res = client.get(
        f"/api/admin/tenants/{tenant_id}/drafts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    admin_drafts = res.json()["items"]
    assert any(d["draft_id"] == draft_id for d in admin_drafts)
    print("[OK] Super Admin Tenant Inspection HTTP 200 OK (Verified Tenant Isolation Bypass for Super Admin)")

    print("\n=== ALL E2E VERIFICATION STEPS PASSED SUCCESSFULLY ===")


if __name__ == "__main__":
    run_e2e_test()
