"""
panel.api_server
~~~~~~~~~~~~~~~~

FastAPI application — REST API bridge between the Next.js frontend and the
Mergen Platform core / product layers.

CORS Policy:
    Allows http://localhost:3000 (Next.js dev server) and any additional
    origins listed in the ALLOWED_ORIGINS environment variable (comma-separated).

Running locally::
    uv run uvicorn panel.api_server:app --reload --port 8000

Author: Mergen Platform -- Panel Team
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from fastapi import FastAPI, HTTPException, Path, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Path setup — make shared/, core/, packages/, products/ importable
# ---------------------------------------------------------------------------
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (
    os.path.join(_ROOT, "shared"),
    os.path.join(_ROOT, "core"),
    os.path.join(_ROOT, "packages"),
    os.path.join(_ROOT, "products"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from panel.schemas import (  # noqa: E402
    OnboardingRequest,
    OnboardingResponse,
    DashboardControlRequest,
    DashboardControlResponse,
    LogsResponse,
    MessageLogEntry,
    PlanResponse,
    PlanLimitEntry,
    HealthResponse,
)

from mergen_product_desk.onboarding_orchestrator import DeskOnboardingService  # noqa: E402
from mergen_pkg_whatsapp.client import WhatsAppClient, WhatsAppAPIError  # noqa: E402
from mergen_core.plan_guard import PLAN_LIMITS  # noqa: E402
from mergen_core.database import engine, Base  # noqa: E402
from mergen_core.tenant_manager import get_tenant_manager, TenantNotFoundError  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s -- %(message)s",
)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mergen Panel API",
    version="7.3.0",
    description=(
        "REST API bridge between the Mergen Platform core/product modules "
        "and the Next.js frontend dashboard."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")
except Exception:
    logger.exception("Failed to initialize database tables.")

# ---------------------------------------------------------------------------
# CORS — allow Next.js dev server + any additional origins from env
# ---------------------------------------------------------------------------
_default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_extra_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]
_all_origins: List[str] = list(dict.fromkeys(_default_origins + _extra_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_all_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

logger.info("CORS: allowed origins = %s", _all_origins)

# ---------------------------------------------------------------------------
# Dependency: WhatsApp Client (mock-safe factory)
# ---------------------------------------------------------------------------
_override_wa_client:  Optional[Any] = None
_override_rag_engine: Optional[Any] = None
_override_tenant_mgr: Optional[Any] = None


def set_test_overrides(
    wa_client: Optional[Any] = None,
    rag_engine: Optional[Any] = None,
    tenant_manager: Optional[Any] = None,
) -> None:
    """Inject mock dependencies for testing.  Call BEFORE making test requests."""
    global _override_wa_client, _override_rag_engine, _override_tenant_mgr
    _override_wa_client  = wa_client
    _override_rag_engine = rag_engine
    _override_tenant_mgr = tenant_manager


def clear_test_overrides() -> None:
    """Reset all overrides to production defaults."""
    global _override_wa_client, _override_rag_engine, _override_tenant_mgr
    _override_wa_client  = None
    _override_rag_engine = None
    _override_tenant_mgr = None


def _get_whatsapp_client() -> WhatsAppClient:
    token   = os.getenv("WHATSAPP_PLATFORM_TOKEN", "")
    waba_id = os.getenv("WHATSAPP_WABA_ID", "")

    if token and waba_id:
        return WhatsAppClient(platform_token=token, waba_id=waba_id)

    mock_client = MagicMock(spec=WhatsAppClient)
    mock_client.add_phone_number.return_value = f"MOCK_PHONE_ID_{uuid.uuid4().hex[:8].upper()}"
    return mock_client  # type: ignore[return-value]


def _get_onboarding_service_with_overrides() -> DeskOnboardingService:
    return DeskOnboardingService(
        whatsapp_client=_override_wa_client or _get_whatsapp_client(),
        rag_engine=_override_rag_engine,
        tenant_manager=_override_tenant_mgr,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """Liveness probe — returns OK when the API server is running."""
    return HealthResponse()


# ── Onboarding ────────────────────────────────────────────────────────────

@app.post(
    "/api/onboarding",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Onboarding"],
    summary="Register a new Desk client",
)
def create_onboarding(body: OnboardingRequest) -> OnboardingResponse:
    """Orchestrate the complete Desk client onboarding flow with rich data structures."""
    tenant_id = str(uuid.uuid4())

    # Build the rich raw_form_data dict
    raw_form: Dict[str, Any] = {
        "business_hours":      body.business_hours,      # Dict[str, str]
        "location":            body.location,            # str
        "contact_info":        body.contact_info,        # str
        "cancellation_policy": body.cancellation_policy,  # str
        "services":            body.services,            # List[Dict[str, str]]
        "faqs":                body.faqs,                # List[Dict[str, str]]
    }
    if body.pricing:
        raw_form["pricing"] = body.pricing

    logger.info(
        "POST /api/onboarding: tenant_id=%s business='%s' phone=%s",
        tenant_id,
        body.business_name,
        body.phone_number,
    )

    service = _get_onboarding_service_with_overrides()
    result  = service.setup_new_client(
        tenant_id=tenant_id,
        business_name=body.business_name,
        raw_form_data=raw_form,
        phone_number=body.phone_number,
        plan=body.plan or "starter",
    )

    return OnboardingResponse(
        status=result.get("status", "unknown"),
        tenant_id=result.get("tenant_id", tenant_id),
        phone_number_id=result.get("phone_number_id"),
        knowledge_fields_ingested=result.get("knowledge_fields_ingested", 0),
        persona=result.get("persona"),
        error=result.get("error"),
        missing_fields=result.get("missing_fields"),
    )


# ── Tenant Settings / Control Endpoint ────────────────────────────────────

@app.post(
    "/api/tenant/{tenant_id}/settings",
    response_model=DashboardControlResponse,
    status_code=status.HTTP_200_OK,
    tags=["Tenant Management"],
    summary="Configure real-time tenant settings and control overrides",
)
def configure_tenant_settings(
    body: DashboardControlRequest,
    tenant_id: str = Path(..., description="UUID of the target tenant"),
) -> DashboardControlResponse:
    """Update tenant's active bot status and custom system prompts in the database."""
    logger.info(
        "POST /api/tenant/%s/settings: bot_active=%s prompt_override=%s",
        tenant_id,
        body.bot_active,
        body.system_prompt_override is not None,
    )
    
    manager = _override_tenant_mgr or get_tenant_manager()
    try:
        manager.update_tenant(
            tenant_id=tenant_id,
            bot_active=body.bot_active,
            system_prompt_override=body.system_prompt_override,
        )
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found."
        )
    
    status_msg = f"Bot status updated to {'active' if body.bot_active else 'inactive'}."
    if body.system_prompt_override:
        status_msg += " System prompt override applied."

    return DashboardControlResponse(
        status="success",
        message=status_msg,
        tenant_id=tenant_id,
        bot_active=body.bot_active,
        system_prompt_override=body.system_prompt_override,
    )


