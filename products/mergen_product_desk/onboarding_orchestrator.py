"""
mergen_product_desk.onboarding_orchestrator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Desk product client onboarding orchestration.

``DeskOnboardingService`` coordinates the full client setup flow:

  1. Validate knowledge form data          → DeskTemplateValidator
  2. Register tenant in the platform       → Core TenantManager
  3. Ingest knowledge fields into RAG      → Core RagEngine
  4. Register WhatsApp number with Meta    → mergen_pkg_whatsapp WhatsAppClient
  5. Return status dict                    → {"status": ..., "phone_number_id": ...}

Flow Diagram::

    setup_new_client(tenant_id, business_name, raw_form_data, phone_number)
         │
         ├─ 1. DeskTemplateValidator.validate_and_convert()
         │       └─ DeskValidationError  →  abort, return {"status": "validation_error"}
         │
         ├─ 2. TenantManager.create_tenant()
         │       └─ TenantAlreadyExistsError  →  idempotent skip, continue
         │
         ├─ 3. RagEngine.index_knowledge_fields()
         │       └─ Exception  →  log + abort, return {"status": "rag_error"}
         │
         ├─ 4. WhatsAppClient.add_phone_number()
         │       └─ WhatsAppAPIError  →  log + return {"status": "whatsapp_error"}
         │
         └─ 5. Return {"status": "pending_verification", "phone_number_id": <id>,
                        "knowledge_fields_ingested": N, "tenant_id": ..., ...}

Status Codes
------------
``pending_verification``   Successful — waiting for Meta OTP verification.
``validation_error``       Required form field(s) missing.
``tenant_error``           Tenant creation failed unexpectedly.
``rag_error``              Knowledge ingestion failed.
``whatsapp_error``         Meta API call failed.

Author: Mergen Platform -- Desk Product Team
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup for cross-package imports
# ---------------------------------------------------------------------------
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for _p in (
    os.path.join(_ROOT, "shared"),
    os.path.join(_ROOT, "core"),
    os.path.join(_ROOT, "packages"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------
from mergen_common.models import Tenant, KnowledgeField  # noqa: E402

# ---------------------------------------------------------------------------
# Core imports
# ---------------------------------------------------------------------------
from mergen_core.tenant_manager import (  # noqa: E402
    TenantManager,
    TenantAlreadyExistsError,
    get_tenant_manager,
)
from mergen_core.rag_engine import RagEngine, get_rag_engine  # noqa: E402

# ---------------------------------------------------------------------------
# WhatsApp package
# ---------------------------------------------------------------------------
from mergen_pkg_whatsapp.client import (  # noqa: E402
    WhatsAppClient,
    WhatsAppAPIError,
)

# ---------------------------------------------------------------------------
# Desk product modules
# ---------------------------------------------------------------------------
from mergen_product_desk.knowledge_template import (  # noqa: E402
    DeskTemplateValidator,
    DeskValidationError,
)
from mergen_product_desk.desk_persona import DESK_PERSONA  # noqa: E402

logger = logging.getLogger(__name__)

# Default plan slug assigned to all Desk tenants at onboarding
_DESK_DEFAULT_PLAN = "starter"
_DESK_SECTOR       = "desk"


# ---------------------------------------------------------------------------
# DeskOnboardingService
# ---------------------------------------------------------------------------

class DeskOnboardingService:
    """Orchestrates the full client setup flow for the Desk product.

    All dependencies are injected at construction time to allow easy mocking
    in tests and verification scripts.

    Constructor Args
    ----------------
    whatsapp_client:
        A ``WhatsAppClient`` instance (or compatible mock).  Required.
    tenant_manager:
        Optional ``TenantManager``.  Defaults to the process-wide singleton
        via ``get_tenant_manager()``.
    rag_engine:
        Optional ``RagEngine``.  When ``None``, a new instance is created
        with default (FAISS) backend.

    Example::
        service = DeskOnboardingService(
            whatsapp_client=WhatsAppClient(token=..., waba_id=...),
        )
        result = service.setup_new_client(
            tenant_id="abc-123",
            business_name="Acme Barber",
            raw_form_data={
                "business_hours": "Mon-Fri 09:00-19:00",
                "location": "Kadikoy, Istanbul",
                "contact_info": "acme@example.com | +90 212 000 0000",
                "cancellation_policy": "24 hours notice required",
                "services": "Haircut, Beard trim, Coloring",
            },
            phone_number="+905550001234",
        )
    """

    def __init__(
        self,
        whatsapp_client: WhatsAppClient,
        tenant_manager: Optional[TenantManager] = None,
        rag_engine: Optional[RagEngine] = None,
    ) -> None:
        self._wa = whatsapp_client
        self._tenant_mgr = tenant_manager or get_tenant_manager()
        self._rag = rag_engine or get_rag_engine()
        self._validator = DeskTemplateValidator()

        logger.info(
            "DeskOnboardingService: initialised (TenantManager=%s, RagEngine=%s).",
            type(self._tenant_mgr).__name__,
            type(self._rag).__name__,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup_new_client(
        self,
        tenant_id: str,
        business_name: str,
        raw_form_data: Dict[str, Any],
        phone_number: str,
        plan: str = _DESK_DEFAULT_PLAN,
        sector: str = _DESK_SECTOR,
        persona: str = "friendly_energetic",
        meta_phone_id: str = "",
        meta_access_token: Optional[str] = None,
        telegram_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Orchestrate the full Desk client onboarding flow.

        Args:
            tenant_id:      UUID for the new tenant (caller-generated).
            business_name:  Human-readable display name for the business.
            raw_form_data:  Knowledge form data (see DeskTemplateValidator schema).
            phone_number:   E.164 WhatsApp phone number to register.
            plan:           Subscription plan slug (default: "starter").

        Returns:
            Status dict.  Keys:
            - ``status``                    : str (see module-level Status Codes)
            - ``tenant_id``                 : str
            - ``phone_number_id``           : str (set on success)
            - ``knowledge_fields_ingested`` : int (count)
            - ``persona``                   : str (registered persona name)
            - ``error``                     : str (set on failure)
        """
        result: Dict[str, Any] = {
            "tenant_id":                 tenant_id,
            "business_name":             business_name,
            "phone_number":              phone_number,
            "phone_number_id":           None,
            "knowledge_fields_ingested": 0,
            "persona":                   persona,
            "status":                    "unknown",
            "error":                     None,
        }

        # ── Step 1: Validate form data ─────────────────────────────────────
        logger.info(
            "DeskOnboardingService.setup_new_client: STEP 1 — validating form data for tenant=%s.",
            tenant_id,
        )
        form_data = dict(raw_form_data)
        form_data["persona"] = persona

        try:
            knowledge_fields: List[KnowledgeField] = self._validator.validate_and_convert(
                tenant_id=tenant_id,
                raw_form_data=form_data,
            )
        except DeskValidationError as exc:
            logger.error(
                "DeskOnboardingService: validation FAILED tenant=%s missing=%s",
                tenant_id,
                exc.missing_fields,
            )
            result["status"] = "validation_error"
            result["error"]  = str(exc)
            result["missing_fields"] = exc.missing_fields
            return result

        logger.info(
            "DeskOnboardingService: Step 1 OK — %d field(s) validated.",
            len(knowledge_fields),
        )

        # ── Step 2: Register tenant ────────────────────────────────────────
        logger.info(
            "DeskOnboardingService.setup_new_client: STEP 2 — registering tenant=%s.",
            tenant_id,
        )
        tenant = Tenant(
            tenant_id=tenant_id,
            business_name=business_name,
            sector=sector,
            plan=plan,
            whatsapp_phone_number_id=meta_phone_id or "",
            created_at=datetime.now(tz=timezone.utc),
            persona=persona,
            telegram_token=telegram_token,
        )
        try:
            self._tenant_mgr.create_tenant(tenant)
            logger.info("DeskOnboardingService: Step 2 OK — tenant created.")
        except TenantAlreadyExistsError:
            logger.warning(
                "DeskOnboardingService: tenant=%s already exists — idempotent skip.",
                tenant_id,
            )
        except Exception as exc:
            logger.error(
                "DeskOnboardingService: tenant creation FAILED tenant=%s — %s",
                tenant_id,
                exc,
            )
            result["status"] = "tenant_error"
            result["error"]  = str(exc)
            return result

        # ── Step 3: Ingest knowledge into RAG ─────────────────────────────
        logger.info(
            "DeskOnboardingService.setup_new_client: STEP 3 — ingesting %d field(s) into RAG.",
            len(knowledge_fields),
        )
        try:
            indexed = self._rag.ingest_fields(tenant_id, knowledge_fields)
            result["knowledge_fields_ingested"] = indexed
            logger.info("DeskOnboardingService: Step 3 OK — RAG ingestion complete (%d indexed).", indexed)
        except Exception as exc:
            logger.error(
                "DeskOnboardingService: RAG ingestion FAILED tenant=%s — %s",
                tenant_id,
                exc,
            )
            result["status"] = "rag_error"
            result["error"]  = str(exc)
            return result

        # ── Step 4: Register WhatsApp number ──────────────────────────────
        logger.info(
            "DeskOnboardingService.setup_new_client: STEP 4 — registering WhatsApp number=%s.",
            phone_number,
        )
        try:
            phone_number_id = self._wa.add_phone_number(
                phone_number=phone_number,
                display_name=business_name,
            )
            result["phone_number_id"] = phone_number_id

            # Persist the phone_number_id back onto the tenant record
            try:
                self._tenant_mgr.update_whatsapp_phone_number_id(tenant_id, phone_number_id)
                logger.info(
                    "DeskOnboardingService: phone_number_id=%s saved to tenant=%s.",
                    phone_number_id,
                    tenant_id,
                )
            except Exception as upd_exc:
                logger.warning(
                    "DeskOnboardingService: could not update phone_number_id on tenant — %s",
                    upd_exc,
                )

            logger.info(
                "DeskOnboardingService: Step 4 OK — phone_number_id=%s",
                phone_number_id,
            )
        except WhatsAppAPIError as exc:
            logger.error(
                "DeskOnboardingService: WhatsApp registration FAILED tenant=%s — %s",
                tenant_id,
                exc,
            )
            result["status"] = "whatsapp_error"
            result["error"]  = str(exc)
            return result

        # ── Step 5: Success ────────────────────────────────────────────────
        result["status"] = "pending_verification"
        logger.info(
            "DeskOnboardingService.setup_new_client: SUCCESS tenant=%s phone_id=%s "
            "fields_ingested=%d status=pending_verification.",
            tenant_id,
            result["phone_number_id"],
            result["knowledge_fields_ingested"],
        )
        return result
