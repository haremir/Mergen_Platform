"""
mergen_core.handoff_engine
~~~~~~~~~~~~~~~~~~~~~~~~~~

Domain-agnostic human handoff detection and event emission for the Mergen Platform.

Responsibilities
----------------
* **Intent detection**: Scans inbound text for multilingual signals that
  indicate the user wants to speak with a human operator.  The keyword
  library covers common expressions in English and Turkish.

* **Generic event emission**: When a handoff is triggered, the engine emits
  a plain Python dict (a ``HandoffEvent``) rather than calling any specific
  delivery channel.  The calling layer (webhook handler, conversation engine)
  is responsible for routing the event to the appropriate notifier
  (internal queue, CRM, ticketing system, etc.).

Design Principles
-----------------
* **Channel-agnostic**: The engine has ZERO knowledge of WhatsApp, Telegram,
  SMS, Email, or any other delivery mechanism.  Coupling to channels must
  happen at the product layer.
* **Immutable events**: The emitted dict is a snapshot of the moment the
  handoff was triggered.  It should be treated as append-only.
* **Auditable**: Every trigger is logged at WARNING level with a structured
  context so it can be correlated in the platform's audit log.

HandoffEvent Schema
-------------------
    {
        "event_type":        "handoff_required",
        "tenant_id":         str,             # UUID of the requesting tenant
        "reason":            str,             # "user_requested" | "llm_failure" | "policy"
        "trigger_keyword":   str | None,      # keyword that triggered the event
        "original_message": {                 # Serialised InboundMessage
            "tenant_id":    str,
            "channel":      str,
            "sender":       str,
            "text":         str,
            "received_at":  str,             # ISO-8601
        },
        "timestamp":        str,             # ISO-8601 event creation time
    }

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Import shared domain models
# ---------------------------------------------------------------------------
try:
    from mergen_common.models import InboundMessage
except ModuleNotFoundError:
    _shared = os.path.join(os.path.dirname(__file__), "..", "..", "shared")
    sys.path.insert(0, os.path.abspath(_shared))
    from mergen_common.models import InboundMessage  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handoff Keyword / Pattern Library
# ---------------------------------------------------------------------------
# Multilingual trigger signals.  Each entry is a (pattern, label) tuple.
# The label is used in the event's ``trigger_keyword`` field for traceability.
#
# Coverage:
#   EN — English expressions for requesting a human agent
#   TR — Turkish equivalents (the platform's primary secondary language)
#
# Extend this list for additional languages; no code changes required.

_HANDOFF_SIGNALS: List[Tuple[str, str]] = [
    # ── English ──────────────────────────────────────────────────────────
    (r"\bhuman\b",                  "en:human"),
    (r"\bhuman\s+agent\b",          "en:human_agent"),
    (r"\bhuman\s+operator\b",       "en:human_operator"),
    (r"\blive\s+agent\b",           "en:live_agent"),
    (r"\blive\s+support\b",         "en:live_support"),
    (r"\breal\s+person\b",          "en:real_person"),
    (r"\breal\s+agent\b",           "en:real_agent"),
    (r"\bspeak\s+(to|with)\s+(a\s+)?(human|person|agent|representative)\b", "en:speak_to_human"),
    (r"\btalk\s+(to|with)\s+(a\s+)?(human|person|agent|representative)\b",  "en:talk_to_human"),
    (r"\bconnect\s+me\s+(to|with)\b","en:connect_me"),
    (r"\btransfer\s+me\b",          "en:transfer_me"),
    (r"\bescalate\b",               "en:escalate"),
    (r"\bcomplaint\b",              "en:complaint"),
    (r"\bsupervisor\b",             "en:supervisor"),
    (r"\bmanager\b",                "en:manager"),
    (r"\bi\s+(need|want)\s+(to\s+)?(speak|talk|chat)\s+(to|with)?\s*(a\s+)?(human|person|agent)\b",
                                    "en:i_need_human"),
    # ── Turkish ──────────────────────────────────────────────────────────
    (r"\binsan\b",                  "tr:insan"),
    (r"\bgercek\s+kisi\b",          "tr:gercek_kisi"),
    (r"\bgercek\s+kisi\b",          "tr:gercek_kisi_ascii"),
    (r"\bmusteri\s+temsilcisi",      "tr:musteri_temsilcisi"),
    (r"\bmüşteri\s+temsilcisi",      "tr:musteri_temsilcisi_unicode"),
    (r"\boperator\b",               "tr:operator"),
    (r"\boperatör\b",               "tr:operatr_unicode"),
    (r"\bdestek\s+ekibi\b",         "tr:destek_ekibi"),
    (r"\byetkili\b",                "tr:yetkili"),
    (r"\bsikayet\b",                "tr:sikayet_ascii"),
    (r"\bşikayet\b",                "tr:sikayet_unicode"),
    (r"\bsorun\s+var\b",            "tr:sorun_var"),
    (r"\btemsilci\b",               "tr:temsilci"),
    (r"\binsanla\s+konusmak\b",     "tr:insanla_konusmak"),
    (r"\bcanlı\s+destek\b",         "tr:canli_destek"),
    (r"\bcali\s*stir\b",            "tr:calistir"),
    (r"\byardim\s+istiyorum\b",     "tr:yardim_istiyorum"),
    (r"\bmemnun\s+(kalmadim|degilim)\b", "tr:memnun_kalmadim"),
]

# Pre-compile all patterns for performance
_COMPILED_SIGNALS: List[Tuple[re.Pattern, str]] = [
    (re.compile(pattern, re.IGNORECASE | re.UNICODE), label)
    for pattern, label in _HANDOFF_SIGNALS
]

# Reasons for handoff — extend as needed
REASON_USER_REQUESTED = "user_requested"
REASON_LLM_FAILURE    = "llm_failure"
REASON_POLICY         = "policy_violation"


# ---------------------------------------------------------------------------
# HandoffEngine
# ---------------------------------------------------------------------------

class HandoffEngine:
    """Detects human handoff intent and emits generic HandoffEvents.

    The engine is stateless — it holds no per-tenant or per-session state.
    All state lives in the calling conversation engine.

    Example::
        engine = HandoffEngine()

        if engine.analyze_handoff_intent(user_text):
            event = engine.trigger_notification(
                tenant_id=msg.tenant_id,
                message=msg,
                reason=REASON_USER_REQUESTED,
            )
            # Route `event` to your notification bus / ticketing system
    """

    def __init__(self) -> None:
        logger.info(
            "HandoffEngine: initialised with %d trigger signal(s).",
            len(_COMPILED_SIGNALS),
        )

    # ------------------------------------------------------------------
    # Intent Detection
    # ------------------------------------------------------------------

    def analyze_handoff_intent(self, user_text: str) -> bool:
        """Detect whether the user is requesting a human operator.

        Scans normalised text against the multilingual keyword/pattern library.
        The first match short-circuits the scan for efficiency.

        Args:
            user_text: Raw text from the end user.

        Returns:
            ``True``  — handoff intent detected.
            ``False`` — no handoff signal found.
        """
        if not user_text or not user_text.strip():
            return False

        normalised = re.sub(r"\s+", " ", user_text.strip())

        for compiled_pattern, label in _COMPILED_SIGNALS:
            match = compiled_pattern.search(normalised)
            if match:
                logger.info(
                    "HandoffEngine.analyze_handoff_intent: signal detected "
                    "label='%s' match='%s' text='%.80s'",
                    label,
                    match.group(0),
                    user_text,
                )
                return True

        logger.debug(
            "HandoffEngine.analyze_handoff_intent: no signal in '%.60s'",
            user_text,
        )
        return False

    def get_trigger_label(self, user_text: str) -> Optional[str]:
        """Return the label of the first matched handoff signal, or None.

        Useful for including the matched trigger in the HandoffEvent for
        traceability and analytics.

        Args:
            user_text: Raw user text.

        Returns:
            Label string (e.g. ``"tr:musteri_temsilcisi"``) or ``None``.
        """
        if not user_text:
            return None
        normalised = re.sub(r"\s+", " ", user_text.strip())
        for compiled_pattern, label in _COMPILED_SIGNALS:
            if compiled_pattern.search(normalised):
                return label
        return None

    # ------------------------------------------------------------------
    # Event Emission
    # ------------------------------------------------------------------

    def trigger_notification(
        self,
        tenant_id: str,
        message: InboundMessage,
        reason: str = REASON_USER_REQUESTED,
    ) -> Dict:
        """Emit a generic HandoffEvent dict.

        This method is deliberately channel-agnostic.  It logs a structured
        warning and returns a plain Python dict.  The calling layer routes
        this dict to the appropriate delivery mechanism (internal message
        queue, CRM webhook, ticketing API, etc.).

        Args:
            tenant_id: UUID of the tenant that owns this conversation.
            message:   The ``InboundMessage`` that triggered the handoff.
            reason:    Reason code for the handoff.  Use one of the module-level
                       ``REASON_*`` constants.

        Returns:
            A ``HandoffEvent`` dict (see module docstring for schema).
        """
        trigger_label = self.get_trigger_label(message.text)
        timestamp = datetime.now(tz=timezone.utc).isoformat()

        event: Dict = {
            "event_type":       "handoff_required",
            "tenant_id":        tenant_id,
            "reason":           reason,
            "trigger_keyword":  trigger_label,
            "original_message": {
                "tenant_id":   message.tenant_id,
                "channel":     message.channel,
                "sender":      message.sender,
                "text":        message.text,
                "received_at": message.received_at.isoformat()
                               if hasattr(message.received_at, "isoformat")
                               else str(message.received_at),
            },
            "timestamp": timestamp,
        }

        logger.warning(
            "HandoffEngine.trigger_notification: HANDOFF REQUIRED "
            "tenant=%s reason=%s channel=%s sender=%s trigger='%s'",
            tenant_id,
            reason,
            message.channel,
            message.sender,
            trigger_label or "n/a",
        )

        return event

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def signal_count(self) -> int:
        """Return the number of active handoff detection signals."""
        return len(_COMPILED_SIGNALS)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_engine: Optional[HandoffEngine] = None


def get_handoff_engine() -> HandoffEngine:
    """Return the process-wide singleton HandoffEngine (lazy-initialised)."""
    global _engine
    if _engine is None:
        _engine = HandoffEngine()
    return _engine


def reset_handoff_engine(engine: Optional[HandoffEngine] = None) -> None:
    """Replace the singleton.  Useful in tests to inject a mock engine."""
    global _engine
    _engine = engine
