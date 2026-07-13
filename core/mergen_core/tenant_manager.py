"""
mergen_core.tenant_manager
~~~~~~~~~~~~~~~~~~~~~~~~~~

Domain-agnostic multi-tenant manager for the Mergen Platform.
SQLAlchemy ORM version with full SQLite and PostgreSQL database support.

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Optional, List

from mergen_core.database import SessionLocal
from mergen_core.db_models import DBTenant

# ---------------------------------------------------------------------------
# Import shared domain models (zero-dependency dataclasses)
# ---------------------------------------------------------------------------
try:
    from mergen_common.models import Tenant
except ModuleNotFoundError:
    _shared = os.path.join(os.path.dirname(__file__), "..", "..", "shared")
    sys.path.insert(0, os.path.abspath(_shared))
    from mergen_common.models import Tenant  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TenantNotFoundError(KeyError):
    """Raised when a tenant lookup returns no result."""


class TenantAlreadyExistsError(ValueError):
    """Raised when trying to create a tenant with a duplicate tenant_id."""


# ---------------------------------------------------------------------------
# TenantManager
# ---------------------------------------------------------------------------

class TenantManager:
    """Multi-tenant CRUD manager backed by SQLAlchemy database session.

    Resolves tenant_id by phone number and manages plan and settings overrides.
    """

    # Subscription plan hierarchy — also defined in plan_guard.py.
    VALID_PLANS = frozenset({"free", "starter", "business", "premium", "enterprise"})

    def __init__(self, db_adapter=None) -> None:
        self._db = db_adapter
        logger.info("TenantManager: initialised with SQLAlchemy ORM database backend.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_tenant(self, tenant: Tenant) -> None:
        """Persist a new Tenant record in the database."""
        if tenant.plan not in self.VALID_PLANS:
            raise ValueError(
                f"TenantManager.create_tenant: unknown plan '{tenant.plan}'. "
                f"Valid plans: {sorted(self.VALID_PLANS)}"
            )

        with SessionLocal() as session:
            existing = session.query(DBTenant).filter(DBTenant.id == tenant.tenant_id).first()
            if existing:
                raise TenantAlreadyExistsError(
                    f"TenantManager.create_tenant: tenant '{tenant.tenant_id}' already exists."
                )

            db_tenant = DBTenant(
                id=tenant.tenant_id,
                business_name=tenant.business_name,
                sector=tenant.sector,
                plan=tenant.plan,
                whatsapp_phone_number_id=tenant.whatsapp_phone_number_id or None,
                created_at=tenant.created_at or datetime.now(timezone.utc),
                bot_active=True,
                system_prompt_override=None
            )
            session.add(db_tenant)
            try:
                session.commit()
            except Exception as e:
                session.rollback()
                logger.exception("Failed to commit tenant creation.")
                raise e

        logger.info(
            "TenantManager: created tenant id=%s name='%s' plan=%s.",
            tenant.tenant_id,
            tenant.business_name,
            tenant.plan,
        )

    def get_tenant_by_id(self, tenant_id: str) -> Tenant:
        """Fetch a Tenant by its primary key UUID."""
        with SessionLocal() as session:
            db_tenant = session.query(DBTenant).filter(DBTenant.id == tenant_id).first()
            if db_tenant is None:
                raise TenantNotFoundError(
                    f"TenantManager.get_tenant_by_id: no tenant with id='{tenant_id}'."
                )
            return _db_to_domain(db_tenant)

    def get_db_tenant_by_id(self, tenant_id: str) -> DBTenant:
        """Fetch the raw DBTenant database model to read extra attributes (bot_active, system_prompt_override)."""
        with SessionLocal() as session:
            db_tenant = session.query(DBTenant).filter(DBTenant.id == tenant_id).first()
            if db_tenant is None:
                raise TenantNotFoundError(
                    f"TenantManager.get_db_tenant_by_id: no tenant with id='{tenant_id}'."
                )
            # Expunge model from session so it can be read outside transaction block
            session.expunge(db_tenant)
            return db_tenant

    def get_tenant_by_whatsapp_id(self, phone_number_id: str) -> Tenant:
        """Resolve a WhatsApp phone_number_id to a Tenant record."""
        with SessionLocal() as session:
            db_tenant = (
                session.query(DBTenant)
                .filter(DBTenant.whatsapp_phone_number_id == phone_number_id)
                .first()
            )
            if db_tenant is None:
                raise TenantNotFoundError(
                    f"TenantManager.get_tenant_by_whatsapp_id: "
                    f"no tenant registered for phone_number_id='{phone_number_id}'."
                )
            return _db_to_domain(db_tenant)

    def update_tenant(
        self,
        tenant_id: str,
        bot_active: bool,
        system_prompt_override: Optional[str]
    ) -> Tenant:
        """Update a tenant's active bot status and custom prompt override."""
        with SessionLocal() as session:
            db_tenant = session.query(DBTenant).filter(DBTenant.id == tenant_id).first()
            if db_tenant is None:
                raise TenantNotFoundError(
                    f"TenantManager.update_tenant: tenant '{tenant_id}' not found."
                )
            db_tenant.bot_active = bot_active
            db_tenant.system_prompt_override = system_prompt_override
            try:
                session.commit()
                session.refresh(db_tenant)
                return _db_to_domain(db_tenant)
            except Exception as e:
                session.rollback()
                logger.exception("Failed to update tenant configuration.")
                raise e

    def update_whatsapp_phone_number_id(self, tenant_id: str, phone_number_id: str) -> Tenant:
        """Update a tenant's WhatsApp phone number ID in the database."""
        with SessionLocal() as session:
            db_tenant = session.query(DBTenant).filter(DBTenant.id == tenant_id).first()
            if db_tenant is None:
                raise TenantNotFoundError(
                    f"TenantManager.update_whatsapp_phone_number_id: tenant '{tenant_id}' not found."
                )
            db_tenant.whatsapp_phone_number_id = phone_number_id
            try:
                session.commit()
                session.refresh(db_tenant)
                return _db_to_domain(db_tenant)
            except Exception as e:
                session.rollback()
                logger.exception("Failed to update tenant whatsapp_phone_number_id.")
                raise e

    def update_tenant_plan(self, tenant_id: str, new_plan: str) -> Tenant:
        """Upgrade or downgrade a tenant's subscription plan."""
        if new_plan not in self.VALID_PLANS:
            raise ValueError(
                f"TenantManager.update_tenant_plan: unknown plan '{new_plan}'."
            )

        with SessionLocal() as session:
            db_tenant = session.query(DBTenant).filter(DBTenant.id == tenant_id).first()
            if db_tenant is None:
                raise TenantNotFoundError(
                    f"TenantManager.update_tenant_plan: tenant '{tenant_id}' not found."
                )
            db_tenant.plan = new_plan
            try:
                session.commit()
                session.refresh(db_tenant)
                return _db_to_domain(db_tenant)
            except Exception as e:
                session.rollback()
                logger.exception("Failed to update tenant plan.")
                raise e

    def delete_tenant(self, tenant_id: str) -> None:
        """Remove a Tenant record (hard delete)."""
        with SessionLocal() as session:
            db_tenant = session.query(DBTenant).filter(DBTenant.id == tenant_id).first()
            if db_tenant is None:
                raise TenantNotFoundError(
                    f"TenantManager.delete_tenant: tenant '{tenant_id}' not found."
                )
            session.delete(db_tenant)
            try:
                session.commit()
            except Exception as e:
                session.rollback()
                logger.exception("Failed to delete tenant.")
                raise e
        logger.info("TenantManager: deleted tenant id=%s.", tenant_id)

    def list_tenants(self) -> List[Tenant]:
        """Return all tenants."""
        with SessionLocal() as session:
            db_tenants = session.query(DBTenant).order_by(DBTenant.created_at.desc()).all()
            return [_db_to_domain(t) for t in db_tenants]

    def count(self) -> int:
        """Return total number of registered tenants."""
        with SessionLocal() as session:
            return session.query(DBTenant).count()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db_to_domain(db_tenant: DBTenant) -> Tenant:
    """Helper to map a DBTenant SQLAlchemy record to a domain Tenant dataclass."""
    return Tenant(
        tenant_id=db_tenant.id,
        business_name=db_tenant.business_name,
        sector=db_tenant.sector,
        plan=db_tenant.plan,
        whatsapp_phone_number_id=db_tenant.whatsapp_phone_number_id or "",
        created_at=db_tenant.created_at,
    )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: Optional[TenantManager] = None


def get_tenant_manager() -> TenantManager:
    """Return the process-wide singleton TenantManager (lazy-initialised)."""
    global _manager
    if _manager is None:
        _manager = TenantManager()
    return _manager


def reset_tenant_manager(manager: Optional[TenantManager] = None) -> None:
    """Replace the singleton.  Useful in tests to inject a mock manager."""
    global _manager
    _manager = manager
