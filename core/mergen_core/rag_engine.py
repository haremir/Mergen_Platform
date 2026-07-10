"""
mergen_core.rag_engine
~~~~~~~~~~~~~~~~~~~~~~

Domain-agnostic Retrieval-Augmented Generation engine for the Mergen Platform.

Architecture
------------
The engine wraps a pluggable vector store backend and a sentence-transformer
embedding model.  Two backends are supported:

  Backend   | Class              | When to use
  ----------|--------------------|-------------------------------------------
  Qdrant    | QdrantVectorStore  | Production.  Remote or in-process server.
  FAISS     | FaissVectorStore   | Local dev / CI.  No server required.

Both backends implement the ``VectorStore`` Protocol, so callers never touch
the backend directly.

Field-Based Chunking Strategy
------------------------------
Unlike naive free-text chunking (which loses structure and causes hallucinations
on mixed-content blobs), this engine embeds one ``KnowledgeField`` at a time.
Each field is a discrete, semantically atomic unit (an FAQ pair, a policy
clause, a product description, etc.).  This means:

  * Retrieval is exact at the field level — no partial-chunk misses.
  * The ``tenant_id`` is stored in the vector payload, providing strict
    isolation between tenants at the index level.
  * Updating a single piece of knowledge is a simple upsert of one vector,
    not a full re-index.

Embedding Model
---------------
``sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`` (117 MB) is
chosen because:
  1. Multilingual — handles Turkish, English, and Arabic natively.
  2. Small footprint — runs on CPU with ~200 ms/inference.
  3. 384-dimensional output — efficient FAISS index and Qdrant storage.

Usage::
    import sys; sys.path.insert(0, 'shared')  # in repo root
    from mergen_common.models import KnowledgeField
    from mergen_core.rag_engine import RagEngine

    engine = RagEngine()           # auto-selects FAISS if Qdrant is absent
    engine.ingest_fields("tenant-1", [field1, field2, field3])
    results = engine.retrieve("tenant-1", "What are your working hours?")

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

import numpy as np

# ---------------------------------------------------------------------------
# Shared models — imported from the zero-dependency shared package.
# If running the engine from the repo root, ensure `shared/` is on sys.path.
# ---------------------------------------------------------------------------
try:
    from mergen_common.models import KnowledgeField
except ModuleNotFoundError:
    # Fallback: allow running from core/ directly during development
    _shared = os.path.join(
        os.path.dirname(__file__), "..", "..", "shared"
    )
    sys.path.insert(0, os.path.abspath(_shared))
    from mergen_common.models import KnowledgeField  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding model
# ---------------------------------------------------------------------------

_EMBED_MODEL_NAME = os.getenv(
    "MERGEN_EMBED_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
_EMBED_DIM = 384   # fixed for MiniLM-L12-v2 family
_TOP_K_DEFAULT = int(os.getenv("RAG_TOP_K", "3"))


# ---------------------------------------------------------------------------
# EmbedderSingleton — lazy-loaded, process-wide sentence-transformer
# ---------------------------------------------------------------------------

class _EmbedderSingleton:
    """Holds the singleton SentenceTransformer model instance."""

    _model: Optional[Any] = None

    @classmethod
    def get(cls) -> Any:
        """Lazy-load and cache the SentenceTransformer model."""
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                logger.info(
                    "RagEngine: loading embedding model '%s' (first call only).",
                    _EMBED_MODEL_NAME,
                )
                cls._model = SentenceTransformer(_EMBED_MODEL_NAME)
                logger.info("RagEngine: embedding model loaded.")
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required for RagEngine. "
                    "Install it with: pip install sentence-transformers"
                ) from exc
        return cls._model


def embed(text: str) -> List[float]:
    """Embed ``text`` into a 384-dim float vector using the multilingual MiniLM model.

    Args:
        text: Plain-text string to embed.  Should be < 512 tokens for best quality.

    Returns:
        List of 384 floats (L2-normalised by SentenceTransformer).
    """
    model = _EmbedderSingleton.get()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


# ---------------------------------------------------------------------------
# Payload schema — stored alongside each vector
# ---------------------------------------------------------------------------

@dataclass
class _VectorPayload:
    """Metadata stored in the vector store alongside each embedding.

    This is the canonical serialisation format.  The ``field_id`` is a
    deterministic SHA-256 hash of ``(tenant_id, field_type, value[:64])``
    so that re-ingesting the same field is idempotent.
    """

    field_id: str
    tenant_id: str
    field_type: str
    value: str

    @staticmethod
    def make_id(tenant_id: str, field_type: str, value: str) -> str:
        """Deterministic integer ID derived from content hash (FAISS requires int)."""
        raw = f"{tenant_id}::{field_type}::{value[:128]}"
        h = hashlib.sha256(raw.encode()).hexdigest()
        # Map first 15 hex chars → positive int64 (safe for numpy int64)
        return h[:15]

    @staticmethod
    def make_int_id(tenant_id: str, field_type: str, value: str) -> int:
        """Deterministic integer ID for FAISS (which uses int64 IDs)."""
        h = _VectorPayload.make_id(tenant_id, field_type, value)
        return int(h, 16) % (2**62)  # stay positive int64

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "tenant_id": self.tenant_id,
            "field_type": self.field_type,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> _VectorPayload:
        return cls(
            field_id=d["field_id"],
            tenant_id=d["tenant_id"],
            field_type=d["field_type"],
            value=d["value"],
        )


# ---------------------------------------------------------------------------
# VectorStore Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class VectorStore(Protocol):
    """Interface that both FAISS and Qdrant backends must satisfy."""

    def upsert(
        self,
        vector: List[float],
        payload: _VectorPayload,
    ) -> None:
        """Insert or update a single vector + metadata."""
        ...

    def search(
        self,
        query_vector: List[float],
        tenant_id: str,
        top_k: int = _TOP_K_DEFAULT,
    ) -> List[Tuple[float, _VectorPayload]]:
        """Return top-k results filtered to ``tenant_id``.

        Returns:
            List of (score, payload) tuples ordered by descending similarity.
        """
        ...

    def count(self, tenant_id: Optional[str] = None) -> int:
        """Return the number of indexed vectors (optionally scoped to tenant)."""
        ...


# ---------------------------------------------------------------------------
# FAISS Backend — local / dev / CI
# ---------------------------------------------------------------------------

class FaissVectorStore:
    """In-process FAISS vector store with tenant isolation via payload filtering.

    Uses an ``IndexFlatIP`` (inner product) index because vectors are L2-
    normalised by the embedding model, making cosine similarity == inner product.
    All vectors are stored in a single flat index; tenant isolation is enforced
    at query-time by filtering payloads.

    This is suitable for datasets up to ~100 K vectors per process.  For larger
    datasets or multi-process deployments, switch to the QdrantVectorStore.
    """

    def __init__(self, dim: int = _EMBED_DIM) -> None:
        try:
            import faiss  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "faiss-cpu is required for FaissVectorStore. "
                "Install it with: pip install faiss-cpu"
            ) from exc

        self._faiss = faiss
        self._index = faiss.IndexIDMap(faiss.IndexFlatIP(dim))
        # Map from int64 FAISS ID -> _VectorPayload
        self._id_to_payload: Dict[int, _VectorPayload] = {}
        self._dim = dim
        logger.info("FaissVectorStore: initialised (dim=%d).", dim)

    def upsert(self, vector: List[float], payload: _VectorPayload) -> None:
        int_id = _VectorPayload.make_int_id(
            payload.tenant_id, payload.field_type, payload.value
        )
        vec = np.array([vector], dtype=np.float32)
        ids = np.array([int_id], dtype=np.int64)

        # Remove existing entry for idempotency
        if int_id in self._id_to_payload:
            self._index.remove_ids(ids)

        self._index.add_with_ids(vec, ids)
        self._id_to_payload[int_id] = payload
        logger.debug(
            "FaissVectorStore: upserted id=%d tenant=%s type=%s",
            int_id,
            payload.tenant_id,
            payload.field_type,
        )

    def search(
        self,
        query_vector: List[float],
        tenant_id: str,
        top_k: int = _TOP_K_DEFAULT,
    ) -> List[Tuple[float, _VectorPayload]]:
        if self._index.ntotal == 0:
            return []

        # Over-fetch to allow tenant filtering
        k = min(self._index.ntotal, top_k * 10)
        q = np.array([query_vector], dtype=np.float32)
        scores, ids = self._index.search(q, k)

        results: List[Tuple[float, _VectorPayload]] = []
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1:
                continue
            pld = self._id_to_payload.get(int(idx))
            if pld is None:
                continue
            if pld.tenant_id != tenant_id:
                continue
            results.append((float(score), pld))
            if len(results) >= top_k:
                break

        return results

    def count(self, tenant_id: Optional[str] = None) -> int:
        if tenant_id is None:
            return int(self._index.ntotal)
        return sum(
            1 for p in self._id_to_payload.values()
            if p.tenant_id == tenant_id
        )


# ---------------------------------------------------------------------------
# Qdrant Backend — production
# ---------------------------------------------------------------------------

class QdrantVectorStore:
    """Qdrant vector store backend for production deployments.

    Uses a single Qdrant collection (``QDRANT_COLLECTION``) with per-tenant
    isolation via payload filtering on the ``tenant_id`` field.  Qdrant's
    native filtering is server-side, making this dramatically more efficient
    than the FAISS post-filter approach for large multi-tenant datasets.

    Environment Variables
    ---------------------
    QDRANT_URL          : Qdrant server URL (default: http://localhost:6333)
    QDRANT_API_KEY      : API key for Qdrant Cloud (optional for self-hosted)
    QDRANT_COLLECTION   : Collection name (default: mergen_knowledge)
    """

    _COLLECTION = os.getenv("QDRANT_COLLECTION", "mergen_knowledge")
    _URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    _API_KEY = os.getenv("QDRANT_API_KEY")

    def __init__(self, dim: int = _EMBED_DIM) -> None:
        try:
            from qdrant_client import QdrantClient  # type: ignore
            from qdrant_client.models import (  # type: ignore
                Distance,
                PointStruct,
                VectorParams,
                Filter,
                FieldCondition,
                MatchValue,
            )
        except ImportError as exc:
            raise ImportError(
                "qdrant-client is required for QdrantVectorStore. "
                "Install it with: pip install qdrant-client"
            ) from exc

        self._QdrantClient = QdrantClient
        self._PointStruct = PointStruct
        self._VectorParams = VectorParams
        self._Distance = Distance
        self._Filter = Filter
        self._FieldCondition = FieldCondition
        self._MatchValue = MatchValue

        self._dim = dim
        self._client = QdrantClient(
            url=self._URL,
            api_key=self._API_KEY,
            timeout=10,
        )
        self._ensure_collection()
        logger.info(
            "QdrantVectorStore: connected to %s, collection='%s'.",
            self._URL,
            self._COLLECTION,
        )

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if self._COLLECTION not in existing:
            self._client.create_collection(
                collection_name=self._COLLECTION,
                vectors_config=self._VectorParams(
                    size=self._dim,
                    distance=self._Distance.COSINE,
                ),
            )
            logger.info(
                "QdrantVectorStore: created collection '%s'.", self._COLLECTION
            )

    def upsert(self, vector: List[float], payload: _VectorPayload) -> None:
        int_id = _VectorPayload.make_int_id(
            payload.tenant_id, payload.field_type, payload.value
        )
        self._client.upsert(
            collection_name=self._COLLECTION,
            points=[
                self._PointStruct(
                    id=int_id,
                    vector=vector,
                    payload=payload.to_dict(),
                )
            ],
        )
        logger.debug(
            "QdrantVectorStore: upserted id=%d tenant=%s type=%s",
            int_id,
            payload.tenant_id,
            payload.field_type,
        )

    def search(
        self,
        query_vector: List[float],
        tenant_id: str,
        top_k: int = _TOP_K_DEFAULT,
    ) -> List[Tuple[float, _VectorPayload]]:
        results = self._client.search(
            collection_name=self._COLLECTION,
            query_vector=query_vector,
            query_filter=self._Filter(
                must=[
                    self._FieldCondition(
                        key="tenant_id",
                        match=self._MatchValue(value=tenant_id),
                    )
                ]
            ),
            limit=top_k,
            with_payload=True,
        )
        return [
            (hit.score, _VectorPayload.from_dict(hit.payload))
            for hit in results
        ]

    def count(self, tenant_id: Optional[str] = None) -> int:
        if tenant_id is None:
            return self._client.count(
                collection_name=self._COLLECTION
            ).count
        return self._client.count(
            collection_name=self._COLLECTION,
            count_filter=self._Filter(
                must=[
                    self._FieldCondition(
                        key="tenant_id",
                        match=self._MatchValue(value=tenant_id),
                    )
                ]
            ),
        ).count


# ---------------------------------------------------------------------------
# RagEngine — high-level facade
# ---------------------------------------------------------------------------

class RagEngine:
    """High-level RAG engine combining embedding + vector store.

    Automatically selects the backend:
      * If ``qdrant-client`` is importable and ``QDRANT_URL`` is reachable →
        uses QdrantVectorStore.
      * Otherwise → falls back to FaissVectorStore with a warning.

    Pass ``backend="faiss"`` or ``backend="qdrant"`` to force a specific choice.

    Args:
        backend:   "auto" (default), "faiss", or "qdrant".
        top_k:     Default number of results for ``retrieve()``.
    """

    def __init__(
        self,
        backend: str = "auto",
        top_k: int = _TOP_K_DEFAULT,
    ) -> None:
        self._top_k = top_k
        self._store: VectorStore = self._init_store(backend)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, text: str) -> List[float]:
        """Embed ``text`` into a 384-dim float vector.

        Delegates to the module-level ``embed()`` function which uses the
        process-wide singleton SentenceTransformer model.
        """
        return embed(text)

    def upsert(
        self,
        tenant_id: str,
        knowledge_field: KnowledgeField,
        vector: Optional[List[float]] = None,
    ) -> None:
        """Insert or update a single KnowledgeField in the vector store.

        Args:
            tenant_id:       UUID of the owning tenant.
            knowledge_field: The field to index.
            vector:          Pre-computed embedding (optional).  If None,
                             the field's ``value`` is embedded on-the-fly.
        """
        if vector is None:
            vector = self.embed(knowledge_field.value)

        payload = _VectorPayload(
            field_id=_VectorPayload.make_id(
                tenant_id, knowledge_field.field_type, knowledge_field.value
            ),
            tenant_id=tenant_id,
            field_type=knowledge_field.field_type,
            value=knowledge_field.value,
        )
        self._store.upsert(vector, payload)

    def retrieve(
        self,
        tenant_id: str,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[KnowledgeField]:
        """Retrieve the most relevant KnowledgeFields for ``query``.

        Args:
            tenant_id: UUID of the tenant whose knowledge base to search.
            query:     Natural-language query string.
            top_k:     Number of results to return (default: engine default).

        Returns:
            List of KnowledgeField objects ordered by descending similarity.
        """
        k = top_k or self._top_k
        query_vector = self.embed(query)
        hits = self._store.search(query_vector, tenant_id=tenant_id, top_k=k)

        fields: List[KnowledgeField] = []
        for score, payload in hits:
            logger.debug(
                "RAG hit: tenant=%s type=%s score=%.4f value_preview='%s'",
                tenant_id,
                payload.field_type,
                score,
                payload.value[:80],
            )
            fields.append(
                KnowledgeField(
                    tenant_id=payload.tenant_id,
                    field_type=payload.field_type,
                    value=payload.value,
                )
            )
        return fields

    def ingest_fields(
        self,
        tenant_id: str,
        fields: List[KnowledgeField],
    ) -> int:
        """Batch-embed and upsert a list of KnowledgeFields.

        Each field is embedded independently (field-based chunking) to
        preserve semantic boundaries and prevent context bleeding between
        different knowledge types.

        Args:
            tenant_id: UUID of the owning tenant.
            fields:    List of KnowledgeField objects to index.

        Returns:
            Number of fields successfully indexed.
        """
        indexed = 0
        for kf in fields:
            try:
                # Prefix the value with its type tag to give the embedding
                # model a semantic anchor (e.g., "faq: What are your hours?")
                embed_text = f"{kf.field_type}: {kf.value}"
                vector = self.embed(embed_text)
                self.upsert(tenant_id, kf, vector=vector)
                indexed += 1
                logger.info(
                    "RagEngine.ingest_fields: indexed [%s] '%s...' for tenant %s",
                    kf.field_type,
                    kf.value[:60],
                    tenant_id,
                )
            except Exception as exc:
                logger.error(
                    "RagEngine.ingest_fields: failed to index field type=%s — %s",
                    kf.field_type,
                    exc,
                )
        logger.info(
            "RagEngine.ingest_fields: %d/%d fields indexed for tenant %s.",
            indexed,
            len(fields),
            tenant_id,
        )
        return indexed

    def count(self, tenant_id: Optional[str] = None) -> int:
        """Return the number of indexed vectors, optionally scoped to a tenant."""
        return self._store.count(tenant_id)

    # ------------------------------------------------------------------
    # Backend initialisation
    # ------------------------------------------------------------------

    @staticmethod
    def _init_store(backend: str) -> VectorStore:
        if backend == "faiss":
            return FaissVectorStore()

        if backend == "qdrant":
            return QdrantVectorStore()

        # "auto" — try Qdrant first, fall back to FAISS
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        try:
            store = QdrantVectorStore()
            logger.info("RagEngine: using QdrantVectorStore (auto-selected).")
            return store
        except Exception as exc:
            logger.warning(
                "RagEngine: QdrantVectorStore unavailable (%s) — "
                "falling back to FaissVectorStore.",
                exc,
            )
            return FaissVectorStore()


# ---------------------------------------------------------------------------
# Utility — build a context block from retrieved fields
# ---------------------------------------------------------------------------

def build_context_block(fields: List[KnowledgeField]) -> str:
    """Format retrieved KnowledgeFields into a concise LLM context block.

    Args:
        fields: Retrieved knowledge fields (output of ``RagEngine.retrieve``).

    Returns:
        A formatted string ready to be injected into the system prompt or
        a ``<context>`` tag in the user message.

    Example output::
        [faq] What are your working hours?
        Answer: We are open Monday–Friday, 09:00–18:00.

        [policy] We do not offer refunds after 48 hours of service delivery.
    """
    if not fields:
        return "(No relevant knowledge found for this query.)"

    lines: List[str] = []
    for f in fields:
        lines.append(f"[{f.field_type}] {f.value}")
    return "\n\n".join(lines)
