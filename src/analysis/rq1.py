"""RQ1 (P10 §5.2): H1, H1b, nonlinearity, H1c."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from src.analysis.common import (
    Result,
    dl_weighted_mean,
    mean_ci,
    one_sided_z,
    t_one_sided,
    wilcoxon_one_sided,
)
from src.metrics.elasticity import scale_runs


def h1(ft: pd.DataFrame) -> list[Result]:
    """Large caps, beta_C < 1: DL random-effects weighted mean (primary), unweighted t and
    Wilcoxon (robustness)."""
    L = ft[(ft["group"] == "L")].dropna(subset=["beta_C"])
    b, se = L["beta_C"].to_numpy(float), L["se_C"].to_numpy(float)
    mu, mu_se, tau2 = dl_weighted_mean(b, se)
    out = [Result("H1", "primary", "DL weighted mean beta_C (L)", mu,
                  (mu - 1.96 * mu_se, mu + 1.96 * mu_se), one_sided_z(mu, mu_se, 1, "less"),
                  len(L), "< 1", f"tau2 = {tau2:.4f}")]
    m, p, _ = t_one_sided(b, 1, "less")
    out.append(Result("H1-unweighted", "robustness", "mean beta_C (L), t test", m, mean_ci(b), p,
                      len(b), "< 1"))
    out.append(Result("H1-wilcoxon", "robustness", "median beta_C (L), Wilcoxon",
                      float(np.median(b)) if len(b) else np.nan, p=wilcoxon_one_sided(b, 1, "less"),
                      n=len(b), direction="< 1"))
    return out


def pooled_runs(runs: pd.DataFrame, sample: pd.DataFrame, condition: str = "C"
                ) -> pd.DataFrame:
    r = scale_runs(runs)
    r = r[(r["condition"] == condition) & r["valid"].eq(True) & (r["value_per_share"] > 0)]
    r = r.merge(sample[["firm_id", "group"]], on="firm_id", how="left",
                suffixes=("_run", ""))
    if "group" not in r:
        r["group"] = r["group_run"]
    return r.assign(logv=np.log(r["value_per_share"].astype(float)),
                    logk=np.log(r["k"].astype(float)),
                    small=(r["group"] == "S").astype(float), mid=(r["group"] == "M").astype(float))


def h1b(runs: pd.DataFrame, sample: pd.DataFrame) -> tuple[Result, pd.DataFrame]:
    """log V = firm FE + (b + b_S Small + b_M Mid) log k, SEs clustered by firm; b_S > 0."""
    d = pooled_runs(runs, sample)
    if d["firm_id"].nunique() < 3:
        return Result("H1b", "exploratory", "b_S", np.nan, note="too few firms"), pd.DataFrame()
    fit = smf.ols("logv ~ C(firm_id) + logk + logk:small + logk:mid", data=d).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d["firm_id"])[0]})
    rows = []
    for term in ("logk", "logk:small", "logk:mid"):
        rows.append({"term": term, "coef": fit.params[term], "se": fit.bse[term],
                     "ci_lo": fit.conf_int().loc[term, 0], "ci_hi": fit.conf_int().loc[term, 1],
                     "p_two_sided": fit.pvalues[term]})
    tab = pd.DataFrame(rows)
    bs = tab.set_index("term").loc["logk:small"]
    z = bs["coef"] / bs["se"]
    res = Result("H1b", "exploratory", "b_S (small - large slope), firm-clustered", bs["coef"],
                 (bs["ci_lo"], bs["ci_hi"]), float(stats.norm.sf(z)), int(d["firm_id"].nunique()),
                 "> 0", f"b (large) = {tab.iloc[0]['coef']:.3f}; runs {len(d)}")
    return res, tab


def nonlinearity(ft: pd.DataFrame) -> Result:
    q = ft.dropna(subset=["p_quad_C"])
    share = float((q["p_quad_C"] < 0.05).mean()) if len(q) else np.nan
    return Result("nonlinearity", "exploratory", "share of firms with p(quad) < 0.05", share,
                  n=len(q), note=f"mean beta_quad {q['beta_quad_C'].mean():.3f}")


def h1c(ft_p: pd.DataFrame) -> Result:
    """epsilon by group (structure P; zero by construction under T): L > S, Mann–Whitney."""
    col = next((c for c in ("eps_median", "eps_mean", "epsilon") if c in ft_p), None)
    if col is None or ft_p.empty:
        return Result("H1c", "exploratory", "median eps L - S (P)", np.nan,
                      note="no structure-P epsilon available")
    L = ft_p.loc[ft_p["group"] == "L", col].dropna().to_numpy(float)
    S = ft_p.loc[ft_p["group"] == "S", col].dropna().to_numpy(float)
    if len(L) < 2 or len(S) < 2:
        return Result("H1c", "exploratory", "median eps L - S (P)", np.nan, note="too few firms")
    p = float(stats.mannwhitneyu(L, S, alternative="greater").pvalue)
    return Result("H1c", "exploratory", f"median {col} L - S (structure P)",
                  float(np.median(L) - np.median(S)), p=p, n=len(L) + len(S), direction="> 0",
                  note=f"median L {np.median(L):.3f}, S {np.median(S):.3f}")
