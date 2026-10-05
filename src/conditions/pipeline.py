"""P4 data flow: identifier dictionaries, industry labels, fake names and conditioned
packages for the 150 sample firms. Inputs are P1/P2 outputs on disk (no network)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

from src.conditions.build import ConditionCode, ConditionedPackage, make_condition
from src.conditions.identifiers import FirmIdentifiers, build_identifiers
from src.conditions.industry import label_for
from src.config import CONFIG_DIR, PROJECT_ROOT
from src.data.package_schema import InputPackage

PROCESSED = PROJECT_ROOT / "data" / "processed"
RAW_DART = PROJECT_ROOT / "data" / "raw" / "dart"
IDENTIFIERS_DIR = PROCESSED / "identifiers"
FAKE_NAMES = PROCESSED / "fake_names.parquet"
OVERRIDES = CONFIG_DIR / "redaction_overrides.yaml"
FISCAL_YEAR = 2025


def load_sample() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "sample.parquet")


PACKAGES_DIR = PROCESSED / "packages"
DEV_DIR = PROCESSED / "dev"                 # P7 dev set (prompt iteration, outside the sample)


def load_package(firm_id: str, packages_dir: Path | None = None) -> InputPackage:
    path = (packages_dir or PACKAGES_DIR) / f"{firm_id}.json"
    return InputPackage.from_json(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def companies() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "p1" / "companies.parquet").set_index("corp_code")


def investments(corp_code: str, year: int = FISCAL_YEAR) -> pd.DataFrame:
    path = RAW_DART / "investments" / corp_code / f"{year}_11011.json"
    if not path.exists():
        return pd.DataFrame()
    body = json.loads(path.read_text(encoding="utf-8"))
    return pd.DataFrame(body.get("list", []))


def load_overrides(path: Path = OVERRIDES) -> dict:
    if not path.exists():
        return {"firms": {}, "ignore": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {"firms": data.get("firms") or {}, "ignore": data.get("ignore") or []}


@lru_cache(maxsize=1)
def peer_counts() -> dict[str, int]:
    u = pd.read_parquet(PROCESSED / "p1" / "universe.parquet")
    u = u[u["in_universe"].eq(True)] if "in_universe" in u else u
    return u["ksic2"].dropna().astype(str).value_counts().to_dict()


def industry_label(ksic2: str | None) -> str | None:
    return label_for(ksic2, peer_counts())


def identifiers_for(row: dict, overrides: dict | None = None) -> FirmIdentifiers:
    comp = companies().loc[row["corp_code"]].to_dict()
    comp["stock_code"] = comp.get("stock_code") or row.get("stock_code")
    ov = (overrides or load_overrides())["firms"].get(row["firm_id"], {})
    return build_identifiers(row["firm_id"], comp, investments(row["corp_code"]), ov)


def save_identifiers(ids: FirmIdentifiers) -> None:
    IDENTIFIERS_DIR.mkdir(parents=True, exist_ok=True)
    (IDENTIFIERS_DIR / f"{ids.firm_id}.json").write_text(ids.model_dump_json(indent=1),
                                                       encoding="utf-8")


def load_identifiers(firm_id: str) -> FirmIdentifiers:
    return FirmIdentifiers.model_validate_json(
        (IDENTIFIERS_DIR / f"{firm_id}.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def fake_names() -> dict[str, str]:
    df = pd.read_parquet(FAKE_NAMES)
    return dict(zip(df["firm_id"], df["fake_name"], strict=True))


def conditioned(firm_id: str, condition: ConditionCode) -> ConditionedPackage:
    """The package of one firm in one information condition (used by P5 onwards)."""
    pkg = load_package(firm_id)
    ksic2 = (pkg.meta.ksic or "")[:2] or None
    return make_condition(pkg, condition, load_identifiers(firm_id),
                          fake_name=fake_names().get(firm_id) if condition == "D" else None,
                          industry_label=industry_label(ksic2))
