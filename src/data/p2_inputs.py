"""Load P1 outputs needed to build packages (reads the raw cache; no new API calls
for anything P1 already fetched)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from src.config import PROJECT_ROOT, Config
from src.data.dart_client import DartClient
from src.data.package_builder import BuildResult, build_package

P1_DIR = PROJECT_ROOT / "data" / "processed" / "p1"
P2_DIR = PROJECT_ROOT / "data" / "processed" / "p2"


@dataclass
class P1Data:
    universe: pd.DataFrame
    companies: pd.DataFrame
    fs_status: pd.DataFrame

    @classmethod
    def load(cls, p1_dir: Path = P1_DIR) -> P1Data:
        return cls(
            universe=pd.read_parquet(p1_dir / "universe.parquet"),
            companies=pd.read_parquet(p1_dir / "companies.parquet"),
            fs_status=pd.read_parquet(p1_dir / "fs_status.parquet"),
        )

    def table(self, name: str, p1_dir: Path = P1_DIR) -> pd.DataFrame:
        return pd.read_parquet(p1_dir / f"{name}.parquet")


def build_one(dart: DartClient, cfg: Config, row, company: dict, fs_row) -> BuildResult:
    t_post = cfg.require_dates()[0]
    fy = int(fs_row.fiscal_year)
    fs = dart.financial_statements(row.corp_code, fy, fs_div=fs_row.fs_div)
    return build_package(
        corp_code=row.corp_code, fs=fs, fs_div=fs_row.fs_div, company=company,
        shares=dart.share_totals(row.corp_code, fy), dividends=dart.dividends(row.corp_code, fy),
        fiscal_year=fy, eval_date=t_post, market=row.market,
    )


def iter_builds(dart: DartClient, cfg: Config, data: P1Data,
                corp_codes: list[str] | None = None) -> Iterator[BuildResult]:
    uni = data.universe[data.universe["in_universe"]]
    if corp_codes is not None:
        uni = uni[uni["corp_code"].isin(corp_codes)]
    companies = data.companies.set_index("corp_code")
    fs_status = data.fs_status.set_index("corp_code")
    for row in uni.itertuples(index=False):
        if row.corp_code not in fs_status.index or pd.isna(fs_status.loc[row.corp_code,
                                                                         "fs_div"]):
            yield BuildResult(row.corp_code, None, "no_statements")
            continue
        company = companies.loc[row.corp_code].to_dict() if row.corp_code in companies.index \
            else {}
        company["corp_code"] = row.corp_code
        yield build_one(dart, cfg, row, company, fs_status.loc[row.corp_code])


def filing_date(rcept_no: str) -> date:
    return date(int(rcept_no[:4]), int(rcept_no[4:6]), int(rcept_no[6:8]))
