"""
mergen_core.plan_guard
~~~~~~~~~~~~~~~~~~~~~~

Domain-agnostic plan enforcement and LLM circuit breaker for the Mergen Platform.
SQLAlchemy database version for quota tracking and concurrent usage protection.

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from mergen_core.database import SessionLocal
from mergen_core.db_models import DBPlanUsage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Monthly message quotas per plan slug.
PLAN_LIMITS: Dict[str, int] = {
    "free":       100,
    "starter":    500,
    "business":   2_000,
    "premium":    99_999,
    "enterprise": 999_999,
}

# Circuit breaker thresholds
_CB_FAILURE_THRESHOLD: int = 3     # Open circuit after N consecutive failures
_CB_COOLDOWN_SECONDS:  int = 300   # Seconds before circuit auto-resets (5 min)


# ---------------------------------------------------------------------------
# PlanGuard
# ---------------------------------------------------------------------------

class PlanGuard:
    """Plan quota enforcer and LLM circuit breaker.

    Uses SQLAlchemy database transactions for concurrency-safe quota tracking,
    and process-wide memory stores for transient circuit breaker states.
    """

    def __init__(self, redis_client=None) -> None:
        self._redis = redis_client

        # ── In-memory transient stores for Circuit Breaker ───────────────
        # Circuit breaker counters: { "circuit:{tenant_id}": int }
        self._circuit_failures: Dict[str, int] = {}

        # Circuit open timestamps: { "circuit:{tenant_id}": datetime }
        self._circuit_opened_at: Dict[str, datetime] = {}

        logger.info(
            "PlanGuard: initialised with SQLAlchemy ORM database usage backend."
        )

    # ------------------------------------------------------------------
    # Quota Enforcement (SQL Database Backed)
    # ------------------------------------------------------------------

    def check_and_increment(self, tenant_id: str, plan: str) -> bool:
        """Check if the tenant is within their monthly quota and increment usage.

        Uses SELECT FOR UPDATE to lock the row and ensure concurrency safety.
        """
        limit = PLAN_LIMITS.get(plan)
        if limit is None:
            logger.warning(
                "PlanGuard.check_and_increment: unknown plan '%s' for tenant %s — "
                "defaulting to 'free' limit (%d).",
                plan,
                tenant_id,
                PLAN_LIMITS["free"],
            )
            limit = PLAN_LIMITS["free"]

        month_key = datetime.now(timezone.utc).strftime("%Y-%m")

        with SessionLocal() as session:
            try:
                # Select with update row locking
                usage_row = (
                    session.query(DBPlanUsage)
                    .filter(
                        DBPlanUsage.tenant_id == tenant_id,
                        DBPlanUsage.month_key == month_key
                    )
                    .with_for_update()
                    .first()
                )

                if usage_row is None:
                    usage_row = DBPlanUsage(
                        tenant_id=tenant_id,
                        month_key=month_key,
                        used_messages=0
                    )
                    session.add(usage_row)
                    session.flush()

                if usage_row.used_messages >= limit:
                    logger.warning(
                        "PlanGuard: QUOTA EXCEEDED tenant=%s plan=%s usage=%d limit=%d.",
                        tenant_id,
                        plan,
                        usage_row.used_messages,
                        limit,
                    )
                    session.rollback()
                    return False

                usage_row.used_messages += 1
                session.commit()
                
                logger.debug(
                    "PlanGuard: tenant=%s plan=%s usage=%d/%d OK.",
                    tenant_id,
                    plan,
                    usage_row.used_messages,
                    limit,
                )
                return True

            except Exception as e:
                session.rollback()
                logger.exception("Failed to execute check_and_increment transaction.")
                raise e

    def get_usage(self, tenant_id: str) -> int:
        """Return the current monthly message count for a tenant."""
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        with SessionLocal() as session:
            usage_row = (
                session.query(DBPlanUsage)
                .filter(
                    DBPlanUsage.tenant_id == tenant_id,
                    DBPlanUsage.month_key == month_key
                )
                .first()
            )
            return usage_row.used_messages if usage_row else 0

    def reset_usage(self, tenant_id: str) -> None:
        """Hard-reset a tenant's monthly counter."""
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        with SessionLocal() as session:
            usage_row = (
                session.query(DBPlanUsage)
                .filter(
                    DBPlanUsage.tenant_id == tenant_id,
                    DBPlanUsage.month_key == month_key
                )
                .first()
            )
            if usage_row:
                session.delete(usage_row)
                try:
                    session.commit()
                    logger.info("PlanGuard: usage counter reset for tenant=%s.", tenant_id)
                except Exception as e:
                    session.rollback()
                    logger.exception("Failed to delete usage row.")
                    raise e

    # ------------------------------------------------------------------
    # LLM Circuit Breaker (Transient Process-wide Memory)
    # ------------------------------------------------------------------

    def track_llm_failure(self, tenant_id: str) -> int:
        """Record one consecutive LLM failure for this tenant."""
        cb_key = self._circuit_key(tenant_id)
        current = self._circuit_failures.get(cb_key, 0)

        if current == 0:
            self._circuit_opened_at[cb_key] = datetime.now(timezone.utc)

        new_count = current + 1
        self._circuit_failures[cb_key] = new_count

        if new_count >= _CB_FAILURE_THRESHOLD:
            logger.error(
                "PlanGuard: CIRCUIT OPEN tenant=%s consecutive_failures=%d "
                "(threshold=%d). LLM calls blocked for %ds.",
                tenant_id,
                new_count,
                _CB_FAILURE_THRESHOLD,
                _CB_COOLDOWN_SECONDS,
            )
        else:
            logger.warning(
                "PlanGuard: LLM failure tracked tenant=%s count=%d/%d.",
                tenant_id,
                new_count,
                _CB_FAILURE_THRESHOLD,
            )

        return new_count

    def is_circuit_open(self, tenant_id: str) -> bool:
        """Check whether the circuit breaker is currently open for this tenant."""
        cb_key = self._circuit_key(tenant_id)
        count = self._circuit_failures.get(cb_key, 0)

        if count < _CB_FAILURE_THRESHOLD:
            return False

        opened_at = self._circuit_opened_at.get(cb_key)
        if opened_at is None:
            return False

        elapsed = (datetime.now(timezone.utc) - opened_at).total_seconds()
        if elapsed >= _CB_COOLDOWN_SECONDS:
            # Cooldown expired — auto-reset (half-open)
            self._circuit_failures.pop(cb_key, None)
            self._circuit_opened_at.pop(cb_key, None)
            logger.info(
                "PlanGuard: circuit AUTO-RESET for tenant=%s (cooldown expired).",
                tenant_id,
            )
            return False

        return True

    def reset_circuit(self, tenant_id: str) -> None:
        """Manually close the circuit breaker for a tenant."""
        cb_key = self._circuit_key(tenant_id)
        self._circuit_failures.pop(cb_key, None)
        self._circuit_opened_at.pop(cb_key, None)
        logger.info("PlanGuard: circuit RESET (manually) for tenant=%s.", tenant_id)

    def get_failure_count(self, tenant_id: str) -> int:
        """Return current consecutive failure count for a tenant."""
        return self._circuit_failures.get(self._circuit_key(tenant_id), 0)

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _circuit_key(tenant_id: str) -> str:
        return f"circuit:{tenant_id}"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_guard: Optional[PlanGuard] = None


def get_plan_guard() -> PlanGuard:
    """Return the process-wide singleton PlanGuard (lazy-initialised)."""
    global _guard
    if _guard is None:
        _guard = PlanGuard()
    return _guard


def reset_plan_guard(guard: Optional[PlanGuard] = None) -> None:
    """Replace the singleton.  Useful in tests to inject a mock guard."""
    global _guard
    _guard = guard
