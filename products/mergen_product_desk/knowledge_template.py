"""
mergen_product_desk.knowledge_template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Desk product knowledge-field validator and converter.

The Desk product requires a **canonical set of knowledge fields** to be present
before a tenant can be activated.  Missing fields would leave the AI assistant
unable to answer the most basic customer questions.

``DeskTemplateValidator`` enforces this contract at onboarding time, preventing
misconfigured tenants from going live.

Required Fields Schema
----------------------
+------------------------+-------------+--------------------------------------+
| Field Key              | field_type  | Description                          |
+========================+=============+======================================+
| business_hours         | policy      | Opening / closing hours per day      |
| location               | contact     | Physical address or directions       |
| contact_info           | contact     | Phone, e-mail, social handles        |
| cancellation_policy    | policy      | Lead time and penalty rules          |
| services               | product     | List of offered services / menu      |
+------------------------+-------------+--------------------------------------+

Optional (enrichment) fields — included when present in raw_form_data:
+------------------------+-------------+--------------------------------------+
| Field Key              | field_type  | Description                          |
+========================+=============+======================================+
| faq_*                  | faq         | Any key prefixed with faq_           |
| system_prompt_override | system_prompt | Tenant-specific LLM instruction    |
| pricing                | product     | Pricing table or price range         |
| social_media           | contact     | Instagram, Twitter, etc.             |
| languages_spoken       | policy      | Languages the staff can assist in    |
+------------------------+-------------+--------------------------------------+

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
# Maps each required/optional field key to its KnowledgeField.field_type.

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

# ---------------------------------------------------------------------------
# Required fields (onboarding gate — these MUST be present)
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: List[str] = [
    "business_hours",
    "location",
    "contact_info",
    "cancellation_policy",
    "services",
]

# Optional fields that are included if provided (no validation error if absent)
OPTIONAL_FIELDS: List[str] = [
    "pricing",
    "social_media",
    "languages_spoken",
    "system_prompt_override",
]


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class DeskValidationError(ValueError):
    """Raised when the raw form data is missing one or more required fields."""

    def __init__(self, missing: List[str]) -> None:
        self.missing_fields = missing
        super().__init__(
            f"DeskTemplateValidator: missing required fields: {missing}. "
            f"All of {REQUIRED_FIELDS} must be present in raw_form_data."
        )


# ---------------------------------------------------------------------------
# DeskTemplateValidator
# ---------------------------------------------------------------------------

class DeskTemplateValidator:
    """Validates and converts raw onboarding form data into KnowledgeField objects.

    Enforces the Desk product's required-field contract and produces a
    ready-to-ingest list of ``KnowledgeField`` objects for the RAG engine.

    Usage::
        validator = DeskTemplateValidator()
        fields = validator.validate_and_convert(tenant_id, raw_form_data)
        # Then pass fields to RagEngine.index_knowledge_fields(fields)

    Raises:
        DeskValidationError: If any required field is missing from raw_form_data.
    """

    def __init__(self) -> None:
        logger.info(
            "DeskTemplateValidator: initialised. Required fields: %s",
            REQUIRED_FIELDS,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_and_convert(
        self,
        tenant_id: str,
        raw_form_data: Dict[str, Any],
    ) -> List[KnowledgeField]:
        """Validate the form data and convert it to a list of KnowledgeFields.

        Process:
          1. Check all REQUIRED_FIELDS are present and non-empty.
          2. Raise ``DeskValidationError`` if any are missing.
          3. Convert each recognised field to a ``KnowledgeField``.
          4. Handle ``faq_*`` prefixed keys as FAQ entries.
          5. Return the list ordered by: required → optional → faq.

        Args:
            tenant_id:      UUID of the tenant being onboarded.
            raw_form_data:  Dict of field_key -> value (strings or dicts).
                            Values may be strings, lists, or nested dicts —
                            all are coerced to strings via ``_coerce_to_str()``.

        Returns:
            List of ``KnowledgeField`` objects ready for RAG ingestion.

        Raises:
            DeskValidationError: If any required field is missing or empty.
        """
        # ── Step 1: Validate required fields ──────────────────────────────
        self._validate_required(raw_form_data)

        knowledge_fields: List[KnowledgeField] = []

        # ── Step 2: Add required fields ───────────────────────────────────
        for key in REQUIRED_FIELDS:
            value = raw_form_data[key]
            kf = KnowledgeField(
                tenant_id=tenant_id,
                field_type=_FIELD_TYPE_MAP[key],
                value=f"[{key}] {_coerce_to_str(value)}",
            )
            knowledge_fields.append(kf)
            logger.debug(
                "DeskTemplateValidator: required field '%s' -> field_type='%s'",
                key,
                _FIELD_TYPE_MAP[key],
            )

        # ── Step 3: Add optional fields if present ────────────────────────
        for key in OPTIONAL_FIELDS:
            if key in raw_form_data and raw_form_data[key]:
                value = raw_form_data[key]
                kf = KnowledgeField(
                    tenant_id=tenant_id,
                    field_type=_FIELD_TYPE_MAP[key],
                    value=f"[{key}] {_coerce_to_str(value)}",
                )
                knowledge_fields.append(kf)
                logger.debug(
                    "DeskTemplateValidator: optional field '%s' included.", key
                )

        # ── Step 4: Collect faq_* prefixed entries ────────────────────────
        for key, value in raw_form_data.items():
            if key.startswith("faq_") and value:
                kf = KnowledgeField(
                    tenant_id=tenant_id,
                    field_type="faq",
                    value=f"[{key}] {_coerce_to_str(value)}",
                )
                knowledge_fields.append(kf)
                logger.debug(
                    "DeskTemplateValidator: FAQ field '%s' included.", key
                )

        logger.info(
            "DeskTemplateValidator.validate_and_convert: tenant=%s -> %d KnowledgeField(s) generated.",
            tenant_id,
            len(knowledge_fields),
        )
        return knowledge_fields

    def validate_only(self, raw_form_data: Dict[str, Any]) -> None:
        """Run validation without conversion.  Raises DeskValidationError on failure.

        Useful for pre-flight checks in admin UIs before committing the full
        onboarding flow.
        """
        self._validate_required(raw_form_data)

    def get_required_fields(self) -> List[str]:
        """Return the list of required field keys for this product."""
        return list(REQUIRED_FIELDS)

    def get_optional_fields(self) -> List[str]:
        """Return the list of optional field keys."""
        return list(OPTIONAL_FIELDS)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_required(raw_form_data: Dict[str, Any]) -> None:
        """Raise DeskValidationError if any required field is absent or empty."""
        missing = [
            key
            for key in REQUIRED_FIELDS
            if not raw_form_data.get(key)
        ]
        if missing:
            logger.warning(
                "DeskTemplateValidator: validation FAILED — missing fields: %s",
                missing,
            )
            raise DeskValidationError(missing)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coerce_to_str(value: Any) -> str:
    """Convert any form value to a clean string for RAG storage.

    - str  → strip whitespace
    - list → newline-joined items
    - dict → comma-separated "key: value" pairs
    - else → str()
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if item)
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)
