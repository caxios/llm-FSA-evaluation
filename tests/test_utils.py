import json
import math
import os
from pathlib import Path

import pytest

from src.utils import io
from src.utils.hashing import canonical_json, stable_hash


def test_stable_hash_ignores_key_order():
    assert stable_hash({"a": 1, "b": [1, 2]}) == stable_hash({"b": [1, 2], "a": 1})


def test_stable_hash_golden_value():
    # Fixed value: a change here means every cache key in the project changes.
    assert stable_hash({"model": "m", "rep": 1, "text": "삼성"}) == (
        "2d48eb0d1cb8d3c73e783011bf36215c7b13ec3f32965444b740a64fc3b46f90"
    )


def test_canonical_json_keeps_korean_and_handles_nan():
    s = canonical_json({"name": "삼성전자", "x": math.nan})
    assert "삼성전자" in s
    assert '"nan"' in s


def test_write_raw_creates_sidecar_and_redacts(tmp_path: Path):
    target = tmp_path / "dart" / "fs" / "x.json"
    io.write_raw(
        target,
        {"status": "000", "list": []},
        url="https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
        params={"crtfc_key": "SECRET123", "corp_code": "00126380"},
        status="000",
    )
    payload, meta = io.read_raw(target)
    assert json.loads(payload)["status"] == "000"
    assert meta["params"]["crtfc_key"] == io.REDACTED
    assert meta["params"]["corp_code"] == "00126380"
    assert "SECRET123" not in io.meta_path(target).read_text(encoding="utf-8")
    assert "fetched_at" in meta


def test_atomic_write_leaves_no_partial_file(tmp_path: Path, monkeypatch):
    target = tmp_path / "out.bin"
    target.write_bytes(b"old")

    def boom(src, dst):
        raise OSError("simulated crash during rename")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        io.atomic_write(target, b"new")
    assert target.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["out.bin"]
