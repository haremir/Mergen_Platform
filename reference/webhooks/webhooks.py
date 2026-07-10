"""FastAPI-based webhook server for WhatsApp and Instagram channels in dent_bot.

Security Model
--------------
The WhatsApp webhook endpoint implements a **three-layer security firewall**:

Layer 1 — Cryptographic Signature Verification
    Every POST from Meta carries an ``X-Hub-Signature-256`` header.
    Its value is ``sha256=<hmac_hex>`` where the HMAC-SHA256 is computed over
    the raw request body using ``META_APP_SECRET`` as the key.
    Requests without a valid signature are rejected with HTTP 401 immediately,
    before any payload parsing or DB access.

Layer 2 — Multi-Tenant DB Routing
    The ``metadata.phone_number_id`` is extracted from the verified payload
    and used to look up the clinic record via ``get_clinic_by_phone_number_id``.
    Only clinics with ``whatsapp_active = TRUE`` are resolved.  Unknown or
    inactive phone_number_ids result in a silent HTTP 200 + drop (to prevent
    Meta retry floods).

Layer 3 — Instant 200 + BackgroundTasks
    Meta requires an HTTP 200 response within 5 seconds or it retries.
    The POST handler returns 200 immediately and pushes all message processing
    (DB lookup, engine dispatch, reply sending) into FastAPI ``BackgroundTasks``.

New vs. Old endpoint
--------------------
The old ``GET /webhooks/whatsapp`` / ``POST /webhooks/whatsapp`` handlers remain
intact (they handle the legacy single-tenant path).  The new *security-hardened*
endpoints are mounted at:
    GET  /webhook/whatsapp   (note: singular — Meta Dashboard canonical path)
    POST /webhook/whatsapp

The legacy ``/webhooks/whatsapp`` (plural) routes are kept for backward compatibility
but will emit a deprecation log warning on POST.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from dentbot.config import get_config
from dentbot.conversation import ConversationEngine
from dentbot.conversation.flow_handlers import (
    AnamnesisHandler,
    AppointmentHandler,
    SelfServiceHandler,
)
from dentbot.channels.whatsapp import WhatsAppTransport
from dentbot.channels.instagram import InstagramTransport
from dentbot.tools import get_adapter
from dentbot.services.tenant_resolution import get_tenant_resolver
from dentbot.services.context_service import (
    set_active_tenant_id,
    reset_active_tenant_id,
    get_active_tenant_id,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TenantRoutingMiddleware — ASGI middleware for HTTP-level tenant injection
# ---------------------------------------------------------------------------

class TenantRoutingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that extracts the tenant ID from the X-Tenant-ID HTTP
    header and injects it into the ContextVar for the lifetime of the request.

    Isolation guarantee: BaseHTTPMiddleware wraps each request in its own
    async task, so the ContextVar value set here is invisible to all other
    concurrent requests — by Python's contextvars design.

    Priority:
      1. X-Tenant-ID header value (explicit per-request override)
      2. TenantResolutionService fallback (ACTIVE_TENANT_ID env var)
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        tenant_id = request.headers.get("X-Tenant-ID", "").strip()

        if not tenant_id:
            # Fall back to the global env default
            try:
                tenant_id = get_config().get_active_tenant_id()
            except Exception:
                tenant_id = os.getenv("ACTIVE_TENANT_ID", "")

        token = set_active_tenant_id(tenant_id)
        try:
            response = await call_next(request)
        finally:
            reset_active_tenant_id(token)

        return response


# ---------------------------------------------------------------------------
# TelemetryMiddleware — invisible AIOps request latency recorder
# ---------------------------------------------------------------------------

class TelemetryMiddleware(BaseHTTPMiddleware):
    """
    Fire-and-forget HTTP middleware that records per-request latency into the
    ``system_metrics`` table without touching the response in any way.

    Implementation notes:
    - Uses ``asyncio.create_task()`` so the DB insert runs after the response
      is already returned to the client (truly non-blocking).
    - ``call_next(request)`` is awaited and the *original* response object is
      returned unchanged — status code, headers, and body are untouched.
    - All exceptions inside the background task are swallowed by
      ``record_metric`` itself (see ``dentbot.core.telemetry``).
    - Does NOT record metrics for health-check / docs paths to avoid noise.
    """

    # Paths that generate high-frequency noise with no diagnostic value
    _SKIP_PATHS = frozenset(["/health", "/docs", "/openapi.json", "/redoc"])

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        path = request.url.path
        if path not in self._SKIP_PATHS:
            try:
                from dentbot.core.telemetry import record_metric
                from dentbot.services.context_service import get_active_tenant_id

                try:
                    tenant_id: Optional[str] = get_active_tenant_id()
                except Exception:
                    tenant_id = None

                asyncio.create_task(
                    record_metric(
                        "api_request",
                        round(elapsed_ms, 3),
                        tenant_id=tenant_id,
                        metadata={
                            "path": path,
                            "method": request.method,
                            "status_code": response.status_code,
                        },
                    )
                )
            except Exception:  # pragma: no cover
                # If task creation itself fails, silently ignore.
                pass

        return response  # ← 100% original response, untouched


# ---------------------------------------------------------------------------
# FastAPI Application Factory
# ---------------------------------------------------------------------------

app = FastAPI(title="DentBot Gateway", version="1.0.0")

# ---------------------------------------------------------------------------
# CORS — required for Next.js browser clients calling /api/* from localhost:3000
# ---------------------------------------------------------------------------
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001")
_allowed_origins: List[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-ID"],
    expose_headers=["X-Request-ID"],
    max_age=600,  # Preflight cache: 10 minutes
)

app.add_middleware(TenantRoutingMiddleware)
app.add_middleware(TelemetryMiddleware)  # ← AIOps: silent request latency recorder

# ---------------------------------------------------------------------------
# Mount API routers (JWT auth + admin endpoints)
# ---------------------------------------------------------------------------
try:
    from dentbot.api import create_api_router
    app.include_router(create_api_router())
    logger.info("JWT auth router mounted at /api/auth")
except Exception as _api_exc:
    logger.warning("Could not mount API router: %s", _api_exc)


# ---------------------------------------------------------------------------
# Session State Store
# ---------------------------------------------------------------------------
# In-memory per-session state. For production at scale, replace with Redis.
_session_states: Dict[str, Dict[str, Any]] = {}

_engine: Optional[ConversationEngine] = None
_whatsapp_transport: Optional[WhatsAppTransport] = None
_instagram_transport: Optional[InstagramTransport] = None


# ---------------------------------------------------------------------------
# Lazy Singletons
# ---------------------------------------------------------------------------

def get_conversation_engine() -> ConversationEngine:
    global _engine
    if _engine is None:
        from dentbot.channels.telegram import get_llm, _fallback_llm
        _engine = ConversationEngine(
            adapter=get_adapter(),
            config=get_config(),
            llm=get_llm(),
            fallback_llm=_fallback_llm,
        )
    return _engine


def get_whatsapp_transport() -> WhatsAppTransport:
    global _whatsapp_transport
    if _whatsapp_transport is None:
        _whatsapp_transport = WhatsAppTransport()
    return _whatsapp_transport


def get_instagram_transport() -> InstagramTransport:
    global _instagram_transport
    if _instagram_transport is None:
        _instagram_transport = InstagramTransport()
    return _instagram_transport


def _get_user_state(session_key: str) -> Dict[str, Any]:
    if session_key not in _session_states:
        _session_states[session_key] = {}
    return _session_states[session_key]


# ---------------------------------------------------------------------------
# Signature Verification (Layer 1 — Cryptographic Firewall)
# ---------------------------------------------------------------------------

def _verify_meta_signature(raw_body: bytes, signature_header: str, app_secret: str) -> bool:
    """Verify the ``X-Hub-Signature-256`` header sent by Meta.

    Meta computes:
        HMAC-SHA256(key=APP_SECRET, message=raw_body_bytes)
    and sends it as ``sha256=<hex_digest>`` in the ``X-Hub-Signature-256`` header.

    This function replicates that computation and performs a **constant-time
    comparison** (via ``hmac.compare_digest``) to prevent timing-oracle attacks.

    Args:
        raw_body:         The unmodified raw request body bytes.
        signature_header: Value of the ``X-Hub-Signature-256`` header.
        app_secret:       ``META_APP_SECRET`` environment variable value.

    Returns:
        ``True`` if the signature is valid, ``False`` otherwise.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    received_sig = signature_header[len("sha256="):]

    expected_sig = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_sig, received_sig)


