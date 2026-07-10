# mergen_core — Core orchestration and domain logic for the Mergen Platform.
# This package is the heart of the platform: conversation engine, LLM routing,
# RAG pipeline, and cross-tenant shared business logic all live here.

from mergen_core.llm_gateway import LLMGateway, UsageRecord, get_gateway, reset_gateway
from mergen_core.rag_engine import RagEngine, FaissVectorStore, QdrantVectorStore, embed, build_context_block

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
]
