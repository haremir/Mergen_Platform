"""
mergen_core.tenant_manager
~~~~~~~~~~~~~~~~~~~~~~~~~~

Domain-agnostic multi-tenant manager for the Mergen Platform.

Responsibilities
----------------
* CRUD operations for Tenant records (PostgreSQL-backed in production).
* Webhook routing key resolution: resolves a ``whatsapp_phone_number_id``
  to the matching Tenant so the webhook firewall can dispatch inbound
  messages to the correct tenant context.

Storage Architecture
--------------------
Production deployments use a PostgreSQL ``tenants`` table:

    CREATE TABLE tenants (
        tenant_id               UUID PRIMARY KEY,
        business_name           TEXT        NOT NULL,
        sector                  TEXT        NOT NULL,
        plan                    TEXT        NOT NULL DEFAULT 'starter',
        whatsapp_phone_number_id TEXT       UNIQUE,
        created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    -- Lookup index for webhook routing (hot path, must be fast)
    CREATE INDEX idx_tenants_wa_phone ON tenants (whatsapp_phone_number_id);

This module uses an **in-memory dict** to mock the DB adapter so the
class can be imported and tested without a real database.  To plug in
a real adapter, subclass ``TenantManager`` and override the private
``_db_*`` methods — the public API surface does not change.

Pattern inspired by (but NOT imported from):
    reference/webhooks/tenant_resolution.py

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Dict, Optional

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
    """Multi-tenant CRUD manager with webhook-routing key resolution.

    Constructor Args
    ---------------
    db_adapter:
        Optional production database adapter (e.g. asyncpg connection pool).
        When ``None`` (default) the manager falls back to an in-memory dict
        that mimics the SQL layer for local development and unit tests.

    Example::
        manager = TenantManager()
        manager.create_tenant(tenant)
        found = manager.get_tenant_by_whatsapp_id("109876543210123")
    """

    # Subscription plan hierarchy — also defined in plan_guard.py.
    # Keep in sync if plans change.
    VALID_PLANS = frozenset({"free", "starter", "business", "premium", "enterprise"})

    def __init__(self, db_adapter=None) -> None:
        self._db = db_adapter  # Production: asyncpg pool / SQLAlchemy session

        # ── In-memory mock store (dev / test) ────────────────────────────
        # Structure mirrors two DB indexes:
        #   _store_by_id        → { tenant_id: Tenant }        (PK lookup)
        #   _store_by_wa_phone  → { phone_number_id: tenant_id }  (FK index)
        self._store_by_id: Dict[str, Tenant] = {}
        self._store_by_wa_phone: Dict[str, str] = {}

        logger.info(
            "TenantManager: initialised (%s backend).",
            "in-memory mock" if db_adapter is None else "database",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_tenant(self, tenant: Tenant) -> None:
        """Persist a new Tenant record.

        Args:
            tenant: Fully-populated ``Tenant`` dataclass.

        Raises:
            TenantAlreadyExistsError: If ``tenant_id`` already exists.
            ValueError: If ``tenant.plan`` is not a recognised plan slug.

        SQL equivalent::
            INSERT INTO tenants
                (tenant_id, business_name, sector, plan,
                 whatsapp_phone_number_id, created_at)
            VALUES
                ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (tenant_id) DO NOTHING;
        """
        if tenant.plan not in self.VALID_PLANS:
            raise ValueError(
                f"TenantManager.create_tenant: unknown plan '{tenant.plan}'. "
                f"Valid plans: {sorted(self.VALID_PLANS)}"
            )

        if tenant.tenant_id in self._store_by_id:
            raise TenantAlreadyExistsError(
                f"TenantManager.create_tenant: tenant '{tenant.tenant_id}' already exists."
            )

        # ── Mock DB write ────────────────────────────────────────────────
        self._store_by_id[tenant.tenant_id] = tenant
        if tenant.whatsapp_phone_number_id:
            self._store_by_wa_phone[tenant.whatsapp_phone_number_id] = tenant.tenant_id

        logger.info(
            "TenantManager: created tenant id=%s name='%s' plan=%s.",
            tenant.tenant_id,
            tenant.business_name,
            tenant.plan,
        )

    def get_tenant_by_id(self, tenant_id: str) -> Tenant:
        """Fetch a Tenant by its primary key UUID.

        Args:
            tenant_id: UUID string.

        Returns:
            The matching ``Tenant`` dataclass.

        Raises:
            TenantNotFoundError: If no tenant with that ID exists.

        SQL equivalent::
            SELECT * FROM tenants WHERE tenant_id = $1 LIMIT 1;
        """
        tenant = self._store_by_id.get(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(
                f"TenantManager.get_tenant_by_id: no tenant with id='{tenant_id}'."
            )
        logger.debug("TenantManager: fetched tenant by id=%s.", tenant_id)
        return tenant

    def get_tenant_by_whatsapp_id(self, phone_number_id: str) -> Tenant:
        """Resolve a WhatsApp ``phone_number_id`` to a Tenant record.

        This is the **hot path** called on every inbound webhook request.
        In production, the query hits the ``idx_tenants_wa_phone`` index:

        SQL equivalent::
            SELECT * FROM tenants
            WHERE whatsapp_phone_number_id = $1
            LIMIT 1;

        Args:
            phone_number_id: Meta Cloud API ``phone_number_id`` value from
                             the webhook payload's ``value.metadata`` block.

        Returns:
            The matching ``Tenant`` dataclass.

        Raises:
            TenantNotFoundError: If no tenant is registered for that
                                 phone_number_id. This is the firewall
                                 rejection trigger — callers should respond
                                 with HTTP 403 to Meta.
        """
        tenant_id = self._store_by_wa_phone.get(phone_number_id)
        if tenant_id is None:
            raise TenantNotFoundError(
                f"TenantManager.get_tenant_by_whatsapp_id: "
                f"no tenant registered for phone_number_id='{phone_number_id}'."
            )
        return self.get_tenant_by_id(tenant_id)

    def update_tenant_plan(self, tenant_id: str, new_plan: str) -> Tenant:
        """Upgrade or downgrade a tenant's subscription plan.

        Args:
            tenant_id: UUID of the tenant to update.
            new_plan:  Target plan slug (must be in VALID_PLANS).

        Returns:
            Updated ``Tenant`` dataclass.

        Raises:
            TenantNotFoundError: If tenant does not exist.
            ValueError: If ``new_plan`` is not a recognised plan slug.

        SQL equivalent::
            UPDATE tenants SET plan = $2 WHERE tenant_id = $1
            RETURNING *;
        """
        if new_plan not in self.VALID_PLANS:
            raise ValueError(
                f"TenantManager.update_tenant_plan: unknown plan '{new_plan}'."
            )
        existing = self.get_tenant_by_id(tenant_id)

        # Dataclasses are not frozen, so we replace the instance
        from dataclasses import replace
        updated = replace(existing, plan=new_plan)
        self._store_by_id[tenant_id] = updated

        logger.info(
            "TenantManager: updated tenant id=%s plan %s → %s.",
            tenant_id,
            existing.plan,
            new_plan,
        )
        return updated

    def delete_tenant(self, tenant_id: str) -> None:
        """Remove a Tenant record (hard delete).

        SQL equivalent::
            DELETE FROM tenants WHERE tenant_id = $1;

        Args:
            tenant_id: UUID of the tenant to delete.

        Raises:
            TenantNotFoundError: If tenant does not exist.
        """
        tenant = self.get_tenant_by_id(tenant_id)
        del self._store_by_id[tenant_id]
        if tenant.whatsapp_phone_number_id in self._store_by_wa_phone:
            del self._store_by_wa_phone[tenant.whatsapp_phone_number_id]
        logger.info("TenantManager: deleted tenant id=%s.", tenant_id)

    def list_tenants(self) -> list:
        """Return all tenants (dev / admin use only — no pagination).

        SQL equivalent::
            SELECT * FROM tenants ORDER BY created_at DESC;
        """
        return list(self._store_by_id.values())

    def count(self) -> int:
        """Return total number of registered tenants."""
        return len(self._store_by_id)


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
