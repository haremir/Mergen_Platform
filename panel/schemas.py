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

    Maps to the Desk product's rich, structured knowledge request.
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
    # Structured business_hours: Dict[str, str] mapping days like "monday" to "09:00-18:00"
    business_hours: Dict[str, str] = Field(
        ...,
        description="Operating hours per day.",
        examples=[{"monday": "09:00-18:00", "tuesday": "09:00-18:00"}],
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
    # List of FAQs: list of dicts mapping "question" to "answer"
    faqs: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of frequently asked questions with answers.",
        examples=[[{"question": "Randevu iptal edilebilir mi?", "answer": "Evet, 24 saat kalana kadar."}]],
    )
    # List of Services: list of dicts containing "name", "price", "description"
    services: List[Dict[str, str]] = Field(
        ...,
        description="List of offered services with pricing and descriptions.",
        examples=[[{"name": "Haircut", "price": "150 TL", "description": "Classic hair cutting."}]],
    )
    pricing: Optional[str] = Field(
        default=None,
        description="Generic pricing notes or overall price list text.",
        examples=["Haircut: 150 TL, Beard trim: 80 TL"],
    )
    plan: Optional[str] = Field(
        default="starter",
        description="Subscription plan slug.",
        examples=["starter", "business", "enterprise"],
    )
    product: str = Field(
        default="desk",
        description="Mergen product code.",
        examples=["desk"],
    )
    sector: str = Field(
        ...,
        description="Business sector category.",
        examples=["hairdresser"],
    )
    persona: str = Field(
        ...,
        description="Yapay zeka asistanı karakter/persona kodu.",
        examples=["friendly_energetic"],
    )
    meta_phone_id: str = Field(
        ...,
        description="Meta cloud API phone number ID.",
        examples=["104857204857302"],
    )
    meta_access_token: Optional[str] = Field(
        default=None,
        description="Meta temporary access token override.",
        examples=["EAAx2..."],
    )

    @field_validator("business_name", "phone_number", "location", 
                     "cancellation_policy", "contact_info", "product",
                     "sector", "persona", "meta_phone_id", "meta_access_token", mode="before")
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
# Dashboard Control / Settings
# ---------------------------------------------------------------------------

class DashboardControlRequest(BaseModel):
    """Payload to configure real-time tenant settings."""

    bot_active: bool = Field(
        default=True,
        description="Toggle bot active processing state.",
    )
    system_prompt_override: Optional[str] = Field(
        default=None,
        description="Custom system persona prompt override.",
    )


class DashboardControlResponse(BaseModel):
    """Response for updating tenant settings."""

    status: str = "success"
    message: str
    tenant_id: str
    bot_active: bool
    system_prompt_override: Optional[str] = None


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
    version: str = "7.3.0"
    service: str = "Mergen Panel API"
