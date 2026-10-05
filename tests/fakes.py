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


class FixtureStore:
    """PackageStore over the fixture packages (runner and job-builder tests)."""

    def __init__(self, names: list[str] | None = None):
        from src.conditions.identifiers import FirmIdentifiers, name_variants

        self._ids = FirmIdentifiers
        self._variants = name_variants
        self.pkgs = {}
        for n in names or PACKAGE_NAMES:
            p = load_package(n)
            self.pkgs[p.meta.firm_id] = p
        import pandas as pd

        self.sample = pd.DataFrame({"firm_id": list(self.pkgs),
                                    "group": [p.meta.group for p in self.pkgs.values()]}
                                   ).set_index("firm_id")

    def package(self, firm_id):
        return self.pkgs[firm_id]

    def group(self, firm_id):
        return self.pkgs[firm_id].meta.group

    def condition(self, pkg, condition):
        from src.conditions.build import make_condition

        ids = self._ids(firm_id=pkg.meta.firm_id, names=self._variants(pkg.meta.real_name))
        return make_condition(pkg, condition, ids,
                              fake_name="마루테크" if condition == "D" else None)

    def real_name(self, firm_id):
        return self.pkgs[firm_id].meta.real_name

    def eval_date(self):
        return next(iter(self.pkgs.values())).meta.eval_date
