"""Pooled response ratios across firms (exploratory, added after the main results; not in
the preregistration).

Per-firm R is too imprecise to judge firm by firm (run-to-run noise is large relative to
the perturbations), but the average response across firms can still be estimated. Each
firm-cell R has a bootstrap 95% CI; its SE is the CI width / 3.92. Cells are pooled with
the DerSimonian–Laird random-effects mean:

- by perturbation type and size (rule size, 2/5/10% tiers): one cell per firm, so firms are
  independent;
- by type overall: a firm's cells are first combined by inverse variance (fixed effect),
  then firms are pooled;
- CB dilution: R_dil for V0, V2, V3 among firms whose CB is in the money for the agent.

Firms whose E0 median value is not positive are excluded (D7.5). Reported for each pool:
mean, 95% CI, tests against 1 (full reflection) and 0 (no reflection), tau², I², and the
unweighted median.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from src.analysis.common import Result
from src.metrics.baseline import baseline
from src.metrics.cells import params
from src.metrics.response import firm_responses
from src.perturb.base import book_equity

TYPES = ("cash", "non_operating", "shares")
LABEL = {"cash": "현금 배당", "non_operating": "비영업자산", "shares": "주식 수 2배",
         "V0": "CB 희석 V0", "V2": "CB 희석 V2(액면 증가)", "V3": "CB 희석 V3(전환가 인하)"}


def dl_pool(r: np.ndarray, se: np.ndarray) -> dict:
    ok = np.isfinite(r) & np.isfinite(se) & (se > 0)
    y, v = r[ok], se[ok] ** 2
    k = len(y)
    out = {"k": k, "mean": np.nan, "se": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
           "p_vs_1": np.nan, "p_vs_0": np.nan, "tau2": np.nan, "I2": np.nan,
           "median_unweighted": float(np.median(r[np.isfinite(r)])) if np.isfinite(r).any()
           else np.nan}
    if k < 2:
        return out
    w = 1 / v
    mu_fe = np.sum(w * y) / np.sum(w)
    q = float(np.sum(w * (y - mu_fe) ** 2))
    c = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    tau2 = max(0.0, (q - (k - 1)) / c) if c > 0 else 0.0
    wr = 1 / (v + tau2)
    mu = float(np.sum(wr * y) / np.sum(wr))
    s = float(math.sqrt(1 / np.sum(wr)))
    out.update(mean=mu, se=s, ci_lo=mu - 1.96 * s, ci_hi=mu + 1.96 * s,
               p_vs_1=float(2 * stats.norm.sf(abs(mu - 1) / s)),
               p_vs_0=float(2 * stats.norm.sf(abs(mu) / s)), tau2=tau2,
               I2=max(0.0, (q - (k - 1)) / q) if q > 0 else 0.0)
    return out


def cell_responses(runs: pd.DataFrame, store, n_boot: int = 500) -> pd.DataFrame:
    """Firm-cell R with SE, size class and group; D7.5 applied."""
    val = runs[runs["schema_name"].fillna("valuation") == "valuation"]
    base = baseline(val)
    resp = firm_responses(val[val["perturbation_type"].isin(("none", *TYPES))], base, n_boot)
    resp = resp[resp["perturbation_type"].isin(TYPES)].copy()
    v0 = base[base["condition"] == "C"].set_index("firm_id")["v0"]
    resp = resp[resp["firm_id"].map(v0) > 0]
    resp["se"] = (resp["ci_hi"] - resp["ci_lo"]) / 3.92

    def size_class(row) -> str:
        if row["perturbation_type"] == "shares":
            return "m=2"
        x = params(row["perturbation_params"]).get("x_mn")
        eq = book_equity(store.package(row["firm_id"]))
        if not x or not eq or eq <= 0:
            return "rule"
        share = x / eq
        tier = min((0.02, 0.05, 0.10), key=lambda t: abs(t - share))
        return f"{tier:.0%}" if abs(share - tier) <= 0.002 else "rule"

    resp["size"] = resp.apply(size_class, axis=1)
    resp["group"] = resp["firm_id"].str[0]
    return resp


def _firm_combined(cells: pd.DataFrame) -> pd.DataFrame:
    """Inverse-variance combination of a firm's cells (fixed effect)."""
    rows = []
    for fid, g in cells.dropna(subset=["R", "se"]).groupby("firm_id"):
        g = g[g["se"] > 0]
        if g.empty:
            continue
        w = 1 / g["se"] ** 2
        rows.append({"firm_id": fid, "group": g["group"].iloc[0],
                     "R": float(np.sum(w * g["R"]) / np.sum(w)),
                     "se": float(math.sqrt(1 / np.sum(w)))})
    return pd.DataFrame(rows)


def pooled_table(cells: pd.DataFrame, dilution: pd.DataFrame | None = None) -> pd.DataFrame:
    rows = []
    for ptype in TYPES:
        sub = cells[cells["perturbation_type"] == ptype]
        if sub.empty:
            continue
        firms = _firm_combined(sub)
        for grp in ("all", "L", "M", "S"):
            f = firms if grp == "all" else firms[firms["group"] == grp]
            rows.append({"item": ptype, "size": "all sizes", "group": grp,
                         **dl_pool(f["R"].to_numpy(float), f["se"].to_numpy(float))})
        for size, s in sub.groupby("size"):
            rows.append({"item": ptype, "size": size, "group": "all",
                         **dl_pool(s["R"].to_numpy(float), s["se"].to_numpy(float))})
    if dilution is not None and not dilution.empty:
        d = dilution[dilution["group"] == "S"]
        d = d[d["itm_agent"].astype("boolean").fillna(False)]
        for v in ("V0", "V2", "V3"):
            if f"R_dil_{v}" not in d:
                continue
            x = d.dropna(subset=[f"R_dil_{v}"])
            se = ((x[f"R_dil_{v}_hi"] - x[f"R_dil_{v}_lo"]) / 3.92).to_numpy(float)
            rows.append({"item": v, "size": "CB", "group": "S",
                         **dl_pool(x[f"R_dil_{v}"].to_numpy(float), se)})
    t = pd.DataFrame(rows)
    t.insert(1, "label", t["item"].map(LABEL))
    return t


def pooled_results(table: pd.DataFrame) -> list[Result]:
    out = []
    for _, r in table[(table["group"].isin(["all", "S"])) &
                      (table["size"].isin(["all sizes", "CB"]))].iterrows():
        out.append(Result(f"POOL-{r['item']}", "exploratory",
                          f"pooled R, {r['label']} (DL, firms)", r["mean"],
                          (r["ci_lo"], r["ci_hi"]), r["p_vs_1"], int(r["k"]), "= 1",
                          f"p vs 0 {r['p_vs_0']:.3g}; I2 {r['I2']:.2f}; unweighted median "
                          f"{r['median_unweighted']:.2f}"))
    return out
