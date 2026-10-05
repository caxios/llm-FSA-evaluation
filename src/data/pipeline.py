"""P1 fetch pipeline: resumable stages that fill data/raw/ and write P1 tables.

Each stage reads its inputs from data/processed/p1/ (written by earlier stages) and relies on
the clients' raw caches, so re-running a stage costs no API calls for completed work.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.config import PROJECT_ROOT, Config
from src.data.cb_collect import (
    collect_cb_terms,
    collect_refixings,
    find_cb_issuers,
    unredeemed_cb_table,
)
from src.data.dart_client import DartClient, DartError
from src.data.krx_client import KrxClient, KrxError, KrxNotApproved
from src.data.price_client import PriceClient, PriceNotFound
from src.data.rate_limit import QuotaExhausted
from src.data.universe import build_universe, fs_status

log = logging.getLogger(__name__)

OUT_DIR = PROJECT_ROOT / "data" / "processed" / "p1"


@dataclass
class Context:
    cfg: Config
    dart: DartClient
    krx: KrxClient | None
    prices: PriceClient
    out_dir: Path = OUT_DIR
    limit: int | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def t_post(self) -> date:
        return self.cfg.require_dates()[0]

    @property
    def fiscal_year(self) -> int:
        """Latest fiscal year whose annual report is due before t_post."""
        return self.t_post.year - 1

    @property
    def cb_window(self) -> tuple[date, date]:
        years = self.cfg.sample.cb_search_years
        return date(self.t_post.year - years, self.t_post.month, 1), self.t_post

    def path(self, name: str) -> Path:
        return self.out_dir / f"{name}.parquet"

    def save(self, name: str, df: pd.DataFrame) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(self.path(name), index=False)
        log.info("wrote %s (%d rows)", self.path(name).name, len(df))

    def load(self, name: str) -> pd.DataFrame:
        if not self.path(name).exists():
            raise FileNotFoundError(f"{self.path(name)} missing; run its stage first")
        return pd.read_parquet(self.path(name))

    def limited(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.head(self.limit) if self.limit else df


def _each(ctx: Context, items: list, fn: Callable, what: str) -> list:
    """Apply fn to items; log failures and keep going (quota exhaustion stops the stage)."""
    results, failures = [], 0
    for i, item in enumerate(items, 1):
        try:
            results.append(fn(item))
        except QuotaExhausted:
            log.error("%s: quota exhausted after %d/%d; re-run tomorrow (cached work is kept)",
                      what, i - 1, len(items))
            raise
        except (DartError, KrxError, PriceNotFound, ValueError, KeyError) as exc:
            failures += 1
            log.warning("%s: %s failed: %s", what, item, exc)
        if i % 200 == 0:
            log.info("%s: %d/%d", what, i, len(items))
    if failures:
        ctx.notes.append(f"{what}: {failures} failures out of {len(items)}")
    return results


# ---------------------------------------------------------------------------- stages


def stage_corpcodes(ctx: Context) -> None:
    codes = ctx.dart.corp_codes()
    listed = codes[codes["stock_code"].str.strip() != ""]
    ctx.save("corp_codes_listed", listed)


def _krx_daily(ctx: Context, market: str) -> pd.DataFrame | None:
    if ctx.krx is None:
        return None
    try:
        return ctx.krx.daily_on_or_before(ctx.t_post, market)
    except KrxNotApproved:
        ctx.notes.append(f"KRX {market} daily service not approved; {market} market data "
                         "(market cap, halt flag) unavailable")
        log.warning("KRX %s service not approved", market)
        return None


def stage_listing(ctx: Context) -> None:
    for market in ("KOSPI", "KOSDAQ"):
        df = _krx_daily(ctx, market)
        if df is not None:
            ctx.save(f"krx_daily_{market}", df)


def company_targets(ctx: Context) -> list[str]:
    """corp_codes that can enter the universe: KOSPI issues trading on KRX at t_post (when
    the KRX data is available, else all listed codes) and KOSDAQ CB issuers.

    Fetching company.json only for these avoids ~2,000 calls for delisted or unrelated firms.
    """
    listed = ctx.load("corp_codes_listed")
    issuers = ctx.load("cb_issuers")["corp_code"].tolist()
    if ctx.path("krx_daily_KOSPI").exists():
        tickers = set(ctx.load("krx_daily_KOSPI")["ticker"])
        kospi = listed[listed["stock_code"].isin(tickers)]["corp_code"].tolist()
    else:
        ctx.notes.append("KRX KOSPI data unavailable: company.json fetched for all listed codes")
        kospi = listed["corp_code"].tolist()
    targets = list(dict.fromkeys(kospi + issuers))
    if ctx.limit:  # smoke runs: take a few of each kind
        targets = list(dict.fromkeys(kospi[: ctx.limit] + issuers[: ctx.limit]))
    return targets


def stage_company(ctx: Context) -> None:
    rows = _each(ctx, company_targets(ctx), ctx.dart.company, "company")
    keep = ["corp_code", "corp_name", "corp_name_eng", "stock_name", "stock_code", "ceo_nm",
            "corp_cls", "induty_code", "adres", "hm_url", "est_dt", "acc_mt"]
    df = pd.DataFrame([r for r in rows if r])
    ctx.save("companies", df.reindex(columns=keep))


def stage_cb_issuers(ctx: Context) -> None:
    bgn, end = ctx.cb_window
    ctx.save("cb_issuers", find_cb_issuers(ctx.dart, bgn, end, corp_cls="K"))


def stage_universe(ctx: Context) -> None:
    def optional(name: str) -> pd.DataFrame | None:
        return ctx.load(name) if ctx.path(name).exists() else None

    uni = build_universe(ctx.load("companies"), optional("krx_daily_KOSPI"),
                         optional("krx_daily_KOSDAQ"), ctx.load("cb_issuers"),
                         ctx.cfg.sample.exclusions.ksic_prefixes)
    ctx.save("universe", uni)


def _universe(ctx: Context, market: str | None = None) -> pd.DataFrame:
    uni = ctx.load("universe")
    uni = uni[uni["in_universe"]]
    if market:
        uni = uni[uni["market"] == market]
    return ctx.limited(uni)


def stage_fs(ctx: Context) -> None:
    fy = ctx.fiscal_year

    def fetch(corp_code: str) -> dict:
        fs = ctx.dart.financial_statements(corp_code, fy, fs_div="CFS")
        fs_div = "CFS"
        if fs.empty:  # firms without subsidiaries file separate statements only
            fs, fs_div = ctx.dart.financial_statements(corp_code, fy, fs_div="OFS"), "OFS"
        return {"corp_code": corp_code, "fiscal_year": fy, **fs_status(fs, fs_div, ctx.t_post)}

    rows = _each(ctx, list(_universe(ctx)["corp_code"]), fetch, "fs")
    ctx.save("fs_status", pd.DataFrame(rows))


def stage_shares(ctx: Context) -> None:
    fy = ctx.fiscal_year

    def fetch(corp_code: str) -> dict:
        shares = ctx.dart.share_totals(corp_code, fy)
        divs = ctx.dart.dividends(corp_code, fy)
        invs = ctx.dart.investments(corp_code, fy)
        return {"corp_code": corp_code, "shares_rows": len(shares), "dividend_rows": len(divs),
                "investment_rows": len(invs)}

    rows = _each(ctx, list(_universe(ctx)["corp_code"]), fetch, "shares")
    ctx.save("shares_status", pd.DataFrame(rows))


def stage_cb(ctx: Context) -> None:
    kosdaq = _universe(ctx, "KOSDAQ")
    fs_df = ctx.load("fs_status")
    fs = (fs_df.set_index("corp_code") if "corp_code" in fs_df
          else pd.DataFrame(columns=["rcept_no"]))
    bgn, end = ctx.cb_window
    fy_end = date(ctx.fiscal_year, 12, 31)
    terms, refixes, tables, infos = [], [], [], []

    def fetch(corp_code: str) -> None:
        terms.append(collect_cb_terms(ctx.dart, corp_code, bgn, end))
        # The annual-report table reflects refixings up to the fiscal year end; collect the
        # adjustments between then and t_post.
        refixes.append(collect_refixings(ctx.dart, corp_code, fy_end + timedelta(days=1), end))
        rcept_no = fs["rcept_no"].get(corp_code) if corp_code in fs.index else None
        if rcept_no:
            table, info = unredeemed_cb_table(ctx.dart, corp_code, rcept_no)
            tables.append(table)
            infos.append(info)
        else:
            infos.append({"corp_code": corp_code, "found": False, "status": "no_report",
                          "n_tables": 0, "warnings": ["no annual report"]})

    _each(ctx, list(kosdaq["corp_code"]), fetch, "cb")

    def concat(frames: list[pd.DataFrame]) -> pd.DataFrame:
        frames = [f for f in frames if not f.empty]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    ctx.save("cb_terms", concat(terms))
    ctx.save("cb_refixings", concat(refixes))
    ctx.save("cb_outstanding", concat(tables))
    info_df = pd.DataFrame(infos, columns=["corp_code", "rcept_no", "found", "status",
                                           "n_tables", "unit", "warnings"])
    info_df["warnings"] = info_df["warnings"].map(
        lambda w: "; ".join(w) if isinstance(w, list) else (w or ""))
    ctx.save("cb_parse_info", info_df)


def stage_prices(ctx: Context) -> None:
    uni = _universe(ctx)
    primary = ctx.cfg.require_model("primary")
    targets = {"t_post": ctx.t_post, "cutoff": primary.training_cutoff}

    def fetch(row) -> list[dict]:
        out = []
        for label, on in targets.items():
            try:
                pp = ctx.prices.price_on(row.stock_code, row.market, on)
                out.append({"corp_code": row.corp_code, "ticker": row.stock_code,
                            "market": row.market, "which": label, "requested": on,
                            "date": pp.date, "close": pp.close, "source": pp.source})
            except PriceNotFound as exc:
                log.info("%s", exc)
        return out

    rows = _each(ctx, list(uni.itertuples(index=False)), fetch, "prices")
    ctx.save("prices_snapshot", pd.DataFrame([r for group in rows for r in group]))


STAGES: dict[str, Callable[[Context], None]] = {
    "corpcodes": stage_corpcodes,
    "listing": stage_listing,
    "cb_issuers": stage_cb_issuers,
    "company": stage_company,
    "universe": stage_universe,
    "fs": stage_fs,
    "shares": stage_shares,
    "cb": stage_cb,
    "prices": stage_prices,
}
