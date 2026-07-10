"""
LLM integration with OpenRouter and Ollama fallback.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from dentbot.config import get_config

logger = logging.getLogger(__name__)

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Ollama API endpoint (default local)
OLLAMA_API_URL = "http://localhost:11434/api/chat"


class LLMClient:
    """LLM client with OpenRouter primary and Ollama fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        Initialize LLM client.
        
        Args:
            api_key: OpenRouter API key (if None, will try to get from config)
            model: Model name (if None, will try to get from config)
            timeout: Request timeout in seconds (if None, will try to get from config)
        """
        config = get_config()
        self.api_key = api_key if api_key is not None else config.get_openrouter_api_key()
        self.model = model if model is not None else config.get_openrouter_model()
        self.fallback_model = config.get_openrouter_fallback_model()
        self.base_url = config.get_openrouter_base_url()
        self.http_referer = config.get_openrouter_http_referer()
        self.x_title = config.get_openrouter_x_title()
        self.timeout = timeout if timeout is not None else config.get_llm_timeout()
        self.use_openrouter = bool(self.api_key)
        self.use_groq = self.use_openrouter

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Send a chat request to the LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            system_prompt: Optional system prompt to prepend
            temperature: Sampling temperature (0.0 = deterministic, 0.7 = default).
                         Pass 0.0 when calling the AuditorAgent for strict validation.
        
        Returns:
            Response text from the LLM
        
        Raises:
            Exception: If both OpenRouter and Ollama fail
        """
        # Prepare messages with system prompt if provided
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({
                "role": "system",
                "content": system_prompt,
            })
        formatted_messages.extend(messages)

        # ── AIOps timing ─────────────────────────────────────────────
        _t0 = time.perf_counter()
        self._last_usage: Dict[str, Any] = {}

        # Try OpenRouter first if API key is available
        if self.use_openrouter:
            try:
                result = self._chat_openrouter(formatted_messages, model_name=self.model, temperature=temperature)
            except Exception as e:
                logger.warning(f"Primary OpenRouter model failed ({self.model}): {e}")
                if self.fallback_model and self.fallback_model != self.model:
                    try:
                        logger.info(f"Trying fallback OpenRouter model: {self.fallback_model}")
                        result = self._chat_openrouter(formatted_messages, model_name=self.fallback_model, temperature=temperature)
                    except Exception as fallback_error:
                        logger.warning(f"Fallback OpenRouter model failed ({self.fallback_model}): {fallback_error}. Trying Ollama fallback...")
                        result = self._chat_ollama(formatted_messages, temperature=temperature)
                else:
                    logger.warning("No distinct fallback OpenRouter model configured. Trying Ollama fallback...")
                    result = self._chat_ollama(formatted_messages, temperature=temperature)
        else:
            # Use Ollama directly if no OpenRouter API key
            logger.info("No OpenRouter API key found. Using Ollama...")
            result = self._chat_ollama(formatted_messages, temperature=temperature)

        # ── Fire-and-forget telemetry ──────────────────────────────────────
        _elapsed_ms = (time.perf_counter() - _t0) * 1000.0
        try:
            import asyncio as _asyncio
            from dentbot.core.telemetry import record_metric as _record_metric
            _loop = _asyncio.get_event_loop()
            if _loop.is_running():
                _usage = self._last_usage  # populated by _chat_openrouter
                _loop.create_task(
                    _record_metric(
                        "llm_execution",
                        round(_elapsed_ms, 3),
                        metadata={
                            "model": self.model,
                            "prompt_tokens": _usage.get("prompt_tokens"),
                            "completion_tokens": _usage.get("completion_tokens"),
                            "total_tokens": _usage.get("total_tokens"),
                        },
                    )
                )
        except Exception:  # pragma: no cover
            pass  # Telemetry must never affect the caller

        return result

    def _chat_openrouter(self, messages: List[Dict[str, str]], model_name: Optional[str] = None, temperature: float = 0.7) -> str:
        """Send chat request to OpenRouter API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.http_referer,
            "X-Title": self.x_title,
        }
        
        payload = {
            "model": model_name or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
        }

        with httpx.Client(
            timeout=self.timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        ) as client:
            response = client.post(f"{self.base_url.rstrip('/')}" + "/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Extract content from response
            if "choices" in data and len(data["choices"]) > 0:
                # ── Capture token usage for telemetry ─────────────────────────
                if hasattr(self, "_last_usage") and isinstance(data.get("usage"), dict):
                    self._last_usage = data["usage"]
                return data["choices"][0]["message"]["content"]
            else:
                raise ValueError("Invalid response format from OpenRouter API")

    def _chat_ollama(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """Send chat request to Ollama API (fallback)."""
        # Ollama chat API expects messages in a specific format
        # Convert system message to a regular message if present
        ollama_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Ollama uses "system" role, but we'll convert it to user if needed
            if role == "system":
                # Prepend system message as a user message with context
                ollama_messages.append({"role": "user", "content": f"[System Context] {content}"})
            else:
                ollama_messages.append({"role": role, "content": content})

        model_name = get_config().get_ollama_model()
        payload = {
            "model": model_name,  # Config'ten alınan Ollama model adı
            "messages": ollama_messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        try:
            with httpx.Client(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            ) as client:
                response = client.post(OLLAMA_API_URL, json=payload)
                response.raise_for_status()
                data = response.json()
                
                if "message" in data and "content" in data["message"]:
                    return data["message"]["content"]
                elif "response" in data:
                    # Fallback for older Ollama API format
                    return data["response"]
                else:
                    raise ValueError("Invalid response format from Ollama API")
        except httpx.ConnectError:
            raise ConnectionError(
                "Could not connect to Ollama. "
                "Make sure Ollama is running on localhost:11434. "
                "You can install Ollama from https://ollama.ai"
            )

    def simple_query(self, question: str, system_prompt: Optional[str] = None) -> str:
        """
        Simple query interface for asking a single question.
        
        Args:
            question: The question to ask
            system_prompt: Optional system prompt
        
        Returns:
            Response text
        """
        messages = [
            {
                "role": "user",
                "content": question,
            }
        ]
        return self.chat(messages, system_prompt=system_prompt)


# Global LLM client instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the global LLM client instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def set_llm_client(client: LLMClient) -> None:
    """Set a custom LLM client instance (useful for testing)."""
    global _llm_client
    _llm_client = client
