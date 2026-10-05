"""P2 pipeline: build packages, select the sample, write packages and ground truth.

Stages (each writes data/processed/p2/<name>.parquet and can be re-run):
  builds        build every universe firm's package; record status and key values
  availability  for firms whose latest filing postdates T_post, check that the original
                annual report was filed by T_post (DART list.json, report type A)
  newsworthiness  DART filing counts over the 12 months before T_post for the mid band
  small         KOSDAQ CB state at T_post, in-the-money test, dilution potential
  select        apply exclusions and select L / M / S, assign firm IDs
  packages      write data/processed/packages/{firm_id}.json for the sample
  truth         data/ground_truth/{cb_truth,quiz_truth,anchor_prices}.parquet
  report        docs/sample_report.md
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.config import PROJECT_ROOT, Config
from src.data.cb_truth import build_cb_block, current_instruments
from src.data.dart_client import DartClient
from src.data.ground_truth import anchor_row, cb_truth_rows, quiz_truth_row
from src.data.p2_inputs import P1_DIR, P1Data, iter_builds
from src.data.sample import (
    apply_exclusions,
    assign_firm_ids,
    mid_band,
    select_large,
    select_mid,
    select_small,
)

log = logging.getLogger(__name__)

P2_DIR = PROJECT_ROOT / "data" / "processed" / "p2"
PACKAGES_DIR = PROJECT_ROOT / "data" / "processed" / "packages"
TRUTH_DIR = PROJECT_ROOT / "data" / "ground_truth"
REPORT = PROJECT_ROOT / "docs" / "sample_report.md"


@dataclass
class P2Context:
    cfg: Config
    dart: DartClient
    data: P1Data
    out_dir: Path = P2_DIR
    packages_dir: Path = PACKAGES_DIR
    truth_dir: Path = TRUTH_DIR

    @property
    def t_post(self) -> date:
        return self.cfg.require_dates()[0]

    def save(self, name: str, df: pd.DataFrame) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(self.out_dir / f"{name}.parquet", index=False)
        log.info("wrote %s (%d rows)", name, len(df))

    def load(self, name: str) -> pd.DataFrame:
        return pd.read_parquet(self.out_dir / f"{name}.parquet")

    def p1(self, name: str) -> pd.DataFrame:
        return pd.read_parquet(P1_DIR / f"{name}.parquet")


# ------------------------------------------------------------------------------ stages


def stage_builds(ctx: P2Context) -> None:
    rows = []
    for r in iter_builds(ctx.dart, ctx.cfg, ctx.data):
        row = {"corp_code": r.corp_code, "status": r.status, "issues": "; ".join(r.issues)}
        if r.package is not None:
            p, y = r.package, r.package.latest_year
            eq, cap = p.bs.find("total_equity"), p.bs.find("issued_capital")
            row.update(
                total_equity=eq.values.get(y) if eq else None,
                issued_capital=cap.values.get(y) if cap else None,
                common_outstanding=p.shares.common_outstanding,
                flags=", ".join(p.meta.flags),
                source_rcept_no=p.meta.source_rcept_no,
            )
        rows.append(row)
    ctx.save("build_status", pd.DataFrame(rows))


def stage_availability(ctx: P2Context) -> None:
    """Annual report available at T_post? The latest receipt number can postdate T_post when
    a corrected report was filed later; the original filing date decides availability.
    Using the corrected figures is a small look-ahead, recorded as a limitation."""
    fs = ctx.data.fs_status
    late = fs[fs["fs_div"].notna() & ~fs["filed_by_t_post"].astype(bool)]
    fy = int(fs["fiscal_year"].dropna().iloc[0])
    rows = []
    for row in late.itertuples(index=False):
        filings = ctx.dart.search_filings(date(fy + 1, 1, 1), ctx.t_post,
                                          corp_code=row.corp_code, pblntf_ty="A")
        first = None
        if not filings.empty:
            annual = filings[filings["report_nm"].str.contains("사업보고서")
                             & filings["report_nm"].str.contains(f"{fy}.12")]
            if not annual.empty:
                first = annual["rcept_dt"].min()
        rows.append({"corp_code": row.corp_code, "original_rcept_dt": first,
                     "available_at_t_post": first is not None})
    ctx.save("availability", pd.DataFrame(rows, columns=["corp_code", "original_rcept_dt",
                                                         "available_at_t_post"]))


def _eligibility(ctx: P2Context) -> pd.DataFrame:
    uni = ctx.data.universe[ctx.data.universe["in_universe"]].copy()
    builds = ctx.load("build_status")
    fs = ctx.data.fs_status[["corp_code", "has_3y", "filed_by_t_post"]]
    avail = ctx.load("availability")
    df = uni.merge(builds, on="corp_code", how="left").merge(fs, on="corp_code", how="left")
    df = df.merge(avail[["corp_code", "available_at_t_post"]], on="corp_code", how="left")
    df["excl_halted"] = df["halted"].fillna(False).astype(bool)
    df["excl_build"] = df["status"] != "ok"
    df["excl_no_3y"] = ~df["has_3y"].fillna(False).astype(bool)
    equity, capital = df["total_equity"], df["issued_capital"]
    df["excl_impairment"] = (equity <= 0) | (capital.notna() & (equity < capital))
    filed = df["filed_by_t_post"].fillna(False).astype(bool) | df["available_at_t_post"].fillna(
        False).astype(bool)
    df["excl_not_filed"] = ~filed
    return apply_exclusions(df)


def stage_newsworthiness(ctx: P2Context) -> None:
    band = mid_band(_eligibility(ctx), tuple(ctx.cfg.sample.mid_rank_band))
    start = ctx.t_post - timedelta(days=365)
    rows = []
    for cc in band["corp_code"]:
        filings = ctx.dart.search_filings(start, ctx.t_post - timedelta(days=1), corp_code=cc)
        rows.append({"corp_code": cc, "newsworthiness": len(filings)})
    ctx.save("newsworthiness", pd.DataFrame(rows))


def _prices(ctx: P2Context, which: str) -> pd.DataFrame:
    p = ctx.p1("prices_snapshot")
    return p[p["which"] == which].set_index("corp_code")


def stage_small(ctx: P2Context) -> None:
    elig = _eligibility(ctx)
    kosdaq = elig[elig["market"] == "KOSDAQ"]
    outstanding, refix, terms = (ctx.p1("cb_outstanding"), ctx.p1("cb_refixings"),
                                 ctx.p1("cb_terms"))
    prices = _prices(ctx, "t_post")
    rows = []
    for row in kosdaq.itertuples(index=False):
        cc = row.corp_code
        ins = current_instruments(
            outstanding[outstanding["corp_code"] == cc] if not outstanding.empty else outstanding,
            refix[refix["corp_code"] == cc] if not refix.empty else refix,
            terms[terms["corp_code"] == cc] if not terms.empty else terms,
            ctx.t_post)
        price = float(prices.loc[cc, "close"]) if cc in prices.index else None
        source = prices.loc[cc, "source"] if cc in prices.index else None
        itm_shares = sum(i.convertible_shares for i in ins
                         if price is not None and i.conversion_price < price)
        common = row.common_outstanding if pd.notna(row.common_outstanding) else None
        rows.append({
            "corp_code": cc, "n_series": len(ins), "price_t_post": price, "price_source": source,
            "itm": itm_shares > 0, "itm_convertible_shares": itm_shares,
            "dilution": itm_shares / common if common else 0.0,
            "cb_complex": None, "eligible": bool(row.eligible),
        })
    ctx.save("small_candidates", pd.DataFrame(rows))


def stage_select(ctx: P2Context) -> None:
    elig = _eligibility(ctx)
    news = ctx.load("newsworthiness").set_index("corp_code")["newsworthiness"]
    small = ctx.load("small_candidates")
    sizes = {g: spec.size for g, spec in ctx.cfg.sample.groups.items()}
    large = select_large(elig, sizes["L"])
    mid = select_mid(mid_band(elig, tuple(ctx.cfg.sample.mid_rank_band)), news, sizes["M"],
                     seed=ctx.cfg.sample.seed)
    s = select_small(small, sizes["S"]).merge(
        elig.drop(columns=["eligible"]), on="corp_code", how="left")
    selected = assign_firm_ids(pd.concat([large, mid, s], ignore_index=True))
    keep = ["firm_id", "group", "corp_code", "stock_code", "corp_name", "market", "market_cap",
            "induty_code", "ksic2", "cap_rank", "newsworthiness", "news_group", "dilution",
            "price_t_post", "price_source", "cb_complex", "selection_reason"]
    selected["newsworthiness"] = selected["corp_code"].map(news)
    ctx.save("eligibility", elig)
    ctx.save("sample", selected.reindex(columns=keep))
    (ctx.out_dir.parent / "sample.parquet").write_bytes(
        (ctx.out_dir / "sample.parquet").read_bytes())


def stage_packages(ctx: P2Context) -> None:
    sample = ctx.load("sample")
    outstanding, refix, terms = (ctx.p1("cb_outstanding"), ctx.p1("cb_refixings"),
                                 ctx.p1("cb_terms"))
    ctx.packages_dir.mkdir(parents=True, exist_ok=True)
    by_corp = sample.set_index("corp_code")
    written = 0
    for r in iter_builds(ctx.dart, ctx.cfg, ctx.data, list(sample["corp_code"])):
        meta = by_corp.loc[r.corp_code]
        if r.package is None or r.status != "ok":
            raise RuntimeError(f"selected firm {r.corp_code} failed to build: {r.status}")
        pkg = r.package
        pkg.meta.firm_id, pkg.meta.group = meta["firm_id"], meta["group"]
        if meta["group"] == "S":
            cc = r.corp_code
            ins = current_instruments(outstanding[outstanding["corp_code"] == cc],
                                      refix[refix["corp_code"] == cc] if not refix.empty
                                      else refix,
                                      terms[terms["corp_code"] == cc], ctx.t_post)
            pkg.cb = build_cb_block(ins, ctx.t_post)
        (ctx.packages_dir / f"{meta['firm_id']}.json").write_text(pkg.to_json(),
                                                                  encoding="utf-8")
        written += 1
    log.info("wrote %d packages to %s", written, ctx.packages_dir)


def _load_package(ctx: P2Context, firm_id: str):
    from src.data.package_schema import InputPackage

    return InputPackage.from_json((ctx.packages_dir / f"{firm_id}.json").read_text(
        encoding="utf-8"))


def stage_truth(ctx: P2Context) -> None:
    sample = ctx.load("sample")
    p_new, p_old = _prices(ctx, "t_post"), _prices(ctx, "cutoff")
    cutoff = ctx.cfg.require_model("primary").training_cutoff
    cb_rows, quiz_rows, anchor_rows = [], [], []
    for row in sample.itertuples(index=False):
        pkg = _load_package(ctx, row.firm_id)
        cc = row.corp_code
        new = float(p_new.loc[cc, "close"]) if cc in p_new.index else None
        old = float(p_old.loc[cc, "close"]) if cc in p_old.index else None
        src_new = p_new.loc[cc, "source"] if cc in p_new.index else None
        src_old = p_old.loc[cc, "source"] if cc in p_old.index else None
        cb_rows += cb_truth_rows(row.firm_id, pkg, new, src_new)
        quiz_rows.append(quiz_truth_row(row.firm_id, pkg, new, row.market_cap, src_new))
        anchor_rows.append(anchor_row(row.firm_id, cc, old, new, cutoff, src_old, src_new))
    ctx.truth_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("cb_truth", cb_rows), ("quiz_truth", quiz_rows),
                       ("anchor_prices", anchor_rows)):
        pd.DataFrame(rows).to_parquet(ctx.truth_dir / f"{name}.parquet", index=False)
        log.info("wrote ground truth %s (%d rows)", name, len(rows))


def stage_report(ctx: P2Context) -> None:
    from src.data.sample_report import build_sample_report

    REPORT.write_text(build_sample_report(ctx), encoding="utf-8")
    log.info("wrote %s", REPORT)


STAGES: dict[str, Callable[[P2Context], None]] = {
    "builds": stage_builds,
    "availability": stage_availability,
    "newsworthiness": stage_newsworthiness,
    "small": stage_small,
    "select": stage_select,
    "packages": stage_packages,
    "truth": stage_truth,
    "report": stage_report,
}
