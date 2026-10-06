"""RQ3 (P10 §5.2): H3, H3c, placebo specificity (TOST), H3b."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.analysis.common import (
    Result,
    dl_weighted_mean,
    mean_ci,
    one_sided_z,
    t_one_sided,
    wilcoxon_one_sided,
    wilson,
)
from src.metrics.failure_modes import STAGES


def _itm(ft: pd.DataFrame) -> pd.DataFrame:
    s = ft[ft["group"] == "S"]
    return s[s["itm_agent"].astype("boolean").fillna(False)] if "itm_agent" in s else s.iloc[:0]


def h3(ft: pd.DataFrame) -> list[Result]:
    """R_dil (V0 vs V1) < 1 for small caps whose CB is in the money for the agent: DL
    weighted mean (SE from the bootstrap CI width), Wilcoxon robustness."""
    d = _itm(ft).dropna(subset=["R_dil_V0"])
    r = d["R_dil_V0"].to_numpy(float)
    se = ((d["R_dil_V0_hi"] - d["R_dil_V0_lo"]) / 3.92).to_numpy(float)
    mu, mu_se, tau2 = dl_weighted_mean(r, se)
    out = [Result("H3", "primary", "DL weighted mean R_dil (V0 vs V1), ITM small caps", mu,
                  (mu - 1.96 * mu_se, mu + 1.96 * mu_se), one_sided_z(mu, mu_se, 1, "less"),
                  len(r), "< 1", f"tau2 = {tau2:.4f}")]
    m, p, _ = t_one_sided(r, 1, "less")
    out.append(Result("H3-unweighted", "robustness", "mean R_dil, t test", m, mean_ci(r), p,
                      len(r), "< 1"))
    out.append(Result("H3-wilcoxon", "robustness", "median R_dil, Wilcoxon",
                      float(np.median(r)) if len(r) else np.nan,
                      p=wilcoxon_one_sided(r, 1, "less"), n=len(r), direction="< 1"))
    return out


def h3c(ft: pd.DataFrame) -> Result:
    d = _itm(ft).dropna(subset=["dose_slope"])
    x = d["dose_slope"].to_numpy(float)
    m, p, _ = t_one_sided(x, 1, "less")
    icpt = d["dose_intercept"].dropna()
    return Result("H3c", "exploratory", "mean dose-response slope", m, mean_ci(x), p, len(x),
                  "< 1", f"median intercept {icpt.median():.1f} KRW" if len(icpt) else "")


def specificity(ft: pd.DataFrame) -> tuple[Result, pd.DataFrame]:
    """Placebo V4 vs V0: a firm is equivalent when the shift's 95% bootstrap CI lies within
    +-sigma_i (TOST at alpha = 0.025 per side, conservative); pooled: mean shift / sigma."""
    s = ft[ft["group"] == "S"]
    rows = []
    for _, r in s.iterrows():
        sigma = r.get("sigma_C")
        for name in ("redeemed_cb", "irrelevant"):
            lo, hi = r.get(f"placebo_{name}_shift_lo"), r.get(f"placebo_{name}_shift_hi")
            if pd.isna(lo) or pd.isna(hi) or pd.isna(sigma) or not sigma:
                continue
            rows.append({"firm_id": r["firm_id"], "placebo": name,
                         "shift": r.get(f"placebo_{name}_shift"), "lo": lo, "hi": hi,
                         "sigma": sigma, "equivalent": bool(-sigma < lo and hi < sigma),
                         "shift_over_sigma": r.get(f"placebo_{name}_shift") / sigma})
    tab = pd.DataFrame(rows)
    if tab.empty:
        return Result("specificity", "exploratory", "share equivalent (TOST +-sigma)", np.nan,
                      note="no placebo cells"), tab
    k, n = int(tab["equivalent"].sum()), len(tab)
    z = tab["shift_over_sigma"].dropna().to_numpy(float)
    pooled = stats.ttest_1samp(z, 0).pvalue if len(z) > 1 else np.nan
    return Result("specificity", "exploratory", "share of firm x placebo cells equivalent",
                  k / n, wilson(k, n), n=n,
                  note=f"mean shift/sigma {z.mean():.3f} (two-sided p {pooled:.3f})"), tab


def h3b(ft: pd.DataFrame) -> tuple[Result, pd.DataFrame]:
    """E9 stage shares among ITM small caps: firm-mean proportions with Wilson CIs over
    pooled firm-runs; firm majority extraction vs reflection compared with a sign test."""
    d = _itm(ft).dropna(subset=list(STAGES), how="all")
    if d.empty:
        return Result("H3b", "exploratory", "reflection - extraction share", np.nan,
                      note="no classified runs"), pd.DataFrame()
    n = len(d)
    rows = []
    for s in STAGES:
        m = float(d[s].mean())
        lo, hi = wilson(round(m * n), n)
        rows.append({"stage": s, "mean_share": m, "ci_lo": lo, "ci_hi": hi, "n_firms": n})
    tab = pd.DataFrame(rows)
    ext, ref = d["extraction_failure"], d["reflection_failure"]
    more_ref, more_ext = int((ref > ext).sum()), int((ext > ref).sum())
    p = stats.binomtest(more_ref, more_ref + more_ext, 0.5, alternative="greater").pvalue \
        if more_ref + more_ext else np.nan
    return Result("H3b", "exploratory", "mean reflection share - extraction share",
                  float(ref.mean() - ext.mean()), p=float(p), n=n, direction="> 0",
                  note=f"firms reflection > extraction {more_ref}, < {more_ext}"), tab
