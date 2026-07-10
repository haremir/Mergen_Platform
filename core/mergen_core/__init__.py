# mergen_core — Core orchestration and domain logic for the Mergen Platform.
# This package is the heart of the platform: conversation engine, LLM routing,
# RAG pipeline, and cross-tenant shared business logic all live here.

from mergen_core.llm_gateway import LLMGateway, UsageRecord, get_gateway, reset_gateway
from mergen_core.rag_engine import RagEngine, FaissVectorStore, QdrantVectorStore, embed, build_context_block
from mergen_core.tenant_manager import TenantManager, TenantNotFoundError, TenantAlreadyExistsError, get_tenant_manager, reset_tenant_manager
from mergen_core.plan_guard import PlanGuard, PLAN_LIMITS, get_plan_guard, reset_plan_guard
from mergen_core.prompt_engine import PromptEngine, get_prompt_engine, reset_prompt_engine
from mergen_core.handoff_engine import HandoffEngine, REASON_USER_REQUESTED, REASON_LLM_FAILURE, REASON_POLICY, get_handoff_engine, reset_handoff_engine

__all__ = [
    # LLM Gateway
    "LLMGateway",
    "UsageRecord",
    "get_gateway",
    "reset_gateway",
    # RAG Engine
    "RagEngine",
    "FaissVectorStore",
    "QdrantVectorStore",
    "embed",
    "build_context_block",
    # Tenant Manager (Phase 3)
    "TenantManager",
    "TenantNotFoundError",
    "TenantAlreadyExistsError",
    "get_tenant_manager",
    "reset_tenant_manager",
    # Plan Guard (Phase 3)
    "PlanGuard",
    "PLAN_LIMITS",
    "get_plan_guard",
    "reset_plan_guard",
    # Prompt Engine (Phase 4)
    "PromptEngine",
    "get_prompt_engine",
    "reset_prompt_engine",
    # Handoff Engine (Phase 4)
    "HandoffEngine",
    "REASON_USER_REQUESTED",
    "REASON_LLM_FAILURE",
    "REASON_POLICY",
    "get_handoff_engine",
    "reset_handoff_engine",
]
