"""docs/sample_report.md: exclusions, group descriptives, mid-group contrast, CB summary."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.data.sample import EXCLUSION_COLUMNS


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |")
    return "\n".join(lines)


def build_sample_report(ctx) -> str:
    elig = ctx.load("eligibility")
    sample = ctx.load("sample")
    builds = ctx.load("build_status")
    small = ctx.load("small_candidates")
    out = ["# Sample Report (P2)", "",
           f"- Generated: {datetime.now():%Y-%m-%d %H:%M}",
           f"- `T_post`: {ctx.t_post}; universe firms: {len(elig)}", ""]

    out += ["## Package builds", "", _md_table(
        builds["status"].value_counts().rename_axis("status").reset_index(name="firms")), ""]

    rows = []
    for market in ("KOSPI", "KOSDAQ"):
        m = elig[elig["market"] == market]
        rows.append({"market": market, "universe": len(m),
                     **{c.replace("excl_", ""): int(m[c].fillna(False).astype(bool).sum())
                        for c in EXCLUSION_COLUMNS},
                     "eligible": int(m["eligible"].sum())})
    out += ["## Exclusions (a firm can have several)", "", _md_table(pd.DataFrame(rows)), "",
            "- `financial`: KSIC 64–66 (already outside the universe, shown as 0 here). "
            "`halted`: zero volume on `T_post` (KOSPI only until KRX KOSDAQ data is available). "
            "Administrative-issue status is not yet applied (D0.6, pending).", ""]

    desc = []
    for g in ("L", "M", "S"):
        s = sample[sample["group"] == g]
        cap = s["market_cap"].dropna() / 1e12
        desc.append({"group": g, "firms": len(s),
                     "market cap median (tn KRW)": round(cap.median(), 2) if len(cap) else "",
                     "KSIC divisions": s["ksic2"].nunique()})
    out += ["## Sample", "", _md_table(pd.DataFrame(desc)), ""]

    mid = sample[sample["group"] == "M"]
    if not mid.empty:
        contrast = (mid.assign(cap_quintile=pd.qcut(mid["cap_rank"], 5, labels=False))
                    .groupby(["cap_quintile", "news_group"])["newsworthiness"]
                    .agg(["count", "median"]).reset_index())
        out += ["## Mid group: newsworthiness contrast within market-cap quintiles", "",
                _md_table(contrast), ""]

    s = sample[sample["group"] == "S"]
    cand = small[small["eligible"]]
    out += ["## Small group (CB)", "",
            f"- Eligible KOSDAQ CB issuers: {len(cand)}; with outstanding CB at `T_post`: "
            f"{int((cand['n_series'] > 0).sum())}; in the money at market price: "
            f"{int(cand['itm'].sum())}",
            f"- Selected: {len(s)}; dilution (ITM convertible shares / common shares) median "
            f"{s['dilution'].median():.1%}, range {s['dilution'].min():.1%}–"
            f"{s['dilution'].max():.1%}" if len(s) else "- Selected: 0",
            f"- Price source for the ITM test: {small['price_source'].value_counts().to_dict()}",
            "- **Provisional**: KOSDAQ prices come from yfinance until the KRX KOSDAQ service is "
            "approved; yfinance closes are adjusted for later capital changes. Re-run "
            "`small`, `select`, `packages`, `truth` after approval.", ""]
    return "\n".join(out)
