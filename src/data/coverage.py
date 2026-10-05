"""Coverage report for the P1 fetch (docs/data_coverage_report.md)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


def _load(out_dir: Path, name: str) -> pd.DataFrame | None:
    path = out_dir / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else None


def _pct(n: int, d: int) -> str:
    return f"{n} / {d} ({100 * n / d:.1f}%)" if d else f"{n} / 0"


def build_report(out_dir: Path, t_post, fiscal_year: int, notes: list[str]) -> str:
    lines = [
        "# Data Coverage Report (P1)",
        "",
        f"- Generated: {datetime.now():%Y-%m-%d %H:%M}",
        f"- Evaluation date `T_post`: {t_post}; fiscal year: FY{fiscal_year}",
        "- Source tables: `data/processed/p1/*.parquet` (not committed)",
        "",
    ]
    uni = _load(out_dir, "universe")
    if uni is not None:
        u = uni[uni["in_universe"]]
        lines += ["## Universe", "",
                  "| Market | Listed | Financial (excluded) | CB issuers | In universe |",
                  "|---|---|---|---|---|"]
        for market in ("KOSPI", "KOSDAQ"):
            m = uni[uni["market"] == market]
            lines.append(f"| {market} | {len(m)} | {int(m['excl_financial'].sum())} | "
                         f"{int(m['cb_issuer'].sum())} | {int((m['in_universe']).sum())} |")
        halted = u["halted"].dropna()
        lines += ["", f"- Halted on `T_post` (KRX-covered firms only): {int(halted.sum())} "
                  f"of {len(halted)}", ""]

    fs = _load(out_dir, "fs_status")
    if fs is not None:
        n = len(fs)
        lines += ["## Annual statements", "",
                  f"- Statements found: {_pct(int(fs['fs_div'].notna().sum()), n)}",
                  f"- Consolidated (CFS): {int((fs['fs_div'] == 'CFS').sum())}; "
                  f"separate only (OFS): {int((fs['fs_div'] == 'OFS').sum())}",
                  f"- Three years in one report: {_pct(int(fs['has_3y'].sum()), n)}",
                  f"- Filed by `T_post` (latest receipt date): "
                  f"{_pct(int(fs['filed_by_t_post'].sum()), n)}",
                  "  - Later receipt dates include corrected reports re-filed after `T_post`; "
                  "P2 decides which filings count as available at `T_post`.", ""]

    shares = _load(out_dir, "shares_status")
    if shares is not None:
        n = len(shares)
        lines += ["## Shares, dividends, investments", "",
                  f"- Share totals: {_pct(int((shares['shares_rows'] > 0).sum()), n)}",
                  f"- Dividends: {_pct(int((shares['dividend_rows'] > 0).sum()), n)}",
                  f"- Investments in other companies: "
                  f"{_pct(int((shares['investment_rows'] > 0).sum()), n)}", ""]

    info = _load(out_dir, "cb_parse_info")
    if info is not None:
        outstanding = _load(out_dir, "cb_outstanding")
        terms = _load(out_dir, "cb_terms")
        refix = _load(out_dir, "cb_refixings")
        n = len(info)
        firms_with_cb = (outstanding["corp_code"].nunique()
                         if outstanding is not None and not outstanding.empty else 0)
        lines += ["## Convertible bonds (KOSDAQ CB issuers)", "",
                  f"- Firms processed: {n}",
                  f"- Unredeemed-CB table found in the annual report: "
                  f"{_pct(int(info['found'].sum()), n)}",
                  "- Status: " + ", ".join(f"{k} {v}" for k, v in
                                           info["status"].value_counts().items()),
                  f"- Firms with ≥ 1 outstanding CB series at FY end: {firms_with_cb}",
                  f"- CB issuance terms (series): "
                  f"{0 if terms is None else len(terms)}",
                  f"- Conversion-price adjustments between FY end and `T_post`: "
                  f"{0 if refix is None else len(refix)}",
                  f"- Parse warnings: {int((info['warnings'] != '').sum())}", ""]

    prices = _load(out_dir, "prices_snapshot")
    if prices is not None and not prices.empty:
        lines += ["## Prices", "", "| Date | Source | Firms |", "|---|---|---|"]
        for (which, source), g in prices.groupby(["which", "source"]):
            lines.append(f"| {which} | {source} | {len(g)} |")
        lines.append("")

    if notes:
        lines += ["## Notes", ""] + [f"- {n}" for n in notes] + [""]
    return "\n".join(lines)
