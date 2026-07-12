"""
panel.schemas
~~~~~~~~~~~~~

Pydantic request/response models for the Mergen Panel API.

IMPORTANT: Pydantic is used ONLY in this file (and the FastAPI layer).
The core and shared packages deliberately avoid Pydantic to stay
framework-agnostic. Do not import Pydantic in any file outside of `panel/`.

Author: Mergen Platform -- Panel Team
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

class OnboardingRequest(BaseModel):
    """Payload for POST /api/onboarding.

    Maps to the Desk product's required knowledge form fields.
    All string fields are stripped of leading/trailing whitespace.
    """

    business_name: str = Field(
        ...,
        min_length=2,
        max_length=120,
        description="Human-readable business display name.",
        examples=["Acme Barber Istanbul"],
    )
    phone_number: str = Field(
        ...,
        min_length=7,
        max_length=20,
        description="E.164 WhatsApp phone number to register (e.g. '+905551234567').",
        examples=["+905551234567"],
    )
    business_hours: str = Field(
        ...,
        min_length=3,
        description="Operating hours (e.g. 'Mon-Fri 09:00-19:00, Sat 10:00-17:00').",
        examples=["Mon-Fri 09:00-19:00, Sat 10:00-17:00"],
    )
    location: str = Field(
        ...,
        min_length=5,
        description="Physical address or directions.",
        examples=["Kadikoy Mah. Ataturk Cad. No:12, Kadikoy/Istanbul"],
    )
    cancellation_policy: str = Field(
        ...,
        min_length=5,
        description="Appointment cancellation policy text.",
        examples=["24 hours advance notice required for cancellations."],
    )
    contact_info: str = Field(
        ...,
        min_length=5,
        description="Phone, e-mail, or social handles for the business.",
        examples=["reception@acme.com | +90 212 555 0000"],
    )
    # Optional enrichment fields
    services: Optional[str] = Field(
        default=None,
        description="Comma-separated list of offered services.",
        examples=["Haircut, Beard trim, Coloring"],
    )
    pricing: Optional[str] = Field(
        default=None,
        description="Pricing table or price range.",
        examples=["Haircut: 150 TL, Beard trim: 80 TL"],
    )
    plan: Optional[str] = Field(
        default="starter",
        description="Subscription plan slug.",
        examples=["starter", "business", "enterprise"],
    )

    @field_validator("business_name", "phone_number", "business_hours",
                     "location", "cancellation_policy", "contact_info",
                     mode="before")
    @classmethod
    def strip_whitespace(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v


class OnboardingResponse(BaseModel):
    """Response for POST /api/onboarding."""

    status: str = Field(description="Onboarding status code.")
    tenant_id: str = Field(description="UUID of the newly created tenant.")
    phone_number_id: Optional[str] = Field(
        default=None,
        description="Meta phone_number_id returned by WhatsApp API (populated on success).",
    )
    knowledge_fields_ingested: int = Field(
        default=0,
        description="Number of knowledge fields indexed into the RAG engine.",
    )
    persona: Optional[str] = Field(default=None)
    error: Optional[str] = Field(default=None)
    missing_fields: Optional[List[str]] = Field(default=None)


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

class MessageLogEntry(BaseModel):
    """A single conversation log entry."""

    message_id: str
    tenant_id: str
    sender: str
    channel: str
    direction: str       # "inbound" | "outbound"
    text: str
    timestamp: str       # ISO-8601


class LogsResponse(BaseModel):
    """Response for GET /api/logs/{tenant_id}."""

    tenant_id: str
    total: int
    messages: List[MessageLogEntry]
    note: str = Field(
        default="Mock data — connect to database for production logs.",
    )


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

class PlanLimitEntry(BaseModel):
    """Limit definition for a single resource."""

    limit: int
    used: int
    remaining: int
    unit: str


class PlanResponse(BaseModel):
    """Response for GET /api/plan/{tenant_id}."""

    tenant_id: str
    plan: str
    limits: Dict[str, PlanLimitEntry]
    note: str = Field(
        default="Mock data — connect to billing service for production plan data.",
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "7.1.0"
    service: str = "Mergen Panel API"
