"""Candidate-universe construction (pure functions; I/O lives in pipeline.py)."""

from __future__ import annotations

import pandas as pd

MARKET_BY_CLS = {"Y": "KOSPI", "K": "KOSDAQ"}


def ksic_division(induty_code: str | None) -> str | None:
    if not induty_code or not str(induty_code).strip():
        return None
    return str(induty_code).strip()[:2]


def build_universe(
    companies: pd.DataFrame,
    kospi_daily: pd.DataFrame | None,
    kosdaq_daily: pd.DataFrame | None,
    cb_issuers: pd.DataFrame,
    financial_prefixes: list[str],
) -> pd.DataFrame:
    """One row per listed KOSPI/KOSDAQ company with inclusion flags.

    companies: corp_code, corp_name, stock_code, corp_cls, induty_code (from company.json)
    *_daily: KRX daily data on the evaluation date (None if the service is unavailable)
    cb_issuers: corp_code, n_filings (from find_cb_issuers)
    In the universe: non-financial KOSPI firms, and non-financial KOSDAQ firms with at least
    one CB issuance decision in the search window (implementation plan P1, D1.3).
    """
    df = companies[companies["corp_cls"].isin(MARKET_BY_CLS)].copy()
    df["market"] = df["corp_cls"].map(MARKET_BY_CLS)
    df["ksic2"] = df["induty_code"].map(ksic_division)
    df["excl_financial"] = df["ksic2"].isin(financial_prefixes)

    daily_frames = [d for d in (kospi_daily, kosdaq_daily) if d is not None and not d.empty]
    if daily_frames:
        daily = pd.concat(daily_frames)[["ticker", "close", "volume", "market_cap",
                                         "shares_listed"]]
        df = df.merge(daily, how="left", left_on="stock_code", right_on="ticker")
        df = df.drop(columns="ticker")
    else:
        for col in ("close", "volume", "market_cap", "shares_listed"):
            df[col] = float("nan")
    covered = {m for m, d in (("KOSPI", kospi_daily), ("KOSDAQ", kosdaq_daily))
               if d is not None and not d.empty}
    df["krx_covered"] = df["market"].isin(covered)
    # D0.6: not trading on the evaluation date = halted (only knowable where KRX data exists)
    df["halted"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
    df.loc[df["krx_covered"], "halted"] = ~(df.loc[df["krx_covered"], "volume"].fillna(0) > 0)

    issuers = cb_issuers[["corp_code", "n_filings"]].rename(columns={"n_filings": "n_cb_filings"})
    df = df.merge(issuers, how="left", on="corp_code")
    df["n_cb_filings"] = df["n_cb_filings"].fillna(0).astype(int)
    df["cb_issuer"] = df["n_cb_filings"] > 0

    df["in_universe"] = ~df["excl_financial"] & (
        (df["market"] == "KOSPI") | ((df["market"] == "KOSDAQ") & df["cb_issuer"])
    )
    cols = ["corp_code", "corp_name", "stock_code", "market", "induty_code", "ksic2",
            "excl_financial", "krx_covered", "halted", "close", "volume", "market_cap",
            "shares_listed", "cb_issuer", "n_cb_filings", "in_universe"]
    return df[cols].sort_values(["market", "corp_code"]).reset_index(drop=True)


def fs_status(fs: pd.DataFrame, fs_div: str, t_post) -> dict:
    """Summarize one firm's annual statements: availability, filing date, 3-year coverage."""
    from src.data.parsing import rcept_date

    if fs.empty:
        return {"fs_div": None, "rcept_no": None, "rcept_dt": None, "filed_by_t_post": False,
                "has_3y": False, "n_rows": 0}
    rcept_no = str(fs["rcept_no"].iloc[0])
    bs = fs[fs["sj_div"] == "BS"]
    # Recently listed firms may lack the prior-year columns entirely.
    has_3y = bool(len(bs)) and all(c in bs and bs[c].notna().any() for c in
                                   ("thstrm_amount", "frmtrm_amount", "bfefrmtrm_amount"))
    filed = rcept_date(rcept_no)
    return {"fs_div": fs_div, "rcept_no": rcept_no, "rcept_dt": filed,
            "filed_by_t_post": filed <= t_post, "has_3y": has_3y, "n_rows": len(fs)}