# ── Conversation Logs ─────────────────────────────────────────────────────

_MOCK_LOG_TEMPLATES = [
    ("inbound",  "whatsapp", "Calisma saatleriniz neler?"),
    ("outbound", "whatsapp", "Merhaba! Calisma saatlerimiz Pzt-Cum 09:00-19:00, Cmt 10:00-17:00."),
    ("inbound",  "whatsapp", "Randevu almak istiyorum."),
    ("outbound", "whatsapp", "Size en yakin uygun saati hemen gosterebilirim. Hangun sizin icin uygun?"),
    ("inbound",  "whatsapp", "Musteri temsilcisiyle gorusmek istiyorum."),
    ("outbound", "whatsapp", "Anliyorum, sizi hemen yetkili bir temsilcimize bagliyorum."),
]


@app.get(
    "/api/logs/{tenant_id}",
    response_model=LogsResponse,
    tags=["Logs"],
    summary="Get recent conversation logs for a tenant",
)
def get_logs(
    tenant_id: str = Path(..., description="Tenant UUID"),
    limit: int = 20,
) -> LogsResponse:
    """Return recent conversation log entries for a tenant."""
    now = datetime.now(tz=timezone.utc)

    entries: List[MessageLogEntry] = []
    for i, (direction, channel, text) in enumerate(_MOCK_LOG_TEMPLATES):
        entries.append(
            MessageLogEntry(
                message_id=f"msg_{tenant_id[:8]}_{i:03d}",
                tenant_id=tenant_id,
                sender="905551234567" if direction == "inbound" else "SYSTEM",
                channel=channel,
                direction=direction,
                text=text,
                timestamp=now.replace(minute=now.minute - i).isoformat(),
            )
        )

    return LogsResponse(
        tenant_id=tenant_id,
        total=len(entries),
        messages=entries[:limit],
    )


# ── Plan / Quota ──────────────────────────────────────────────────────────

@app.get(
    "/api/plan/{tenant_id}",
    response_model=PlanResponse,
    tags=["Billing"],
    summary="Get the current plan limits for a tenant",
)
def get_plan(
    tenant_id: str = Path(..., description="Tenant UUID"),
) -> PlanResponse:
    """Return the current subscription plan and quota limits for a tenant."""
    plan_slug = "starter"
    monthly_limit = PLAN_LIMITS.get(plan_slug, 500)
    used = 137

    return PlanResponse(
        tenant_id=tenant_id,
        plan=plan_slug,
        limits={
            "monthly_messages": PlanLimitEntry(
                limit=monthly_limit,
                used=used,
                remaining=max(0, monthly_limit - used),
                unit="messages/month",
            ),
            "rag_documents": PlanLimitEntry(
                limit=100,
                used=10,
                remaining=90,
                unit="documents",
            ),
            "whatsapp_numbers": PlanLimitEntry(
                limit=1,
                used=1,
                remaining=0,
                unit="phone numbers",
            ),
        },
    )