def _get_app_secret() -> str:
    """Resolve META_APP_SECRET from config or env, with a graceful fallback."""
    try:
        return get_config().get_meta_app_secret()
    except Exception:
        return os.getenv("META_APP_SECRET", "")


def _get_verify_token() -> str:
    """Resolve META_VERIFY_TOKEN from config or env, with a graceful fallback."""
    try:
        return get_config().get_meta_verify_token()
    except Exception:
        return (
            os.getenv("META_VERIFY_TOKEN")
            or os.getenv("WHATSAPP_VERIFY_TOKEN")
            or "dentbot_verify_token"
        )


# ---------------------------------------------------------------------------
# Payload Extraction Helpers
# ---------------------------------------------------------------------------

def _extract_whatsapp_phone_number_id(payload: Dict) -> Optional[str]:
    """Extract the ``metadata.phone_number_id`` from a Meta WhatsApp webhook payload."""
    try:
        entry = payload.get("entry", [])
        if not entry:
            return None
        changes = entry[0].get("changes", [])
        if not changes:
            return None
        value = changes[0].get("value", {})
        return (
            value.get("metadata", {}).get("phone_number_id")
            or value.get("phone_number_id")
        )
    except Exception:
        return None


def _extract_instagram_page_id(payload: Dict) -> Optional[str]:
    """Extract the page_id / instagram business account id from the payload."""
    try:
        entry = payload.get("entry", [])
        if not entry:
            return None
        return str(entry[0].get("id", "")) or None
    except Exception:
        return None


