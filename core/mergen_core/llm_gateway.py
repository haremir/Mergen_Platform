"""
mergen_core.llm_gateway
~~~~~~~~~~~~~~~~~~~~~~~

Domain-agnostic LLM gateway for the Mergen Platform.

Architecture — "Self-Host Ready" three-tier fallback chain
----------------------------------------------------------
  Tier 1  LOCAL     Check ``LOCAL_LLM_URL`` env var.  If set, hit a local
                    OpenAI-compatible server first (Ollama / vLLM running
                    Qwen 7B-14B).  Zero latency cost when self-hosted.
  Tier 2  OPENROUTER  Primary cloud provider.  Default model:
                    ``qwen/qwen-2.5-14b-instruct`` (best quality/cost ratio
                    for multilingual SaaS tasks).  Falls back to
                    ``qwen/qwen-2.5-7b-instruct`` inside the same call.
  Tier 3  GROQ      Secondary cloud fallback.  Default model:
                    ``qwen-2.5-32b`` (Groq preview) with
                    ``llama-3.1-70b-versatile`` as last resort.

All three tiers speak the **OpenAI Chat Completions** wire protocol, so
switching providers is a header+URL swap.  No provider-specific SDK needed.

Token / Cost Tracking
---------------------
Every successful call emits a structured log entry tagged with
``tenant_id``, model name, prompt_tokens, completion_tokens, and
wall-clock latency_ms.  In production this is forwarded to a metrics
sink (Prometheus / ClickHouse).  The ``UsageRecord`` dataclass is the
canonical format — it can be persisted or streamed downstream without
any further transformation.

Usage::
    from mergen_core.llm_gateway import LLMGateway, get_gateway

    # Simple one-liner (singleton)
    reply = get_gateway().route(
        query="How can I help you today?",
        system_prompt="You are a helpful assistant.",
        tenant_id="tenant-abc-123",
    )

    # Or with full control
    gw = LLMGateway(
        local_url="http://localhost:11434/v1",
        openrouter_api_key="sk-or-...",
        groq_api_key="gsk_...",
    )
    reply = gw.route(query, system_prompt, tenant_id="t1")

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — model identifiers
# ---------------------------------------------------------------------------

# Tier 1: Local (Ollama/vLLM) — OpenAI-compatible /v1/chat/completions
_LOCAL_DEFAULT_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:14b")

# Tier 2: OpenRouter
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_PRIMARY_MODEL = "qwen/qwen-2.5-14b-instruct"
_OPENROUTER_SECONDARY_MODEL = "qwen/qwen-2.5-7b-instruct"

# Tier 3: Groq
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_GROQ_PRIMARY_MODEL = "qwen-2.5-32b"          # Groq Qwen preview
_GROQ_FALLBACK_MODEL = "llama-3.1-70b-versatile"  # guaranteed availability

_DEFAULT_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))
_DEFAULT_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
_DEFAULT_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))


# ---------------------------------------------------------------------------
# UsageRecord — structured telemetry / cost tracking per call
# ---------------------------------------------------------------------------

@dataclass
class UsageRecord:
    """Immutable record emitted after every successful LLM call.

    Attributes:
        tenant_id:         UUID of the tenant that triggered the call.
        model:             Exact model identifier used (after fallback resolution).
        provider:          One of "local", "openrouter", "groq".
        prompt_tokens:     Tokens consumed by the prompt (None if unavailable).
        completion_tokens: Tokens consumed by the completion.
        total_tokens:      Sum of prompt + completion (or None).
        latency_ms:        Wall-clock time for the HTTP round-trip in milliseconds.
        query_preview:     First 120 chars of the query for log correlation.
    """

    tenant_id: str
    model: str
    provider: str
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    latency_ms: float
    query_preview: str = field(repr=False)

    def as_log_dict(self) -> Dict[str, Any]:
        """Returns a flat dict suitable for structured logging / metrics sinks."""
        return {
            "event": "llm_usage",
            "tenant_id": self.tenant_id,
            "model": self.model,
            "provider": self.provider,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": round(self.latency_ms, 2),
            "query_preview": self.query_preview,
        }


# ---------------------------------------------------------------------------
# LLMGateway
# ---------------------------------------------------------------------------

class LLMGateway:
    """Three-tier self-host-ready LLM gateway.

    Constructor parameters are all optional — the gateway reads from
    environment variables when they are not supplied explicitly, so
    instantiation with no arguments works out-of-the-box.

    Environment Variables
    ---------------------
    LOCAL_LLM_URL        : Base URL of a local OpenAI-compatible server.
                           Example: ``http://localhost:11434/v1``
                           If not set, Tier 1 is skipped.
    LOCAL_LLM_MODEL      : Model tag for the local server (default: qwen2.5:14b)
    OPENROUTER_API_KEY   : Bearer token for api.openrouter.ai
    OPENROUTER_HTTP_REFERER : Sent as HTTP-Referer header (for OR analytics)
    GROQ_API_KEY         : Bearer token for api.groq.com/openai/v1
    LLM_TIMEOUT          : HTTP request timeout in seconds (default: 60)
    LLM_MAX_TOKENS       : Maximum tokens for completion (default: 1024)
    LLM_TEMPERATURE      : Sampling temperature (default: 0.7)
    """

    def __init__(
        self,
        *,
        local_url: Optional[str] = None,
        local_model: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        openrouter_http_referer: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> None:
        # Tier 1 — Local
        self._local_url: Optional[str] = (
            local_url or os.getenv("LOCAL_LLM_URL")
        )
        self._local_model: str = local_model or _LOCAL_DEFAULT_MODEL

        # Tier 2 — OpenRouter
        self._or_key: Optional[str] = (
            openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        )
        self._or_referer: str = (
            openrouter_http_referer
            or os.getenv("OPENROUTER_HTTP_REFERER", "https://mergen.platform")
        )

        # Tier 3 — Groq
        self._groq_key: Optional[str] = groq_api_key or os.getenv("GROQ_API_KEY")

        # Shared config
        self._timeout: int = timeout or _DEFAULT_TIMEOUT
        self._max_tokens: int = max_tokens or _DEFAULT_MAX_TOKENS
        self._temperature: float = temperature if temperature is not None else _DEFAULT_TEMPERATURE

        self._http_limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(
        self,
        query: str,
        system_prompt: str,
        *,
        tenant_id: str = "unknown",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Route a query through the three-tier fallback chain."""
        messages = self._build_messages(system_prompt, query)
        return self.route_messages(
            messages=messages,
            tenant_id=tenant_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def route_messages(
        self,
        messages: List[Dict[str, str]],
        *,
        tenant_id: str = "unknown",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Route a list of OpenAI-formatted messages through the three-tier fallback chain.

        Args:
            messages:    List of message dicts (e.g., [{"role": "system", ...}, {"role": "user", ...}]).
            tenant_id:   UUID of the calling tenant — used for cost tracking.
            temperature: Override per-call temperature (default: gateway default).
            max_tokens:  Override per-call max_tokens (default: gateway default).

        Returns:
            LLM completion string.

        Raises:
            RuntimeError: If all three tiers fail.
        """
        temp = temperature if temperature is not None else self._temperature
        mtok = max_tokens or self._max_tokens
        errors: List[str] = []
        query_preview = messages[-1]["content"] if messages else ""

        # ── Tier 1: Local ────────────────────────────────────────────────────
        if self._local_url:
            try:
                result, usage = self._call_openai_compat(
                    base_url=self._local_url,
                    api_key="ollama",          # Ollama ignores the token
                    model=self._local_model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=mtok,
                )
                self._emit_usage(usage, provider="local", tenant_id=tenant_id, query=query_preview)
                return result
            except Exception as exc:
                err_msg = f"[Tier1/local] {exc}"
                logger.warning("LLMGateway %s — falling through: %s", tenant_id, err_msg)
                errors.append(err_msg)

        # ── Tier 2: OpenRouter ───────────────────────────────────────────────
        if self._or_key:
            for model in (_OPENROUTER_PRIMARY_MODEL, _OPENROUTER_SECONDARY_MODEL):
                try:
                    result, usage = self._call_openai_compat(
                        base_url=_OPENROUTER_BASE_URL,
                        api_key=self._or_key,
                        model=model,
                        messages=messages,
                        temperature=temp,
                        max_tokens=mtok,
                        extra_headers={
                            "HTTP-Referer": self._or_referer,
                            "X-Title": "Mergen Platform",
                        },
                    )
                    self._emit_usage(usage, provider="openrouter", tenant_id=tenant_id, query=query_preview)
                    return result
                except Exception as exc:
                    err_msg = f"[Tier2/openrouter/{model}] {exc}"
                    logger.warning("LLMGateway %s — falling through: %s", tenant_id, err_msg)
                    errors.append(err_msg)
        else:
            logger.info("LLMGateway: OPENROUTER_API_KEY not set — skipping Tier 2.")

        # ── Tier 3: Groq ─────────────────────────────────────────────────────
        if self._groq_key:
            for model in (_GROQ_PRIMARY_MODEL, _GROQ_FALLBACK_MODEL):
                try:
                    result, usage = self._call_openai_compat(
                        base_url=_GROQ_BASE_URL,
                        api_key=self._groq_key,
                        model=model,
                        messages=messages,
                        temperature=temp,
                        max_tokens=mtok,
                    )
                    self._emit_usage(usage, provider="groq", tenant_id=tenant_id, query=query_preview)
                    return result
                except Exception as exc:
                    err_msg = f"[Tier3/groq/{model}] {exc}"
                    logger.warning("LLMGateway %s — falling through: %s", tenant_id, err_msg)
                    errors.append(err_msg)
        else:
            logger.info("LLMGateway: GROQ_API_KEY not set — skipping Tier 3.")

        err_detail = (
            f"LLMGateway: all tiers exhausted for tenant '{tenant_id}'. "
            f"Errors: {'; '.join(errors)}"
        )
        logger.error(err_detail, exc_info=True)
        raise RuntimeError(err_detail)

    def last_usage(self) -> Optional[UsageRecord]:
        """Returns the UsageRecord from the most recent ``route()`` call."""
        return getattr(self, "_last_usage_record", None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(
        system_prompt: str,
        user_query: str,
    ) -> List[Dict[str, str]]:
        """Assemble the OpenAI-format messages list."""
        msgs: List[Dict[str, str]] = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": user_query})
        return msgs

    def _call_openai_compat(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """Single HTTP call to any OpenAI-compatible /v1/chat/completions endpoint.

        Returns:
            (completion_text, usage_dict)

        Raises:
            httpx.HTTPStatusError: On 4xx/5xx responses.
            ValueError: On unexpected response schema.
        """
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        url = f"{base_url.rstrip('/')}/chat/completions"

        with httpx.Client(timeout=self._timeout, limits=self._http_limits) as client:
            t0 = time.perf_counter()
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            latency_ms = (time.perf_counter() - t0) * 1000.0

        data: Dict[str, Any] = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise ValueError(f"Empty 'choices' in response from {url}: {data}")

        content: str = choices[0].get("message", {}).get("content", "")
        usage: Dict[str, Any] = data.get("usage", {})
        usage["_latency_ms"] = round(latency_ms, 2)
        usage["_model"] = model

        return content, usage

    def _emit_usage(
        self,
        usage: Dict[str, Any],
        *,
        provider: str,
        tenant_id: str,
        query: str,
    ) -> None:
        """Build a UsageRecord, store it, and emit a structured log line."""
        record = UsageRecord(
            tenant_id=tenant_id,
            model=usage.get("_model", "unknown"),
            provider=provider,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            latency_ms=usage.get("_latency_ms", 0.0),
            query_preview=query[:120],
        )
        self._last_usage_record: UsageRecord = record
        logger.info(
            "LLMGateway usage | %s",
            record.as_log_dict(),
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_gateway: Optional[LLMGateway] = None


def get_gateway() -> LLMGateway:
    """Return the process-wide singleton LLMGateway (lazy-initialised)."""
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway


def reset_gateway(gw: Optional[LLMGateway] = None) -> None:
    """Replace the singleton.  Useful in tests to inject a mock gateway."""
    global _gateway
    _gateway = gw
