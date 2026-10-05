"""Scale elasticity beta (E2; D6.5).

Per firm x condition (x agent x model): OLS of log V on log k over all valid runs with
V > 0, HC3 standard errors. The quadratic fit adds (log k)^2 to detect curvature. A
median-based estimate (log cell medians on log k) is reported as robustness.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.metrics.cells import AGENT_KEYS, k_of

GROUP = ["firm_id", "condition", *AGENT_KEYS]


def ols_hc3(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(coefficients, HC3 standard errors); x already contains the intercept column."""
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    resid = y - x @ beta
    h = np.einsum("ij,jk,ik->i", x, xtx_inv, x)
    w = (resid / np.clip(1 - h, 1e-12, None)) ** 2
    cov = xtx_inv @ (x.T * w) @ x @ xtx_inv
    return beta, np.sqrt(np.clip(np.diag(cov), 0, None))


def beta_from(logk: np.ndarray, logv: np.ndarray) -> float:
    """Slope only (fast path for bootstrap replicates)."""
    xm = logk - logk.mean()
    denom = (xm * xm).sum()
    return float((xm * (logv - logv.mean())).sum() / denom) if denom > 0 else np.nan


def _fit(g: pd.DataFrame) -> pd.Series:
    ok = g[g["valid"].eq(True) & g["value_per_share"].notna()]
    pos = ok[ok["value_per_share"] > 0]
    out = {"beta": np.nan, "se_hc3": np.nan, "alpha": np.nan, "n_used": len(pos),
           "n_nonpositive_dropped": int(len(ok) - len(pos)), "beta_quad": np.nan,
           "p_quad": np.nan, "beta_median_based": np.nan, "n_k": 0}
    if pos.empty:
        return pd.Series(out)
    logk = np.log(pos["k"].to_numpy(float))
    logv = np.log(pos["value_per_share"].to_numpy(float))
    out["n_k"] = int(len(np.unique(logk)))
    if out["n_k"] < 2:
        return pd.Series(out)
    x = np.column_stack([np.ones_like(logk), logk])
    b, se = ols_hc3(x, logv)
    out.update(alpha=float(b[0]), beta=float(b[1]), se_hc3=float(se[1]))
    if out["n_k"] >= 3:
        xq = np.column_stack([x, logk ** 2])
        bq, seq = ols_hc3(xq, logv)
        out["beta_quad"] = float(bq[2])
        out["p_quad"] = float(2 * stats.norm.sf(abs(bq[2] / seq[2]))) if seq[2] > 0 else np.nan
    med = pos.groupby("k")["value_per_share"].median()
    out["beta_median_based"] = beta_from(np.log(med.index.to_numpy(float)),
                                         np.log(med.to_numpy(float)))
    return pd.Series(out)


def scale_runs(runs: pd.DataFrame) -> pd.DataFrame:
    r = runs[runs["perturbation_type"].isin(["none", "scale"])].copy()
    r["k"] = k_of(r)
    return r


def firm_elasticity(runs: pd.DataFrame) -> pd.DataFrame:
    r = scale_runs(runs)
    if r.empty:
        return pd.DataFrame(columns=[*GROUP, "beta", "se_hc3"])
    return r.groupby(GROUP, sort=True).apply(_fit, include_groups=False).reset_index()
