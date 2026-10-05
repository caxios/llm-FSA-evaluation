"""Test doubles for HTTP sessions (no network in tests)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(*parts: str) -> Any:
    path = FIXTURES.joinpath(*parts)
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")


PACKAGE_NAMES = ["large_pref", "mid", "small_cb_multi", "small_cb_single", "unmapped_heavy"]
CB_PACKAGE_NAMES = ["small_cb_multi", "small_cb_single", "unmapped_heavy"]


def load_package(name: str):
    from src.data.package_schema import InputPackage

    path = FIXTURES / "packages" / f"{name}.json"
    return InputPackage.from_json(path.read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status_code: int = 200, body: Any = None, content: bytes | None = None):
        self.status_code = status_code
        self._body = body
        if content is None:
            content = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None \
                else b""
        self.content = content
        self.text = content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        if self._body is None:
            return json.loads(self.content)
        return self._body


class FakeSession:
    """Routes GET requests to handlers keyed by the last URL path segment."""

    def __init__(self, routes: dict[str, Callable[[dict], FakeResponse]]):
        self.routes = routes
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, params: dict | None = None, headers: dict | None = None,
            timeout: float | None = None) -> FakeResponse:
        endpoint = url.rsplit("/", 1)[-1]
        self.calls.append((endpoint, dict(params or {})))
        if endpoint not in self.routes:
            raise AssertionError(f"unexpected request to {endpoint}")
        return self.routes[endpoint](dict(params or {}))