def _resolve_and_inject_tenant(channel: str, identifier: Optional[str]) -> Optional[str]:
    """Resolve tenant_id for the given channel identifier.

    If the TenantRoutingMiddleware already set a non-empty value (via
    X-Tenant-ID header), that value is used as-is (higher priority).

    Returns the resolved tenant_id, or None on failure.
    """
    existing = get_active_tenant_id()
    if existing:
        return existing

    if not identifier:
        try:
            fallback = get_config().get_active_tenant_id()
        except Exception:
            fallback = os.getenv("ACTIVE_TENANT_ID", "")
        if fallback:
            set_active_tenant_id(fallback)
        return fallback or None

    resolver = get_tenant_resolver()
    tenant_id = resolver.resolve(channel, identifier)
    if tenant_id:
        set_active_tenant_id(tenant_id)
    return tenant_id


# ---------------------------------------------------------------------------
# Background Task: Multi-Tenant WhatsApp Message Processor
# ---------------------------------------------------------------------------

async def _process_whatsapp_message(
    payload: Dict[str, Any],
    phone_number_id: str,
    tenant_id: str,
    tenant_token: str,
) -> None:
    """Background task: parse and dispatch a verified WhatsApp message.

    This runs AFTER the HTTP 200 has already been returned to Meta.
    Any exception here is caught and logged — it must never propagate upward.

    Args:
        payload:          Verified, parsed Meta webhook JSON.
        phone_number_id:  Routing key (already resolved).
        tenant_id:        UUID string of the owning clinic.
        tenant_token:     Decrypted permanent access token for the tenant's
                          WhatsApp Business phone number.  Used to instantiate
                          a per-tenant ``WhatsAppTransport``.
    """
    try:
        # Inject tenant context for downstream services
        set_active_tenant_id(tenant_id)

        # Build a per-tenant transport using the clinic's own token
        transport = WhatsAppTransport(
            token=tenant_token,
            phone_number_id=phone_number_id,
        )
        parsed = transport.parse_update(payload)

        if not parsed or not parsed.get("chat_id") or not parsed.get("text"):
            logger.debug(
                "_process_whatsapp_message [%s]: non-message event, skipping.",
                tenant_id,
            )
            return

        chat_id = parsed["chat_id"]
        user_text = parsed["text"]
        user_name = parsed.get("first_name") or "WhatsApp Patient"

        session_key = f"whatsapp:{tenant_id}:{chat_id}"
        state = _get_user_state(session_key)

        engine = get_conversation_engine()
        engine.register_handlers(
            anamnesis=AnamnesisHandler(state),
            appointment=AppointmentHandler(state, engine.adapter),
            self_service=SelfServiceHandler(state, engine.adapter),
        )

        async def send_fn(text: str) -> None:
            await asyncio.to_thread(transport.send_message, chat_id, text)

        state["channel"] = "whatsapp"
        state["patient_chat_id"] = str(chat_id)
        state["tenant_id"] = tenant_id

        async def callback(aggregated_text: str) -> None:
            try:
                response = await engine.handle(
                    user_message=aggregated_text,
                    chat_id=chat_id,
                    state=state,
                    user_name=user_name,
                    send_fn=send_fn,
                )
                if response:
                    await send_fn(response)
            except Exception as exc:
                logger.error(
                    "_process_whatsapp_message callback [%s]: %s",
                    tenant_id,
                    exc,
                    exc_info=True,
                )
                await send_fn("Sistem şu an yoğun, lütfen daha sonra tekrar deneyin.")

        from dentbot.services.message_buffer import MessageBufferService
        await MessageBufferService.add_message(
            tenant_id=tenant_id,
            channel="whatsapp",
            user_id=str(chat_id),
            text=user_text,
            callback=callback,
        )

    except Exception as exc:
        logger.error(
            "_process_whatsapp_message [%s]: unhandled error — %s",
            tenant_id,
            exc,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# NEW: Security-Hardened WhatsApp Webhooks  GET /webhook/whatsapp
#                                           POST /webhook/whatsapp
# (Singular path — canonical Meta App Dashboard configuration)
# ---------------------------------------------------------------------------

@app.get("/webhook/whatsapp", response_class=PlainTextResponse)
def verify_whatsapp_secure(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Meta webhook verification endpoint (GET /webhook/whatsapp).

    Meta sends this request when you first configure the webhook URL in the
    App Dashboard.  Returns the ``hub.challenge`` integer as plain text when
    the ``hub.verify_token`` matches ``META_VERIFY_TOKEN``.

    HTTP 403 is returned for any mismatch so the App Dashboard reports a
    clear failure rather than silently misconfiguring the subscription.
    """
    expected_token = _get_verify_token()
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("WhatsApp webhook verification successful (GET /webhook/whatsapp).")
        return hub_challenge
    logger.warning(
        "WhatsApp webhook verification FAILED: hub_mode=%r, token_match=%r",
        hub_mode,
        hub_verify_token == expected_token,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid verification token")


@app.post("/webhook/whatsapp")
async def receive_whatsapp_secure(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Meta message receiver with full cryptographic firewall.

    Layer 1 — Signature verification
        Reads the raw body bytes and validates ``X-Hub-Signature-256`` using
        ``META_APP_SECRET``.  Rejects with HTTP 401 on any mismatch.

    Layer 2 — Multi-tenant DB routing
        Extracts ``phone_number_id`` from the verified payload and calls
        ``get_clinic_by_phone_number_id`` to find the owning clinic.
        Unknown phone numbers → silent HTTP 200 (prevents retry floods).

    Layer 3 — Instant 200 + background processing
        Returns HTTP 200 immediately, then dispatches
        ``_process_whatsapp_message`` as a FastAPI ``BackgroundTask``.
    """
    # ── Layer 1: Read raw bytes for signature check ───────────────────────
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256", "")

    app_secret = _get_app_secret()
    if not app_secret:
        logger.error(
            "receive_whatsapp_secure: META_APP_SECRET is not configured — "
            "rejecting all incoming webhooks until secret is set."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook security is not configured on this server.",
        )

    if not _verify_meta_signature(raw_body, signature_header, app_secret):
        logger.warning(
            "receive_whatsapp_secure: INVALID X-Hub-Signature-256 — "
            "request rejected. header=%r",
            signature_header[:30] if signature_header else "(missing)",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Hub-Signature-256 validation failed.",
        )

    # ── Layer 2: Parse payload and resolve tenant from DB ─────────────────
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        # Body was already consumed above; re-parse from bytes
        import json as _json
        try:
            payload = _json.loads(raw_body)
        except Exception as exc:
            logger.warning("receive_whatsapp_secure: could not parse JSON body — %s", exc)
            return {"status": "ignored", "reason": "invalid_json"}

    phone_number_id = _extract_whatsapp_phone_number_id(payload)
    if not phone_number_id:
        logger.debug(
            "receive_whatsapp_secure: no phone_number_id in payload — dropping silently."
        )
        return {"status": "ok"}

    adapter = get_adapter()
    if adapter is None:
        logger.error("receive_whatsapp_secure: adapter unavailable — dropping message.")
        return {"status": "ok"}

    clinic = None
    try:
        clinic = adapter.get_clinic_by_phone_number_id(phone_number_id)
    except Exception as exc:
        logger.error(
            "receive_whatsapp_secure: DB lookup error for phone_number_id=%s — %s",
            phone_number_id,
            exc,
        )

    if not clinic:
        logger.warning(
            "receive_whatsapp_secure: no active clinic for phone_number_id=%s — dropping.",
            phone_number_id,
        )
        return {"status": "ok"}

    tenant_id = str(clinic.get("id", ""))
    if not tenant_id:
        logger.error(
            "receive_whatsapp_secure: clinic row has no id for phone_number_id=%s.",
            phone_number_id,
        )
        return {"status": "ok"}

    # Decrypt the per-tenant WhatsApp token
    encrypted_token: Optional[str] = clinic.get("whatsapp_token")
    tenant_token = ""
    if encrypted_token:
        try:
            from dentbot.crypto import decrypt_token
            tenant_token = decrypt_token(encrypted_token)
        except Exception as exc:
            logger.error(
                "receive_whatsapp_secure: could not decrypt token for tenant %s — %s",
                tenant_id,
                exc,
            )
            # Proceed without token — the per-tenant transport will fail gracefully
            tenant_token = ""

    # ── Layer 3: Return 200 immediately, process in background ───────────
    background_tasks.add_task(
        _process_whatsapp_message,
        payload,
        phone_number_id,
        tenant_id,
        tenant_token,
    )

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# LEGACY: WhatsApp Webhooks  (plural path — kept for backward compatibility)
# GET  /webhooks/whatsapp
# POST /webhooks/whatsapp
# ---------------------------------------------------------------------------

@app.get("/webhooks/whatsapp", response_class=PlainTextResponse)
def verify_whatsapp(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """WhatsApp webhook verification endpoint (legacy plural path)."""
    config = get_config()
    expected_token = (
        os.getenv("WHATSAPP_VERIFY_TOKEN")
        or getattr(config, "_env", {}).get("WHATSAPP_VERIFY_TOKEN")
        or "dentbot_verify_token"
    )
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("WhatsApp webhook verified successfully!")
        return hub_challenge
    raise HTTPException(status_code=403, detail="Invalid verification token")


@app.post("/webhooks/whatsapp")
async def receive_whatsapp(request: Request):
    """Handles incoming WhatsApp messages (legacy plural path, no signature check).

    .. deprecated::
        Use ``POST /webhook/whatsapp`` (singular) which implements the full
        X-Hub-Signature-256 cryptographic firewall and DB-driven multi-tenant routing.
    """
    logger.warning(
        "DEPRECATED: POST /webhooks/whatsapp (plural) received a request. "
        "Please reconfigure Meta App Dashboard to use POST /webhook/whatsapp (singular)."
    )
    payload = await request.json()
    logger.debug("Received WhatsApp Webhook Payload (legacy): %s", payload)

    # ── Tenant Resolution ──────────────────────────────────────────────────
    phone_number_id = _extract_whatsapp_phone_number_id(payload)
    tenant_id = _resolve_and_inject_tenant("whatsapp", phone_number_id)
    if not tenant_id:
        logger.warning(
            "receive_whatsapp: could not resolve tenant for phone_number_id=%s — ignoring.",
            phone_number_id,
        )
        return {"status": "ignored", "reason": "unresolvable_tenant"}

    # ── Message Parsing ────────────────────────────────────────────────────
    whatsapp_transport = get_whatsapp_transport()
    parsed = whatsapp_transport.parse_update(payload)

    if not parsed or not parsed.get("chat_id") or not parsed.get("text"):
        return {"status": "ignored"}

    chat_id = parsed["chat_id"]
    user_text = parsed["text"]
    user_name = parsed["first_name"] or "WhatsApp Patient"

    session_key = f"whatsapp:{chat_id}"
    state = _get_user_state(session_key)

    engine = get_conversation_engine()
    engine.register_handlers(
        anamnesis=AnamnesisHandler(state),
        appointment=AppointmentHandler(state, engine.adapter),
        self_service=SelfServiceHandler(state, engine.adapter),
    )

    async def send_fn(text: str) -> None:
        await asyncio.to_thread(whatsapp_transport.send_message, chat_id, text)

    state["channel"] = "whatsapp"
    state["patient_chat_id"] = str(chat_id)
    state["tenant_id"] = tenant_id  # persist in session for continuity

    async def callback(aggregated_text: str):
        try:
            response = await engine.handle(
                user_message=aggregated_text,
                chat_id=chat_id,
                state=state,
                user_name=user_name,
                send_fn=send_fn,
            )
            if response:
                await send_fn(response)
        except Exception as e:
            logger.error("Error in WhatsApp message processing callback: %s", e, exc_info=True)
            await send_fn("Sistem şu an yoğun, lütfen daha sonra tekrar deneyin.")

    from dentbot.services.message_buffer import MessageBufferService
    await MessageBufferService.add_message(
        tenant_id=tenant_id,
        channel="whatsapp",
        user_id=str(chat_id),
        text=user_text,
        callback=callback
    )

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Instagram Webhooks
# ---------------------------------------------------------------------------

@app.get("/webhooks/instagram", response_class=PlainTextResponse)
def verify_instagram(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Instagram webhook verification endpoint."""
    config = get_config()
    expected_token = (
        os.getenv("INSTAGRAM_VERIFY_TOKEN")
        or getattr(config, "_env", {}).get("INSTAGRAM_VERIFY_TOKEN")
        or "dentbot_verify_token"
    )
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("Instagram webhook verified successfully!")
        return hub_challenge
    raise HTTPException(status_code=403, detail="Invalid verification token")


@app.post("/webhooks/instagram")
async def receive_instagram(request: Request):
    """Handles incoming Instagram Direct Messages with per-message tenant isolation."""
    payload = await request.json()
    logger.debug("Received Instagram Webhook Payload: %s", payload)

    # ── Tenant Resolution ──────────────────────────────────────────────────
    page_id = _extract_instagram_page_id(payload)
    tenant_id = _resolve_and_inject_tenant("instagram", page_id)
    if not tenant_id:
        logger.warning(
            "receive_instagram: could not resolve tenant for page_id=%s — ignoring.",
            page_id,
        )
        return {"status": "ignored", "reason": "unresolvable_tenant"}

    # ── Message Parsing ────────────────────────────────────────────────────
    instagram_transport = get_instagram_transport()
    parsed = instagram_transport.parse_update(payload)

    if not parsed or not parsed.get("chat_id") or not parsed.get("text"):
        return {"status": "ignored"}

    chat_id = parsed["chat_id"]
    user_text = parsed["text"]
    user_name = parsed["first_name"] or "Instagram Patient"

    session_key = f"instagram:{chat_id}"
    state = _get_user_state(session_key)

    engine = get_conversation_engine()
    engine.register_handlers(
        anamnesis=AnamnesisHandler(state),
        appointment=AppointmentHandler(state, engine.adapter),
        self_service=SelfServiceHandler(state, engine.adapter),
    )

    async def send_fn(text: str) -> None:
        await asyncio.to_thread(instagram_transport.send_message, chat_id, text)

    state["channel"] = "instagram"
    state["patient_chat_id"] = str(chat_id)
    state["tenant_id"] = tenant_id

    async def callback(aggregated_text: str):
        try:
            response = await engine.handle(
                user_message=aggregated_text,
                chat_id=chat_id,
                state=state,
                user_name=user_name,
                send_fn=send_fn,
            )
            if response:
                await send_fn(response)
        except Exception as e:
            logger.error("Error in Instagram message processing callback: %s", e, exc_info=True)
            await send_fn("Sistem şu an yoğun, lütfen daha sonra tekrar deneyin.")

    from dentbot.services.message_buffer import MessageBufferService
    await MessageBufferService.add_message(
        tenant_id=tenant_id,
        channel="instagram",
        user_id=str(chat_id),
        text=user_text,
        callback=callback
    )

    return {"status": "ok"}
