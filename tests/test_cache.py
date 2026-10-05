"""P5: cache keys, SQLite cache and JSONL log."""

import json

import pytest

from src.agents.base import cache_key
from src.agents.llm_client import FakeClient
from src.agents.plain import PlainAgent
from src.runner.cache import CallCache
from src.runner.logger import log_record
from tests.p5_helpers import MODEL, valuation_json
from tests.test_agents import request


def test_cache_key_sensitivity():
    ident = {"model_id": "m", "decoding": {"temperature": 0.3}}
    base = cache_key(request(), ident)
    assert base == cache_key(request(), ident)
    changed = request(messages=[{"role": "user", "content": "M00l"}])
    assert cache_key(changed, ident) != base                       # one character
    assert cache_key(request(rep=1), ident) != base
    assert cache_key(request(structure="T"), ident) != base
    assert cache_key(request(), {**ident, "decoding": {"temperature": 0.5}}) != base
    other_exp = request().model_copy(update={"experiment": "E7", "job_id": "x"})
    assert cache_key(other_exp, ident) == base                       # experiment not in key


def test_put_get_and_resume(tmp_path):
    path = tmp_path / "c.sqlite"
    cache = CallCache(path)
    rec = PlainAgent(FakeClient([valuation_json()]), MODEL).run(request())
    assert cache.get(rec.cache_key) is None
    cache.put(rec)
    cache.put(rec)                                                  # idempotent
    assert len(cache) == 1 and cache.has(rec.cache_key)
    cache.close()
    again = CallCache(path)                                         # "after a crash"
    got = again.get(rec.cache_key)
    assert got == rec and len(again.records("fake")) == 1 and again.records("other") == []


def test_put_is_transactional(tmp_path, monkeypatch):
    cache = CallCache(tmp_path / "c.sqlite")
    rec = PlainAgent(FakeClient([valuation_json()]), MODEL).run(request())

    def boom(*a, **k):
        raise RuntimeError("crash while serializing")

    monkeypatch.setattr(type(rec), "model_dump_json", boom)
    with pytest.raises(RuntimeError):
        cache.put(rec)
    monkeypatch.undo()
    assert len(cache) == 0
    cache.put(rec)
    assert len(cache) == 1


def test_log_record(tmp_path):
    rec = PlainAgent(FakeClient([valuation_json()]), MODEL).run(request())
    path = log_record(rec, tmp_path)
    log_record(rec, tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert path.parent.name == "T" and len(lines) == 2
    assert json.loads(lines[0])["cache_key"] == rec.cache_key
