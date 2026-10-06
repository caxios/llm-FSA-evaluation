"""P5: OpenAI-compatible client against a fake HTTP session (no network)."""

import pytest
import requests
from tenacity import wait_none

from src.agents.llm_client import (
    OpenAICompatibleClient,
    RateLimiter,
    TransientError,
    decoding,
    is_refusal,
    make_client,
)
from tests.p5_helpers import MODEL


class Resp:
    def __init__(self, status, body=None, text=""):
        self.status_code, self._body, self.text, self.headers = status, body, text, {}

    def json(self):
        return self._body


class Session:
    def __init__(self, items):
        self.items, self.bodies = list(items), []

    def post(self, url, json=None, timeout=None, headers=None):
        self.bodies.append((url, json, headers))
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


OK = Resp(200, {"id": "req-1", "model": "fake-model-001",
                "choices": [{"message": {"content": '{"a": 1}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10,
                          "total_tokens": 150}})


@pytest.fixture
def client_factory(monkeypatch):
    monkeypatch.setenv("FAKE_API_KEY", "secret")
    monkeypatch.setattr(OpenAICompatibleClient._post.retry, "wait", wait_none())

    def make(items):
        return OpenAICompatibleClient(MODEL, rpm=None, session=Session(items))
    return make


def test_success_and_request_body(client_factory):
    c = client_factory([OK])
    r = c.complete([{"role": "user", "content": "hi"}])
    assert r.text == '{"a": 1}' and r.model_reported == "fake-model-001"
    assert (r.tokens_in, r.tokens_out) == (100, 50)        # thinking tokens counted
    assert r.request_id == "req-1" and not r.refusal
    url, body, headers = c.session.bodies[0]
    assert url == "https://example.invalid/v1/chat/completions"
    assert body["response_format"] == {"type": "json_object"}
    assert body["temperature"] == 0.3 and headers["Authorization"] == "Bearer secret"


def test_transient_errors_are_retried(client_factory):
    c = client_factory([Resp(429, text="rate"), requests.Timeout("t"), Resp(503), OK])
    assert c.complete([{"role": "user", "content": "x"}]).text == '{"a": 1}'
    assert len(c.session.bodies) == 4


def test_gives_up_after_ten_attempts(client_factory):
    c = client_factory([Resp(500)] * 10)
    with pytest.raises(TransientError):
        c.complete([{"role": "user", "content": "x"}])


def test_hard_error_raises(client_factory):
    c = client_factory([Resp(400, text="bad request")])
    with pytest.raises(RuntimeError, match="400"):
        c.complete([{"role": "user", "content": "x"}])
    assert len(c.session.bodies) == 1


def test_refusal_detection():
    assert is_refusal("") and is_refusal("죄송하지만 도와드릴 수 없습니다.")
    assert is_refusal("ok", provider_flag=True)
    assert not is_refusal('죄송하지만 {"a": 1}') and not is_refusal("설명 텍스트")


def test_misc():
    assert decoding(MODEL) == {"temperature": 0.3, "max_tokens": 4096, "json_mode": True}
    RateLimiter(None).wait()
    lim = RateLimiter(2)
    lim.wait()
    lim.wait()
    assert len(lim.starts) == 2
    with pytest.raises(NotImplementedError):
        make_client(MODEL.model_copy(update={"provider": "anthropic"}))
