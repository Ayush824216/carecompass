"""Provider-agnostic hosted-LLM wrapper (JSON-mode chat completion).

Configured by env vars LLM_PROVIDER, LLM_MODEL, LLM_API_KEY (+ optional LLM_BASE_URL, LLM_TIMEOUT_S).
Supported providers: openai, groq, openrouter, together (OpenAI-compatible), gemini, anthropic, none.
Every call has a hard timeout and returns None on any failure so callers can fall back. The API key is
never logged or included in error messages.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional

import httpx

from .config import get_settings

log = logging.getLogger("carecompass.llm")

OPENAI_COMPAT = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "together": "https://api.together.xyz/v1",
}

_client: Optional[httpx.Client] = None


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=get_settings().llm_timeout_s)
    return _client


def available() -> bool:
    s = get_settings()
    return s.llm_provider not in ("", "none") and bool(s.llm_api_key) and bool(s.llm_model)


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def chat_json(system: str, user: str, max_tokens: int = 400, temperature: float = 0.0,
              timeout: Optional[float] = None) -> Optional[dict]:
    """Return the parsed JSON object from the model, or None on timeout/error/invalid JSON."""
    if not available():
        return None
    s = get_settings()
    timeout = timeout or s.llm_timeout_s
    t0 = time.perf_counter()
    try:
        if s.llm_provider in OPENAI_COMPAT or s.llm_provider == "openai_compatible":
            base = os.getenv("LLM_BASE_URL") or OPENAI_COMPAT.get(s.llm_provider, "")
            r = _http().post(
                f"{base.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {s.llm_api_key}"},
                json={"model": s.llm_model, "temperature": temperature, "max_tokens": max_tokens,
                      "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                timeout=timeout,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        elif s.llm_provider == "gemini":
            r = _http().post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{s.llm_model}:generateContent",
                headers={"x-goog-api-key": s.llm_api_key},
                json={"systemInstruction": {"parts": [{"text": system}]},
                      "contents": [{"role": "user", "parts": [{"text": user}]}],
                      "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens,
                                           "responseMimeType": "application/json"}},
                timeout=timeout,
            )
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        elif s.llm_provider == "anthropic":
            r = _http().post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": s.llm_api_key, "anthropic-version": "2023-06-01"},
                json={"model": s.llm_model, "max_tokens": max_tokens, "temperature": temperature,
                      "system": system, "messages": [{"role": "user", "content": user}]},
                timeout=timeout,
            )
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")
        else:
            log.warning("unknown LLM_PROVIDER=%s", s.llm_provider)
            return None
    except httpx.TimeoutException:
        log.warning("llm timeout after %.1fs", time.perf_counter() - t0)
        return None
    except httpx.HTTPStatusError as e:
        log.warning("llm http %s", e.response.status_code)
        return None
    except Exception as e:  # network, schema of provider response, ...
        log.warning("llm error %s", e.__class__.__name__)
        return None
    log.info("llm ok provider=%s ms=%.0f", s.llm_provider, (time.perf_counter() - t0) * 1000)
    return _extract_json(text)
