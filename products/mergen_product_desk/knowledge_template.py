"""
mergen_product_desk.knowledge_template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Desk product knowledge-field validator and converter.
Supports deeply structured schemas for business hours, services, and FAQs.

Author: Mergen Platform -- Desk Product Team
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Import shared domain models
# ---------------------------------------------------------------------------
try:
    from mergen_common.models import KnowledgeField
except ModuleNotFoundError:
    _shared = os.path.join(os.path.dirname(__file__), "..", "..", "shared")
    sys.path.insert(0, os.path.abspath(_shared))
    from mergen_common.models import KnowledgeField  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field type mapping
# ---------------------------------------------------------------------------
_FIELD_TYPE_MAP: Dict[str, str] = {
    "business_hours":        "policy",
    "location":              "contact",
    "contact_info":          "contact",
    "cancellation_policy":   "policy",
    "services":              "product",
    # Optional enrichment fields
    "pricing":               "product",
    "social_media":          "contact",
    "languages_spoken":      "policy",
    "system_prompt_override": "system_prompt",
}

REQUIRED_FIELDS: List[str] = [
    "business_hours",
    "location",
    "contact_info",
    "cancellation_policy",
    "services",
]

OPTIONAL_FIELDS: List[str] = [
    "pricing",
    "social_media",
    "languages_spoken",
    "system_prompt_override",
]


class DeskValidationError(ValueError):
    """Raised when the raw form data is missing one or more required fields."""

    def __init__(self, missing: List[str]) -> None:
        self.missing_fields = missing
        super().__init__(
            f"DeskTemplateValidator: missing required fields: {missing}. "
            f"All of {REQUIRED_FIELDS} must be present in raw_form_data."
        )


class DeskTemplateValidator:
    """Validates and converts raw onboarding form data into KnowledgeField objects.

    Supports structured formats:
    - business_hours: Dict[str, str] (e.g. {"monday": "09:00-18:00"})
    - services: List[Dict[str, str]] (keys: name, price, description)
    - faqs: List[Dict[str, str]] (keys: question, answer)
    """

    def __init__(self) -> None:
        logger.info(
            "DeskTemplateValidator: initialised with structured field support."
        )

    def validate_and_convert(
        self,
        tenant_id: str,
        raw_form_data: Dict[str, Any],
    ) -> List[KnowledgeField]:
        """Validate the form data and convert it to a list of KnowledgeFields."""
        self._validate_required(raw_form_data)

        knowledge_fields: List[KnowledgeField] = []

        # ── 1. Process Business Hours (Dict[str, str]) ────────────────────
        hours_val = raw_form_data["business_hours"]
        if isinstance(hours_val, dict):
            hours_parts = []
            for day, hours in hours_val.items():
                hours_parts.append(f"{day.capitalize()}: {hours}")
            hours_str = ". ".join(hours_parts)
        else:
            hours_str = str(hours_val)

        knowledge_fields.append(
            KnowledgeField(
                tenant_id=tenant_id,
                field_type="policy",
                value=f"[business_hours] {hours_str}",
            )
        )

        # ── 2. Process Location, Contact Info, Cancellation Policy (Str) ─
        for key in ["location", "contact_info", "cancellation_policy"]:
            val = raw_form_data[key]
            knowledge_fields.append(
                KnowledgeField(
                    tenant_id=tenant_id,
                    field_type=_FIELD_TYPE_MAP[key],
                    value=f"[{key}] {str(val).strip()}",
                )
            )

        # ── 3. Process Services (List[Dict[str, str]]) ────────────────────
        services_val = raw_form_data["services"]
        if isinstance(services_val, list):
            for service_dict in services_val:
                name = service_dict.get("name", "").strip()
                price = service_dict.get("price", "").strip()
                desc = service_dict.get("description", "").strip()
                knowledge_fields.append(
                    KnowledgeField(
                        tenant_id=tenant_id,
                        field_type="product",
                        value=f"[service] Name: {name} | Price: {price} | Description: {desc}",
                    )
                )
        else:
            # Fallback for plain string
            knowledge_fields.append(
                KnowledgeField(
                    tenant_id=tenant_id,
                    field_type="product",
                    value=f"[services] {str(services_val).strip()}",
                )
            )

        # ── 4. Process Optional Fields (pricing, social_media, languages_spoken)
        for key in OPTIONAL_FIELDS:
            if key in raw_form_data and raw_form_data[key]:
                val = raw_form_data[key]
                knowledge_fields.append(
                    KnowledgeField(
                        tenant_id=tenant_id,
                        field_type=_FIELD_TYPE_MAP[key],
                        value=f"[{key}] {str(val).strip()}",
                    )
                )

        # ── 5. Process Structured FAQs (List[Dict[str, str]]) ─────────────
        faqs_val = raw_form_data.get("faqs", [])
        if isinstance(faqs_val, list):
            for faq_dict in faqs_val:
                q = faq_dict.get("question", "").strip()
                a = faq_dict.get("answer", "").strip()
                if q and a:
                    knowledge_fields.append(
                        KnowledgeField(
                            tenant_id=tenant_id,
                            field_type="faq",
                            value=f"[faq] Question: {q} | Answer: {a}",
                        )
                    )

        # Legacy faq_* string prefix support
        for key, value in raw_form_data.items():
            if key.startswith("faq_") and value and not key == "faqs":
                knowledge_fields.append(
                    KnowledgeField(
                        tenant_id=tenant_id,
                        field_type="faq",
                        value=f"[{key}] {str(value).strip()}",
                    )
                )

        logger.info(
            "DeskTemplateValidator: generated %d KnowledgeField(s) for tenant %s.",
            len(knowledge_fields),
            tenant_id,
        )
        return knowledge_fields

    def validate_only(self, raw_form_data: Dict[str, Any]) -> None:
        """Run validation without conversion."""
        self._validate_required(raw_form_data)

    def get_required_fields(self) -> List[str]:
        return list(REQUIRED_FIELDS)

    def get_optional_fields(self) -> List[str]:
        return list(OPTIONAL_FIELDS)

    @staticmethod
    def _validate_required(raw_form_data: Dict[str, Any]) -> None:
        """Raise DeskValidationError if any required field is absent or empty."""
        missing = []
        for key in REQUIRED_FIELDS:
            val = raw_form_data.get(key)
            if val is None:
                missing.append(key)
            elif isinstance(val, str) and not val.strip():
                missing.append(key)
            elif isinstance(val, (dict, list)) and len(val) == 0:
                missing.append(key)
        if missing:
            logger.warning(
                "DeskTemplateValidator: validation FAILED — missing fields: %s",
                missing,
            )
            raise DeskValidationError(missing)
