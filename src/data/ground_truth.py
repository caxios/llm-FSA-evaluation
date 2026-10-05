"""Ground-truth tables (P2 Step 2.6): CB truth, memory-quiz truth, stale-anchor prices."""

from __future__ import annotations

import math
from datetime import date

import pandas as pd

from src.data.package_schema import InputPackage

E7_THRESHOLD = 0.30


def cb_truth_rows(firm_id: str, pkg: InputPackage, price_t_post: float | None,
                  price_source: str | None) -> list[dict]:
    if pkg.cb is None:
        return []
    rows = []
    for ins in pkg.cb.instruments:
        rows.append({
            "firm_id": firm_id, "corp_code": pkg.meta.corp_code, "series": ins.series,
            "face_outstanding_mn": ins.face_outstanding, "conversion_price": ins.conversion_price,
            "convertible_shares": ins.convertible_shares, "refix_floor": ins.refix_floor,
            "maturity": ins.maturity, "as_of": pkg.meta.eval_date,
            "source_rcept_no": pkg.meta.source_rcept_no, "price_t_post": price_t_post,
            "price_source": price_source,
            "itm_at_market": (price_t_post is not None and ins.conversion_price < price_t_post),
        })
    return rows


def quiz_truth_row(firm_id: str, pkg: InputPackage, price: float | None,
                   market_cap: float | None, price_source: str | None) -> dict:
    y = pkg.latest_year
    rev = pkg.is_.find("revenue") or pkg.is_.find("operating_expense")
    op = pkg.is_.find("operating_income")
    if market_cap is None or (isinstance(market_cap, float) and math.isnan(market_cap)):
        shares = pkg.shares.common_issued + pkg.shares.preferred_issued
        market_cap = price * shares if price else None
        cap_source = f"{price_source} price x issued shares" if price else None
    else:
        cap_source = "krx"
    return {
        "firm_id": firm_id, "corp_code": pkg.meta.corp_code, "eval_date": pkg.meta.eval_date,
        "market": pkg.meta.market, "price": price, "price_source": price_source,
        "market_cap_krw": market_cap, "market_cap_source": cap_source,
        "revenue_prev_mn": rev.values.get(y) if rev else None,
        "op_income_prev_mn": op.values.get(y) if op else None,
        "fiscal_year_prev": y,
        "main_business": None,  # to be filled by hand before E6 (P8)
    }


def anchor_row(firm_id: str, corp_code: str, p_old: float | None, p_new: float | None,
               cutoff: date, source_old: str | None, source_new: str | None) -> dict:
    log_diff = (math.log(p_new / p_old) if p_old and p_new and p_old > 0 and p_new > 0
                else None)
    return {
        "firm_id": firm_id, "corp_code": corp_code, "cutoff": cutoff, "p_old": p_old,
        "p_new": p_new, "log_diff": log_diff,
        "e7_candidate": log_diff is not None and abs(log_diff) >= E7_THRESHOLD,
        "source_old": source_old, "source_new": source_new,
    }


def to_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)
