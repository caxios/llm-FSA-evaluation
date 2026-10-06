"""H4 (P10 §5.2): structures P, R and T on the 30 extension firms (T from the main run).

Paired by firm: |1 - beta_C|, |1 - R_dil(V0)| and epsilon, Wilcoxon signed-rank; E9 stage
proportions by structure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.analysis.common import Result
from src.metrics.failure_modes import STAGES


def _paired(a: pd.Series, b: pd.Series) -> tuple[float, float, int]:
    d = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    if len(d) < 3 or (d["a"] - d["b"]).abs().sum() == 0:
        return (float((d["a"] - d["b"]).median()) if len(d) else np.nan), np.nan, len(d)
    p = stats.wilcoxon(d["a"], d["b"], alternative="greater").pvalue
    return float((d["a"] - d["b"]).median()), float(p), len(d)


def h4(tables: dict[str, pd.DataFrame], firms: list[str], e8_firms: list[str]
       ) -> tuple[list[Result], pd.DataFrame]:
    """`tables`: firm tables keyed by structure ("T", "P", "R"). Tests that P and R deviate
    more from 1 than T (median paired difference > 0)."""
    def col(s: str, c: str, subset: list[str]) -> pd.Series:
        t = tables.get(s)
        if t is None or c not in t:
            return pd.Series(dtype=float)
        return t.set_index("firm_id").reindex(subset)[c].astype(float)

    out, rows = [], []
    for other in ("P", "R"):
        if other not in tables:
            continue
        dev_t = (1 - col("T", "beta_C", firms)).abs()
        dev_o = (1 - col(other, "beta_C", firms)).abs()
        m, p, n = _paired(dev_o, dev_t)
        out.append(Result(f"H4-beta-{other}", "exploratory",
                          f"median paired |1-beta_C|: {other} - T", m, p=p, n=n, direction="> 0"))
        dev_t = (1 - col("T", "R_dil_V0", e8_firms)).abs()
        dev_o = (1 - col(other, "R_dil_V0", e8_firms)).abs()
        m, p, n = _paired(dev_o, dev_t)
        out.append(Result(f"H4-Rdil-{other}", "exploratory",
                          f"median paired |1-R_dil|: {other} - T", m, p=p, n=n, direction="> 0"))
        e_o = col(other, "eps_median", firms)
        out.append(Result(f"H4-eps-{other}", "exploratory", f"median epsilon ({other}; T = 0)",
                          float(e_o.median()) if e_o.notna().any() else np.nan,
                          n=int(e_o.notna().sum())))
    for s, t in tables.items():
        if t is None or t.empty:
            continue
        sub = t[t["firm_id"].isin(e8_firms)]
        row = {"structure": s, "n_firms": int(sub[list(STAGES)].notna().all(axis=1).sum())
               if set(STAGES) <= set(sub.columns) else 0}
        for st in STAGES:
            row[st] = float(sub[st].mean()) if st in sub else np.nan
        row["median_beta_C"] = float(t[t["firm_id"].isin(firms)]["beta_C"].median()) \
            if "beta_C" in t else np.nan
        rows.append(row)
    return out, pd.DataFrame(rows)
