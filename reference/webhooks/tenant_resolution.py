"""
TenantResolutionService — Multi-Tenant SaaS Channel Router.

Loads a JSON mapping from the TENANT_MAP environment variable and resolves
incoming channel identifiers to tenant UUIDs. Supports:
  - WhatsApp Cloud API  (keyed by phone_number_id)
  - Instagram Messaging (keyed by page_id)
  - Telegram Bot        (keyed by bot_token)

TENANT_MAP format (JSON string in env var):
{
    "whatsapp": {
        "<phone_number_id>": "<tenant_uuid>"
    },
    "instagram": {
        "<page_id>": "<tenant_uuid>"
    },
    "telegram": {
        "<bot_token>": "<tenant_uuid>"
    }
}
"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_TENANT_MAP_ENV_KEY = "TENANT_MAP"
_FALLBACK_TENANT_ENV_KEY = "ACTIVE_TENANT_ID"

# Channel name constants
CHANNEL_WHATSAPP = "whatsapp"
CHANNEL_INSTAGRAM = "instagram"
CHANNEL_TELEGRAM = "telegram"


class TenantResolutionService:
    """
    Resolves channel-specific identifiers to tenant UUIDs.

    Thread-safe and async-safe — the internal map is read-only after __init__.
    One singleton instance is shared across all concurrent requests.
    """

    def __init__(self, tenant_map: Optional[Dict] = None) -> None:
        """
        Args:
            tenant_map: Optional explicit map dict. If None, loads from
                        TENANT_MAP environment variable.
        """
        if tenant_map is not None:
            self._map = tenant_map
        else:
            self._map = self._load_from_env()

    # ------------------------------------------------------------------
    # Public Resolution API
    # ------------------------------------------------------------------

    def resolve_whatsapp(self, phone_number_id: str) -> Optional[str]:
        """Resolve a WhatsApp phone_number_id to a tenant_id."""
        return self._resolve(CHANNEL_WHATSAPP, phone_number_id)

    def resolve_instagram(self, page_id: str) -> Optional[str]:
        """Resolve an Instagram page_id to a tenant_id."""
        return self._resolve(CHANNEL_INSTAGRAM, page_id)

    def resolve_telegram(self, bot_token: str) -> Optional[str]:
        """Resolve a Telegram bot token to a tenant_id."""
        return self._resolve(CHANNEL_TELEGRAM, bot_token)

    def resolve(self, channel: str, identifier: str) -> Optional[str]:
        """
        Generic resolver. Falls back to ACTIVE_TENANT_ID env var if no
        explicit mapping is found.

        Args:
            channel: One of 'whatsapp', 'instagram', 'telegram'.
            identifier: The channel-specific key (phone_number_id, page_id, token).

        Returns:
            Resolved tenant UUID, or the ACTIVE_TENANT_ID fallback, or None.
        """
        tenant_id = self._resolve(channel, identifier)
        if tenant_id:
            return tenant_id

        # Fallback: single-tenant env var
        fallback = os.getenv(_FALLBACK_TENANT_ENV_KEY, "")
        if fallback:
            logger.debug(
                "TenantResolutionService: no explicit mapping for %s:%s — using ACTIVE_TENANT_ID fallback.",
                channel,
                identifier,
            )
            return fallback

        logger.warning(
            "TenantResolutionService: cannot resolve tenant for %s:%s — "
            "no TENANT_MAP entry and ACTIVE_TENANT_ID is not set.",
            channel,
            identifier,
        )
        return None

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _resolve(self, channel: str, identifier: str) -> Optional[str]:
        channel_map: Dict[str, str] = self._map.get(channel, {})
        return channel_map.get(str(identifier))

    @staticmethod
    def _load_from_env() -> Dict:
        raw = os.getenv(_TENANT_MAP_ENV_KEY, "")
        if not raw:
            logger.info(
                "TenantResolutionService: TENANT_MAP env var not set; "
                "will fall back to ACTIVE_TENANT_ID for all channels."
            )
            return {}
        try:
            mapping = json.loads(raw)
            if not isinstance(mapping, dict):
                raise ValueError("TENANT_MAP must be a JSON object.")
            logger.info(
                "TenantResolutionService: loaded %d channel group(s) from TENANT_MAP.",
                len(mapping),
            )
            return mapping
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(
                "TenantResolutionService: failed to parse TENANT_MAP — %s. "
                "All channel requests will use ACTIVE_TENANT_ID fallback.",
                exc,
            )
            return {}


# ---------------------------------------------------------------------------
# Module-Level Singleton
# ---------------------------------------------------------------------------
# Loaded once at import time. Safe to access from any async task because the
# map is read-only after construction.
_tenant_resolver: Optional[TenantResolutionService] = None


def get_tenant_resolver() -> TenantResolutionService:
    """Returns the module-level singleton TenantResolutionService."""
    global _tenant_resolver
    if _tenant_resolver is None:
        _tenant_resolver = TenantResolutionService()
    return _tenant_resolver


def reset_tenant_resolver(resolver: Optional[TenantResolutionService] = None) -> None:
    """
    Replaces the singleton. Used in tests to inject mock resolvers.

    Args:
        resolver: New resolver to use. Pass None to force re-creation from env.
    """
    global _tenant_resolver
    _tenant_resolver = resolver
