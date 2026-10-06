"""Hypothesis table and summary (P10 §5.5).

Verdict rule (preregistered): a primary hypothesis is "supported" when its Holm-adjusted
p < 0.05 in the predicted direction; "not supported" when the 95% CI excludes effects of
practical size; otherwise "inconclusive". Practical-size bounds: H1 and H3 — CI lower bound
above 0.9; H2a — CI upper bound below 0.02 (beta units); H2b — CI upper bound below 0.
Exploratory results get "consistent" / "not consistent" (p < 0.05) labels only.
"""

from __future__ import annotations

import math

import pandas as pd

from src.analysis.common import Result, holm

PRIMARY = ("H1", "H2a", "H2b", "H3")
NOT_SUPPORTED = {"H1": lambda lo, hi: lo > 0.9, "H3": lambda lo, hi: lo > 0.9,
                 "H2a": lambda lo, hi: hi < 0.02, "H2b": lambda lo, hi: hi < 0}


def apply_holm(results: list[Result]) -> None:
    prim = [r for r in results if r.id in PRIMARY]
    for r, p in zip(prim, holm([r.p for r in prim]), strict=True):
        r.p_holm = p


def verdict(r: Result) -> str:
    if r.id in PRIMARY:
        if not math.isnan(r.p_holm) and r.p_holm < 0.05:
            return "supported"
        lo, hi = r.ci
        if not (math.isnan(lo) or math.isnan(hi)) and NOT_SUPPORTED[r.id](lo, hi):
            return "not supported"
        return "inconclusive"
    if r.kind == "exploratory" and not math.isnan(r.p):
        return "consistent (exploratory)" if r.p < 0.05 else "not consistent (exploratory)"
    return "—"


def _f(x, nd=3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def hypothesis_table(results: list[Result], refs: dict[str, str]) -> str:
    rows = ["| H | type | statistic | estimate | 95% CI | p | p (Holm) | n | verdict | ref |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        if r.kind == "robustness":
            continue
        rows.append(f"| {r.id} | {r.kind} | {r.statistic} | {_f(r.estimate)} | "
                    f"[{_f(r.ci[0])}, {_f(r.ci[1])}] | {_f(r.p, 4)} | {_f(r.p_holm, 4)} | "
                    f"{r.n} | {verdict(r)} | {refs.get(r.id.split('-')[0], '')} |")
    return "\n".join(rows)


def robustness_table(results: list[Result]) -> str:
    rows = ["| check | statistic | estimate | 95% CI | p | n | note |",
            "|---|---|---|---|---|---|---|"]
    for r in results:
        if r.kind != "robustness":
            continue
        rows.append(f"| {r.id} | {r.statistic} | {_f(r.estimate)} | [{_f(r.ci[0])}, "
                    f"{_f(r.ci[1])}] | {_f(r.p, 4)} | {r.n} | {r.note} |")
    return "\n".join(rows)


def md(df: pd.DataFrame, max_rows: int = 60) -> str:
    if df is None or df.empty:
        return "(none)"
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "---|" * len(df.columns)
    body = ["| " + " | ".join(_f(v) if isinstance(v, float) else str(v) for v in r) + " |"
            for r in df.head(max_rows).itertuples(index=False)]
    return "\n".join([head, sep, *body])
