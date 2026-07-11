# mergen_product_desk — Mergen Desk product layer.
# The customer-facing AI support desk product built on top of mergen_core.
# Provides tenant onboarding flows, conversation dashboards, and escalation
# routing for support teams.

from mergen_product_desk.desk_persona import DESK_PERSONA, DESK_HANDOFF_TRIGGERS
from mergen_product_desk.knowledge_template import (
    DeskTemplateValidator,
    DeskValidationError,
    REQUIRED_FIELDS,
    OPTIONAL_FIELDS,
)
from mergen_product_desk.onboarding_orchestrator import DeskOnboardingService

__all__ = [
    # Persona
    "DESK_PERSONA",
    "DESK_HANDOFF_TRIGGERS",
    # Knowledge Template
    "DeskTemplateValidator",
    "DeskValidationError",
    "REQUIRED_FIELDS",
    "OPTIONAL_FIELDS",
    # Onboarding
    "DeskOnboardingService",
]
