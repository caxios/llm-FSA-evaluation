"""RQ2 (P10 §5.2): H2a, decomposition, H2b, H2c, H2d."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.outliers_influence import variance_inflation_factor

from src.analysis.common import Result, mean_ci, wilcoxon_one_sided

COMPONENTS = ("industry_eff", "name_eff", "memory_eff", "total_atten")


def h2a(ft: pd.DataFrame) -> list[Result]:
    """E_i = beta_D - beta_C (memory_eff) > 0, one-sided Wilcoxon; all firms and by group."""
    out = []
    for label, sub in [("all", ft)] + [(g, ft[ft["group"] == g]) for g in ("L", "M", "S")]:
        e = sub["memory_eff"].dropna().to_numpy(float)
        out.append(Result("H2a" if label == "all" else f"H2a-{label}",
                          "primary" if label == "all" else "exploratory",
                          f"median E_i ({label})", float(np.median(e)) if len(e) else np.nan,
                          mean_ci(e), wilcoxon_one_sided(e, 0, "greater"), len(e), "> 0",
                          f"mean {e.mean():.4f}" if len(e) else ""))
    return out


def decomposition_table(ft: pd.DataFrame, n_boot: int = 2000, seed: int = 0) -> pd.DataFrame:
    """Mean components with bootstrap CIs over firms, and shares of total attenuation."""
    rng = np.random.default_rng(seed)
    rows = []
    for label, sub in [("all", ft)] + [(g, ft[ft["group"] == g]) for g in ("L", "M", "S")]:
        d = sub[list(COMPONENTS)].dropna()
        if d.empty:
            continue
        x = d.to_numpy(float)
        boots = x[rng.integers(0, len(x), (n_boot, len(x)))].mean(axis=1)
        total = x[:, 3].mean()
        for j, c in enumerate(COMPONENTS):
            lo, hi = np.quantile(boots[:, j], [0.025, 0.975])
            rows.append({"group": label, "component": c, "mean": x[:, j].mean(), "ci_lo": lo,
                         "ci_hi": hi, "share_of_total": x[:, j].mean() / total if total else
                         np.nan, "n": len(x)})
    return pd.DataFrame(rows)


def _industry(ft: pd.DataFrame, min_firms: int = 5) -> pd.Series:
    k = ft["ksic2"].astype(str)
    counts = k.value_counts()
    return k.where(k.map(counts) >= min_firms, "other")


def h2b(ft: pd.DataFrame) -> tuple[list[Result], pd.DataFrame]:
    """WLS E_i ~ M_i + ln(mcap) + industry FE + id_rate_D, weights 1/se(E_i)^2, HC3;
    one-sided gamma_1 > 0. OLS alongside; VIFs; tercile-stratified slopes if VIF(M) > 5."""
    cols = ["memory_eff", "M_i", "market_cap", "id_rate_D"]
    d = ft.dropna(subset=[c for c in cols if c in ft]).copy()
    if "id_rate_D" not in d:
        d["id_rate_D"] = 0.0
    d = d[d["market_cap"] > 0]
    if len(d) < 10:
        return [Result("H2b", "primary", "gamma_1 (M_i)", np.nan, n=len(d),
                       note="too few firms with E_i, M_i and market cap")], pd.DataFrame()
    d["ln_cap"] = np.log(d["market_cap"].astype(float))
    ind = pd.get_dummies(_industry(d), prefix="ind", drop_first=True, dtype=float)
    X = sm.add_constant(pd.concat([d[["M_i", "ln_cap", "id_rate_D"]].astype(float), ind],
                                  axis=1))
    y = d["memory_eff"].astype(float)
    se = d.get("memory_eff_se", pd.Series(np.nan, index=d.index)).astype(float)
    w = 1 / se.clip(lower=se[se > 0].min() if (se > 0).any() else 1) ** 2
    w = w.fillna(w.median() if w.notna().any() else 1.0)
    rows, results = [], []
    for name, fit in (("WLS", sm.WLS(y, X, weights=w).fit(cov_type="HC3")),
                      ("OLS", sm.OLS(y, X).fit(cov_type="HC3"))):
        for term in ("M_i", "ln_cap", "id_rate_D"):
            rows.append({"model": name, "term": term, "coef": fit.params[term],
                         "se": fit.bse[term], "p_two_sided": fit.pvalues[term]})
        g, s = fit.params["M_i"], fit.bse["M_i"]
        results.append(Result("H2b" if name == "WLS" else "H2b-OLS",
                              "primary" if name == "WLS" else "robustness",
                              f"gamma_1 (M_i), {name}, HC3", float(g), (g - 1.96 * s, g + 1.96 * s),
                              float(stats.norm.sf(g / s)), len(d), "> 0",
                              f"R2 {fit.rsquared:.3f}; industry dummies {ind.shape[1]}"))
    core = X[["const", "M_i", "ln_cap", "id_rate_D"]]
    vifs = {c: variance_inflation_factor(core.values, i) for i, c in enumerate(core.columns)
            if c != "const"}
    tab = pd.DataFrame(rows)
    tab.attrs["vif"] = vifs
    results[0].note += f"; VIF(M_i) {vifs['M_i']:.2f}, VIF(ln_cap) {vifs['ln_cap']:.2f}"
    if vifs["M_i"] > 5:
        d["tercile"] = pd.qcut(d["ln_cap"], 3, labels=False)
        for t, sub in d.groupby("tercile"):
            if len(sub) > 5:
                f = sm.OLS(sub["memory_eff"], sm.add_constant(sub[["M_i"]])).fit(cov_type="HC3")
                rows.append({"model": f"OLS tercile {t}", "term": "M_i", "coef": f.params["M_i"],
                             "se": f.bse["M_i"], "p_two_sided": f.pvalues["M_i"]})
        tab = pd.DataFrame(rows)
        tab.attrs["vif"] = vifs
    return results, tab


def h2c(ft: pd.DataFrame) -> Result:
    """E7: log V_C = a + b1 log V_A + b2 log P_old + e, HC3; b2 > 0."""
    d = ft.dropna(subset=["v_C_e7", "v_A_e7", "p_old"])
    d = d[(d["v_C_e7"] > 0) & (d["v_A_e7"] > 0) & (d["p_old"] > 0)]
    if len(d) < 10:
        return Result("H2c", "exploratory", "b2 (log P_old)", np.nan, n=len(d),
                      note="too few firms")
    X = sm.add_constant(np.column_stack([np.log(d["v_A_e7"]), np.log(d["p_old"])]))
    fit = sm.OLS(np.log(d["v_C_e7"].to_numpy(float)), X).fit(cov_type="HC3")
    b2, s = fit.params[2], fit.bse[2]
    return Result("H2c", "exploratory", "b2 (log P_old) in log V_C ~ log V_A + log P_old", b2,
                  (b2 - 1.96 * s, b2 + 1.96 * s), float(stats.norm.sf(b2 / s)), len(d), "> 0",
                  f"b1 = {fit.params[1]:.3f}")


def h2d(ft: pd.DataFrame) -> Result:
    e = ft["industry_eff"].dropna().to_numpy(float)
    return Result("H2d", "exploratory", "median beta_A - beta_B",
                  float(np.median(e)) if len(e) else np.nan, mean_ci(e),
                  wilcoxon_one_sided(e, 0, "greater"), len(e), "> 0")
