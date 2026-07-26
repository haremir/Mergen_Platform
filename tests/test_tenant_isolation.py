"""
tests/test_tenant_isolation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Multi-tenant veri izolasyonu ve JWT kimlik doğrulama testleri.

Test senaryoları:
1. Header tabanlı (X-Tenant-ID) isteklerin 401 ile reddedilmesi.
2. Tenant A'nın kendi projelerine erişebilmesi.
3. Tenant A'nın Tenant B'ye ait bir taslağa/projeye erişmeye çalıştığında 404/403 alması (izolasyon).
4. Admin JWT ile admin endpoint'lerine erişilebilmesi.

Author: Mergen Platform -- QA Team
"""

import sys
import os

# Force SQLite for unit tests
os.environ["FORCE_SQLITE"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///./mergen_local.db"

import pytest
from fastapi.testclient import TestClient

# Ensure root paths are on sys.path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (_ROOT, os.path.join(_ROOT, "shared"), os.path.join(_ROOT, "core"), os.path.join(_ROOT, "packages"), os.path.join(_ROOT, "products")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from panel.api_server import app
from panel.auth import create_access_token, get_password_hash
from mergen_core.database import SessionLocal
from mergen_core.db_models import DBTenant, DBAdminUser
from mergen_product_katip.models import KatipBrandGuide, KatipDraft, KatipTopicQueue, KatipDraftVersion

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_tenants_and_data():
    """Test için 2 farklı tenant ve 1 admin oluşturur."""
    db = SessionLocal()
    try:
        # Cleanup
        db.query(KatipDraftVersion).delete()
        db.query(KatipDraft).delete()
        db.query(KatipTopicQueue).delete()
        db.query(KatipBrandGuide).delete()
        db.query(DBTenant).filter(DBTenant.id.in_(["test_tenant_a", "test_tenant_b"])).delete()
        db.query(DBAdminUser).filter(DBAdminUser.email == "admin_test@mergen.com").delete()
        db.commit()

        # Create Tenant A
        t_a = DBTenant(
            id="test_tenant_a",
            business_name="Tenant A Corp",
            email="tenant_a@test.com",
            hashed_password=get_password_hash("Secret123!"),
            sector="dental_clinic",
            plan="agency",
            enabled_products=["katip"],
        )
        db.add(t_a)

        # Create Tenant B
        t_b = DBTenant(
            id="test_tenant_b",
            business_name="Tenant B Corp",
            email="tenant_b@test.com",
            hashed_password=get_password_hash("Secret123!"),
            sector="real_estate",
            plan="starter",
            enabled_products=["katip"],
        )
        db.add(t_b)

        # Create Super Admin
        admin = DBAdminUser(
            id="test_admin_id",
            email="admin_test@mergen.com",
            hashed_password=get_password_hash("AdminSecret123!"),
        )
        db.add(admin)
        db.commit()

        # Create BrandGuide & Draft for Tenant A
        bg_a = KatipBrandGuide(
            id="bg_a_id",
            tenant_id="test_tenant_a",
            brand_name="Tenant A Brand",
            sector="dental_clinic",
        )
        db.add(bg_a)

        topic_a = KatipTopicQueue(
            id="topic_a_id",
            tenant_id="test_tenant_a",
            brand_guide_id="bg_a_id",
            topic_title="Implant Tedavisi Rehberi",
            status="done",
        )
        db.add(topic_a)

        draft_a = KatipDraft(
            id="draft_a_id",
            tenant_id="test_tenant_a",
            brand_guide_id="bg_a_id",
            topic_id="topic_a_id",
            status="draft",
        )
        db.add(draft_a)
        db.commit()

        yield {
            "tenant_a_token": create_access_token("test_tenant_a", role="tenant"),
            "tenant_b_token": create_access_token("test_tenant_b", role="tenant"),
            "admin_token": create_access_token("test_admin_id", role="super_admin"),
        }
    finally:
        db.close()


def test_x_tenant_id_header_rejected(setup_tenants_and_data):
    """X-Tenant-ID header'ı tek başına gönderildiğinde 401 fırlatılmalı."""
    res = client.get("/api/katip/projects", headers={"X-Tenant-ID": "test_tenant_a"})
    assert res.status_code == 401, f"Beklenen 401, alınan: {res.status_code}"


def test_tenant_a_can_access_own_projects(setup_tenants_and_data):
    """Tenant A kendi projelerini listeleyebilmeli."""
    token = setup_tenants_and_data["tenant_a_token"]
    res = client.get("/api/katip/projects", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == "test_tenant_a"
    assert data["total"] >= 1
    assert any(p["id"] == "bg_a_id" for p in data["items"])


def test_tenant_b_cannot_access_tenant_a_draft(setup_tenants_and_data):
    """Tenant B, Tenant A'ya ait draft_a_id'ye erişmeye çalıştığında 404 almalı."""
    token_b = setup_tenants_and_data["tenant_b_token"]
    res = client.get("/api/katip/drafts/draft_a_id", headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 404, f"Tenant B başkasının taslağını görmemeli! Status: {res.status_code}"


def test_super_admin_can_access_admin_endpoints(setup_tenants_and_data):
    """Super admin /api/admin/tenants/{tenant_id}/drafts üzerinden Tenant A'nın taslağını görebilmeli."""
    admin_token = setup_tenants_and_data["admin_token"]
    res = client.get(
        "/api/admin/tenants/test_tenant_a/drafts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == "test_tenant_a"
    assert any(d["draft_id"] == "draft_a_id" for d in data["items"])


def test_super_admin_forbidden_on_tenant_routes(setup_tenants_and_data):
    """Super admin JWT'si ile yalnızca tenant'lara özel route'a (/api/katip/projects) erişildiğinde 403 verilmeli."""
    admin_token = setup_tenants_and_data["admin_token"]
    res = client.get("/api/katip/projects", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 403
