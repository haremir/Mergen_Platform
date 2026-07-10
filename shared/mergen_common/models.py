"""
mergen_common.models
~~~~~~~~~~~~~~~~~~~~

Shared, strictly-typed, zero-external-dependency dataclasses for the
Mergen Platform monorepo.

Design rules (MUST be enforced on every future edit):
  1. ZERO third-party imports — only `dataclasses`, `typing`, and `datetime`
     from the Python standard library are allowed.
  2. Every dataclass is immutable-by-default (frozen=False but no setattr
     abuse — treat fields as write-once after construction).
  3. All fields have explicit type annotations.
  4. Optional fields use typing.Optional[X] with a default of None.
  5. datetime fields always carry timezone-aware timestamps at the
     application boundary; naive datetimes are acceptable for internal use.

Adapted from proven patterns in the dent_bot project (see reference/):
  - Multi-tenant architecture: every record carries `tenant_id` (str, UUID).
  - Channel abstraction: messages carry a generic `channel` string so the
    same dataclass works for WhatsApp, Telegram, Instagram, etc.
  - KnowledgeField mirrors the RAG knowledge-base row shape used by dent_bot's
    PostgreSQL adapter; it is intentionally flat for easy serialization.

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# InboundMessage
# ---------------------------------------------------------------------------

@dataclass
class InboundMessage:
    """Normalized representation of any message arriving from a channel.

    Created by the channel adapter (e.g. mergen_pkg_whatsapp) immediately
    after the raw webhook payload is verified and parsed. All downstream
    services (conversation engine, RAG pipeline, audit logger) consume this
    struct instead of touching the raw payload.

    Attributes:
        tenant_id:      UUID string of the owning tenant/business.
        channel:        Originating channel slug. Examples: "whatsapp",
                        "telegram", "instagram", "web".
        sender:         Channel-specific sender identifier. For WhatsApp this
                        is the E.164 phone number (e.g. "905551234567"); for
                        Telegram it is the numeric chat_id as a string.
        text:           Decoded plain-text body of the message. Empty string
                        when the message is non-text (image, voice, etc.) --
                        callers must check before processing.
        raw_payload:    Original, unmodified webhook JSON dict for audit trails
                        and future re-processing. Never mutate this dict.
        received_at:    UTC timestamp at which the platform received the
                        message (set by the channel adapter, not by Meta/Telegram).

    Example (WhatsApp)::
        msg = InboundMessage(
            tenant_id="a1b2c3d4-...",
            channel="whatsapp",
            sender="905551234567",
            text="Merhaba, randevu almak istiyorum.",
            raw_payload={...},
            received_at=datetime.utcnow(),
        )
    """

    tenant_id: str
    channel: str
    sender: str
    text: str
    raw_payload: Dict[str, Any]
    received_at: datetime


# ---------------------------------------------------------------------------
# OutboundMessage
# ---------------------------------------------------------------------------

@dataclass
class OutboundMessage:
    """Represents a message to be delivered by a channel transport.

    Produced by the conversation engine or notification service and consumed
    by the appropriate channel transport (e.g. WhatsAppTransport). The
    transport maps `text` to the channel's native send API and, when
    `template_name` is set, switches to a pre-approved template message
    (required by WhatsApp outside the 24-hour customer-service window).

    Attributes:
        tenant_id:      UUID string of the sending tenant/business.
        channel:        Target delivery channel. Must match a registered
                        transport. Examples: "whatsapp", "telegram".
        recipient:      Channel-specific recipient identifier. Mirror of
                        InboundMessage.sender -- use the value you received.
        text:           Message body to send. When `template_name` is set,
                        this field is used as the fallback body or ignored
                        depending on the transport.
        template_name:  Optional pre-approved template identifier. Required
                        by WhatsApp for messages sent outside the 24-hour
                        customer-initiated conversation window. Leave None
                        for free-form text replies within the window.

    Example (WhatsApp free-form)::
        reply = OutboundMessage(
            tenant_id="a1b2c3d4-...",
            channel="whatsapp",
            recipient="905551234567",
            text="Randevunuz onaylandi!",
        )

    Example (WhatsApp template)::
        notification = OutboundMessage(
            tenant_id="a1b2c3d4-...",
            channel="whatsapp",
            recipient="905551234567",
            text="",          # body constructed from template variables
            template_name="appointment_reminder_v1",
        )
    """

    tenant_id: str
    channel: str
    recipient: str
    text: str
    template_name: Optional[str] = field(default=None)


# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------

@dataclass
class Tenant:
    """Core business/tenant record for the Mergen Platform.

    Represents a single onboarded business (a "tenant") in the multi-tenant
    SaaS model. Each tenant has a unique UUID (`tenant_id`), belongs to a
    business sector, and subscribes to a plan that gates feature access.

    The `whatsapp_phone_number_id` field mirrors the `phone_number_id` used
    by the Meta Cloud API as the routing key in the webhook firewall (see
    dent_bot's `webhooks.py` for the proven multi-tenant lookup pattern).

    Attributes:
        tenant_id:                UUID string; primary key in the tenants table.
        business_name:            Human-readable display name (e.g. "Smile Dental
                                  Clinic").
        sector:                   Business sector slug. Examples: "dental",
                                  "hospitality", "retail", "legal". Used to
                                  select the appropriate prompt template and
                                  RAG knowledge schema.
        plan:                     Subscription plan slug. Examples: "free",
                                  "starter", "pro", "enterprise". Gates feature
                                  access at the application layer.
        whatsapp_phone_number_id: Meta phone_number_id used as the webhook
                                  routing key. Stored encrypted in production;
                                  this field holds the decrypted plaintext for
                                  in-memory use only.
        created_at:               UTC timestamp when the tenant was first
                                  registered on the platform.

    Example::
        tenant = Tenant(
            tenant_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            business_name="Smile Dental Clinic",
            sector="dental",
            plan="pro",
            whatsapp_phone_number_id="123456789012345",
            created_at=datetime.utcnow(),
        )
    """

    tenant_id: str
    business_name: str
    sector: str
    plan: str
    whatsapp_phone_number_id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# KnowledgeField
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeField:
    """A single structured knowledge entry in a tenant's RAG knowledge base.

    Mergen Platform's RAG pipeline stores tenant-specific knowledge as a flat
    collection of typed key-value pairs (KnowledgeField rows). This is
    intentionally simple to allow easy CRUD via the admin API and fast
    embedding updates when a field changes.

    The `field_type` discriminator determines how the value is embedded,
    chunked, and retrieved:
      - "faq"           -- Question/answer pair for customer FAQ retrieval.
      - "policy"        -- Business policy text (e.g. refund policy, hours).
      - "product"       -- Product/service description for upsell prompts.
      - "contact"       -- Structured contact info (phone, address, social).
      - "system_prompt" -- Tenant-specific instruction injected into the LLM
                          system prompt at conversation start.

    Attributes:
        tenant_id:   UUID string; links this field to an owning Tenant.
        field_type:  Type discriminator string. See valid values above.
        value:       The raw text content to be embedded and retrieved.
                     Keep individual values under ~2 000 characters for
                     optimal embedding quality.

    Example::
        faq = KnowledgeField(
            tenant_id="a1b2c3d4-...",
            field_type="faq",
            value="S: Calisma saatleriniz neler?\\nC: Hafta ici 09:00-18:00.",
        )
        policy = KnowledgeField(
            tenant_id="a1b2c3d4-...",
            field_type="policy",
            value="Iptal politikasi: Randevunuzu 24 saat oncesine kadar iptal edebilirsiniz.",
        )
    """

    tenant_id: str
    field_type: str
    value: str
