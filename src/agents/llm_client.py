"""LLM clients (P5 §5.3).

`OpenAICompatibleClient` covers every model in config/models.yaml (Gemini through its
OpenAI-compatible endpoint). Concurrency is bounded per model (`max_concurrency`) and by a
requests-per-minute limiter; transient errors (429, 5xx, timeouts, connection errors) are
retried with exponential backoff up to 6 attempts, hard errors are raised. Tests use
`FakeClient`.
"""

from __future__ import annotations

import os
import re
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

import requests
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import ModelConfig, require_env

REFUSAL = re.compile(r"I can(?:'|no)t (?:help|assist|provide)|I'm sorry|죄송하지만|"
                     r"도와드릴 수 없|제공할 수 없|답변할 수 없", re.IGNORECASE)


class RawResponse(BaseModel):
    text: str
    model_reported: str
    finish_reason: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    created_at: datetime
    request_id: str | None = None
    refusal: bool = False


class LLMClient(Protocol):
    def complete(self, messages: list[dict], cfg: ModelConfig) -> RawResponse: ...


class TransientError(Exception):
    pass


def is_refusal(text: str, provider_flag: bool = False) -> bool:
    if provider_flag or not text.strip():
        return True
    return "{" not in text and bool(REFUSAL.search(text))


def decoding(cfg: ModelConfig) -> dict:
    """Decoding configuration recorded with every call and hashed into the cache key."""
    return {"temperature": cfg.temperature, "max_tokens": cfg.max_output_tokens,
            "json_mode": True}


class RateLimiter:
    """At most `rpm` request starts in any 60-second window."""

    def __init__(self, rpm: int | None):
        self.rpm = rpm
        self.starts: deque[float] = deque()
        self.lock = threading.Lock()

    def wait(self) -> None:
        if not self.rpm:
            return
        while True:
            with self.lock:
                now = time.monotonic()
                while self.starts and now - self.starts[0] >= 60:
                    self.starts.popleft()
                if len(self.starts) < self.rpm:
                    self.starts.append(now)
                    return
                delay = 60 - (now - self.starts[0])
            time.sleep(max(delay, 0.05))


def max_concurrency(cfg: ModelConfig) -> int:
    """Per-model concurrency; LLM_MAX_CONCURRENCY overrides the config (operational only,
    outputs do not depend on it)."""
    env = os.environ.get("LLM_MAX_CONCURRENCY")
    return int(env) if env else cfg.max_concurrency


class OpenAICompatibleClient:
    def __init__(self, cfg: ModelConfig, rpm: int | None = 600, timeout: float = 300.0,
                 session: requests.Session | None = None):
        self.cfg = cfg
        self.key = require_env(cfg.api_key_env)
        self.sem = threading.BoundedSemaphore(max_concurrency(cfg))
        self.limiter = RateLimiter(rpm)
        self.timeout = timeout
        self.session = session or requests.Session()

    def complete(self, messages: list[dict], cfg: ModelConfig | None = None) -> RawResponse:
        cfg = cfg or self.cfg
        with self.sem:
            return self._post(messages, cfg)

    @retry(retry=retry_if_exception_type(TransientError), stop=stop_after_attempt(6),
           wait=wait_exponential(multiplier=2, min=2, max=120), reraise=True)
    def _post(self, messages: list[dict], cfg: ModelConfig) -> RawResponse:
        self.limiter.wait()
        dec = decoding(cfg)
        body = {"model": cfg.model_id, "messages": messages, "temperature": dec["temperature"],
                "max_tokens": dec["max_tokens"]}
        if dec["json_mode"]:
            body["response_format"] = {"type": "json_object"}
        t0 = time.monotonic()
        try:
            resp = self.session.post(f"{(cfg.base_url or '').rstrip('/')}/chat/completions",
                                     json=body, timeout=self.timeout,
                                     headers={"Authorization": f"Bearer {self.key}"})
        except (requests.Timeout, requests.ConnectionError) as e:
            raise TransientError(str(e)) from e
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        text = msg.get("content") or ""
        usage = data.get("usage") or {}
        tin = int(usage.get("prompt_tokens", 0))
        # thinking tokens are billed as output but may be missing from completion_tokens
        tout = max(int(usage.get("completion_tokens", 0)),
                   int(usage.get("total_tokens", 0)) - tin)
        return RawResponse(
            text=text, model_reported=data.get("model") or cfg.model_id,
            finish_reason=choice.get("finish_reason") or "", tokens_in=tin, tokens_out=tout,
            latency_s=time.monotonic() - t0, created_at=datetime.now(UTC),
            request_id=data.get("id") or resp.headers.get("x-request-id"),
            refusal=is_refusal(text, bool(msg.get("refusal"))))


class FakeClient:
    """Scripted responses for tests: a list of texts (consumed in order) or a function."""

    def __init__(self, responses: list[str] | Callable[[list[dict]], str],
                 model: str = "fake-model"):
        self.responses = responses
        self.model = model
        self.calls: list[list[dict]] = []
        self.lock = threading.Lock()

    def complete(self, messages: list[dict], cfg: ModelConfig | None = None) -> RawResponse:
        with self.lock:
            self.calls.append(messages)
            if callable(self.responses):
                text = self.responses(messages)
            else:
                text = self.responses.pop(0)
        return RawResponse(text=text, model_reported=self.model, finish_reason="stop",
                           tokens_in=sum(len(m["content"]) for m in messages) // 2,
                           tokens_out=len(text) // 2, latency_s=0.0,
                           created_at=datetime.now(UTC), refusal=is_refusal(text))


def make_client(cfg: ModelConfig) -> LLMClient:
    if cfg.provider == "openai_compatible":
        return OpenAICompatibleClient(cfg)
    raise NotImplementedError(f"provider '{cfg.provider}' has no client yet "
                              "(all configured models use the OpenAI-compatible endpoint)")
