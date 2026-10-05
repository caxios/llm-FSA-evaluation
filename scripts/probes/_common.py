"""Shared helpers for live API probes (P0 Step 0.5).

Probes are run manually, never by pytest. They print findings and save trimmed sample
responses under tests/fixtures/<source>/ for the P1 parser tests.
"""

from __future__ import annotations

import io
import json
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.config import require_env  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
RAW = ROOT / "data" / "raw"
DART_BASE = "https://opendart.fss.or.kr/api"

SAMSUNG = "00126380"  # Samsung Electronics: large KOSPI firm with preferred shares

# Windows consoles may not be UTF-8; avoid crashes when printing Korean text.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def dart_key() -> str:
    return require_env("OPENDARTAPI_KEY")


def dart_get(endpoint: str, **params: Any) -> tuple[requests.Response, float]:
    """GET an OpenDART endpoint; returns (response, latency seconds)."""
    params = {"crtfc_key": dart_key(), **params}
    t0 = time.perf_counter()
    resp = requests.get(f"{DART_BASE}/{endpoint}", params=params, timeout=60)
    return resp, time.perf_counter() - t0


def dart_json(endpoint: str, **params: Any) -> tuple[dict, float]:
    resp, latency = dart_get(endpoint, **params)
    resp.raise_for_status()
    return resp.json(), latency


def save_fixture(source: str, name: str, payload: Any) -> Path:
    """Save a trimmed response as a fixture (JSON or raw text/bytes)."""
    path = FIXTURES / source / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, (dict, list)):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    elif isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_bytes(payload)
    return path


def trim(payload: dict, key: str = "list", n: int = 40) -> dict:
    """Keep only the first n rows of a list-valued key."""
    out = dict(payload)
    if isinstance(out.get(key), list):
        out[key] = out[key][:n]
    return out


def corp_codes() -> list[dict[str, str]]:
    """Download (once) and parse corpCode.xml into a list of dicts."""
    cache = RAW / "dart" / "corpCode" / "corpCode.xml"
    if not cache.exists():
        resp, _ = dart_get("corpCode.xml")
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            xml_name = zf.namelist()[0]
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(zf.read(xml_name))
    from lxml import etree

    tree = etree.parse(str(cache))
    rows = []
    for el in tree.getroot().iter("list"):
        rows.append({child.tag: (child.text or "").strip() for child in el})
    return rows


def section(title: str) -> None:
    print(f"\n=== {title} ===")
