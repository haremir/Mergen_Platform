"""
mergen_core.plan_guard
~~~~~~~~~~~~~~~~~~~~~~

Domain-agnostic plan enforcement and circuit breaker for the Mergen Platform.

Responsibilities
----------------
* **Rate limiting / quota enforcement**: Every inbound message is metered
  against the tenant's monthly plan quota.  When the quota is exhausted the
  PlanGuard returns ``False`` so the caller can reject or gracefully degrade
  the request before it hits the LLM tier.

* **LLM Circuit Breaker**: Tracks consecutive LLM failures per tenant and
  opens a per-tenant circuit when the failure threshold is reached, preventing
  infinite retry storms and runaway costs.

Storage Architecture
--------------------
Production deployments use **Redis** for both features:

  Monthly usage counter (TTL aligned to end of calendar month):
  ┌────────────────────────────────────────────────────────┐
  │  Key:    tenant_usage:{tenant_id}:{YYYY_MM}            │
  │  Type:   Redis String (INCR / GET / SETEX)             │
  │  TTL:    Remaining seconds in current calendar month   │
  │                                                        │
  │  INCR tenant_usage:abc123:2026_07                      │
  │  EXPIRE tenant_usage:abc123:2026_07 <month_remaining>  │
  └────────────────────────────────────────────────────────┘

  Circuit breaker state (short TTL — resets after 5 minutes):
  ┌────────────────────────────────────────────────────────┐
  │  Key:    circuit:{tenant_id}                           │
  │  Type:   Redis String (consecutive failure count)      │
  │  TTL:    300 seconds (5-minute cooldown window)        │
  │                                                        │
  │  INCR  circuit:abc123                                  │
  │  EXPIRE circuit:abc123 300   (reset on first failure)  │
  └────────────────────────────────────────────────────────┘

This module uses an **in-memory dict** to mock the Redis layer.
To plug in a real adapter, subclass ``PlanGuard`` and override the
private ``_redis_*`` methods.

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Monthly message quotas per plan slug.
# Source of truth: update here → propagate to billing service.
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

    Both features are keyed by ``tenant_id`` so they operate in strict
    per-tenant isolation — one tenant's failures or quota exhaustion never
    affect another.

    Constructor Args
    ----------------
    redis_client:
        Optional Redis client (e.g. ``redis.Redis`` or ``aioredis.Redis``).
        When ``None`` the guard uses an in-memory dict for local dev / tests.

    Example::
        guard = PlanGuard()

        # Quota check
        allowed = guard.check_and_increment("tenant-1", "starter")

        # Circuit breaker
        guard.track_llm_failure("tenant-1")
        if guard.is_circuit_open("tenant-1"):
            raise ServiceUnavailable("LLM circuit open — skip this tenant.")
    """

    def __init__(self, redis_client=None) -> None:
        self._redis = redis_client  # Production: redis.Redis / aioredis connection

        # ── In-memory mock stores (dev / test) ───────────────────────────
        # Usage counters: { "tenant_usage:{tenant_id}:{YYYY_MM}": int }
        self._usage: Dict[str, int] = {}

        # Circuit breaker counters: { "circuit:{tenant_id}": int }
        self._circuit_failures: Dict[str, int] = {}

        # Circuit open timestamps: { "circuit:{tenant_id}": datetime }
        # Used to implement the 5-minute cooldown without actual Redis TTL.
        self._circuit_opened_at: Dict[str, datetime] = {}

        logger.info(
            "PlanGuard: initialised (%s backend).",
            "in-memory mock" if redis_client is None else "redis",
        )

    # ------------------------------------------------------------------
    # Quota Enforcement
    # ------------------------------------------------------------------

    def check_and_increment(self, tenant_id: str, plan: str) -> bool:
        """Check if the tenant is within their monthly quota and increment usage.

        This is an **atomic check-and-set** — increment only happens when
        the quota has not been exceeded.  The Redis pipeline equivalent is:

        Redis equivalent::
            WATCH tenant_usage:{tenant_id}:{YYYY_MM}
            current = GET tenant_usage:{tenant_id}:{YYYY_MM}
            if current >= limit: return False
            INCR tenant_usage:{tenant_id}:{YYYY_MM}
            EXPIRE tenant_usage:{tenant_id}:{YYYY_MM} <remaining_seconds>
            return True

        Args:
            tenant_id: UUID of the tenant sending the message.
            plan:      Subscription plan slug (must be in PLAN_LIMITS).

        Returns:
            ``True``  — quota not exceeded; usage has been incremented.
            ``False`` — quota exceeded; usage is NOT incremented.
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

        usage_key = self._usage_key(tenant_id)
        current = self._usage.get(usage_key, 0)

        if current >= limit:
            logger.warning(
                "PlanGuard: QUOTA EXCEEDED tenant=%s plan=%s usage=%d limit=%d.",
                tenant_id,
                plan,
                current,
                limit,
            )
            return False

        # ── Mock Redis INCR ──────────────────────────────────────────────
        self._usage[usage_key] = current + 1
        logger.debug(
            "PlanGuard: tenant=%s plan=%s usage=%d/%d OK.",
            tenant_id,
            plan,
            current + 1,
            limit,
        )
        return True

    def get_usage(self, tenant_id: str) -> int:
        """Return the current monthly message count for a tenant.

        Redis equivalent::
            GET tenant_usage:{tenant_id}:{YYYY_MM}
        """
        return self._usage.get(self._usage_key(tenant_id), 0)

    def reset_usage(self, tenant_id: str) -> None:
        """Hard-reset a tenant's monthly counter (admin / billing tool).

        Redis equivalent::
            DEL tenant_usage:{tenant_id}:{YYYY_MM}
        """
        key = self._usage_key(tenant_id)
        self._usage.pop(key, None)
        logger.info("PlanGuard: usage counter reset for tenant=%s.", tenant_id)

    # ------------------------------------------------------------------
    # LLM Circuit Breaker
    # ------------------------------------------------------------------

    def track_llm_failure(self, tenant_id: str) -> int:
        """Record one consecutive LLM failure for this tenant.

        Increments the failure counter.  If this is the *first* failure in
        a new window, the cooldown clock starts.  If the threshold is reached
        the circuit is opened.

        Redis equivalent::
            count = INCR circuit:{tenant_id}
            if count == 1:
                EXPIRE circuit:{tenant_id} {_CB_COOLDOWN_SECONDS}

        Args:
            tenant_id: UUID of the tenant whose LLM call failed.

        Returns:
            Current consecutive failure count after the increment.
        """
        cb_key = self._circuit_key(tenant_id)
        current = self._circuit_failures.get(cb_key, 0)

        # First failure in a fresh window → start the cooldown clock
        if current == 0:
            self._circuit_opened_at[cb_key] = datetime.now(tz=timezone.utc)

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
        """Check whether the circuit breaker is currently open for this tenant.

        The circuit is open when:
          1. Consecutive failure count >= threshold, AND
          2. The cooldown window has not yet expired.

        After the cooldown, the circuit automatically resets (half-open
        state — next successful call should call ``reset_circuit``).

        Redis equivalent::
            count = GET circuit:{tenant_id}
            return count is not None and int(count) >= threshold

        Args:
            tenant_id: UUID of the tenant to check.

        Returns:
            ``True`` if the circuit is open (LLM calls should be blocked).
            ``False`` if the circuit is closed (normal operation).
        """
        cb_key = self._circuit_key(tenant_id)
        count = self._circuit_failures.get(cb_key, 0)

        if count < _CB_FAILURE_THRESHOLD:
            return False

        # Check if the cooldown window has expired (mock TTL behaviour)
        opened_at = self._circuit_opened_at.get(cb_key)
        if opened_at is None:
            return False

        elapsed = (datetime.now(tz=timezone.utc) - opened_at).total_seconds()
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
        """Manually close the circuit breaker for a tenant.

        Call this after a successful LLM response to confirm the provider
        is healthy again.

        Redis equivalent::
            DEL circuit:{tenant_id}
        """
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
    def _usage_key(tenant_id: str) -> str:
        """Build the monthly usage Redis key for the current month.

        Format: ``tenant_usage:{tenant_id}:{YYYY_MM}``

        Using YYYY_MM (not YYYY_MM_DD) ensures the counter is shared across
        the entire calendar month and expires automatically at month rollover.
        """
        month = datetime.now(tz=timezone.utc).strftime("%Y_%m")
        return f"tenant_usage:{tenant_id}:{month}"

    @staticmethod
    def _circuit_key(tenant_id: str) -> str:
        """Build the circuit breaker Redis key for a tenant.

        Format: ``circuit:{tenant_id}``
        """
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
