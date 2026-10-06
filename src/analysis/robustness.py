"""Robustness (P10 §5.3), one entry per research-plan §7.5 item.

R1 identified firms excluded (H2a/H2b); R2 R by perturbation tier; R3 half reps (H1);
R4 anomaly-flagged runs excluded; R5 comparison model; R6 instruction; R7 complex CBs;
R8 low-validity cells excluded; R9 median-based beta.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.analysis.common import Result, wilcoxon_one_sided
from src.analysis.rq1 import h1
from src.analysis.rq2 import h2a, h2b
from src.analysis.rq3 import h3
from src.metrics.baseline import baseline
from src.metrics.cells import AGENT_KEYS, params
from src.metrics.decomposition import decompose
from src.metrics.dilution import firm_dilution
from src.metrics.elasticity import firm_elasticity
from src.metrics.response import firm_responses
from src.parse.validate import LOW_VALIDITY
from src.perturb.base import book_equity


def quick_table(runs: pd.DataFrame, sample: pd.DataFrame, n_boot: int = 200) -> pd.DataFrame:
    """beta_C/se_C, E_i components and R_dil for a run subset (no decomposition bootstrap)."""
    val = runs[runs["schema_name"].fillna("valuation") == "valuation"]
    betas = firm_elasticity(val)
    key = ["firm_id", *AGENT_KEYS]
    t = pd.DataFrame(columns=key)
    if not betas.empty:
        wide = betas.pivot_table(index=key, columns="condition", values=["beta", "se_hc3"],
                                 aggfunc="first")
        wide.columns = [f"{'beta' if a == 'beta' else 'se'}_{c}" for a, c in wide.columns]
        t = wide.reset_index()
        dec = decompose(betas)
        if not dec.empty:
            t = t.merge(dec, on=key, how="left")
    dil = firm_dilution(val, n_boot)
    if not dil.empty:
        t = t.merge(dil, on=key, how="outer")
    return sample[["firm_id", "group", "ksic2", "market_cap"]].merge(t, on="firm_id",
                                                                      how="right")


def r1_identified(ft: pd.DataFrame) -> list[Result]:
    out = []
    for col in ("id_rate_D", "id_rate_A"):
        if col not in ft:
            continue
        sub = ft[~(ft[col] >= 0.5)]
        a = h2a(sub)[0]
        b = h2b(sub)[0][0]
        for r in (a, b):
            r.id, r.kind = f"R1-{col}-{r.id}", "robustness"
            r.note = f"excluding {int((ft[col] >= 0.5).sum())} firms with {col} >= 0.5; " + r.note
        out += [a, b]
    return out


def r2_tiers(runs: pd.DataFrame, store) -> tuple[Result, pd.DataFrame]:
    """R by tier (2/5/10% of book equity) for cash and non-operating; trend by Spearman.
    `runs`: main valuation runs (the E0 cell is the baseline)."""
    val = runs[runs["schema_name"].fillna("valuation") == "valuation"]
    e3 = val[val["perturbation_type"].isin(["cash", "non_operating"])]
    if e3.empty:
        return Result("R2", "robustness", "R by tier", np.nan, note="no E3 runs"), pd.DataFrame()
    resp = firm_responses(pd.concat([val[val["perturbation_type"] == "none"], e3]),
                          baseline(val), 200)
    return _tier_table(resp[resp["perturbation_type"].isin(["cash", "non_operating"])], store)


def _tier_table(resp: pd.DataFrame, store) -> tuple[Result, pd.DataFrame]:
    rows = []
    for _, r in resp.iterrows():
        x = params(r["perturbation_params"]).get("x_mn")
        eq = book_equity(store.package(r["firm_id"]))
        if not x or not eq or eq <= 0:
            continue
        share = x / eq
        tier = min((0.02, 0.05, 0.10), key=lambda t: abs(t - share))
        if abs(share - tier) > 0.002:
            tier = np.nan                       # rule-size cell, not a tier
        rows.append({"firm_id": r["firm_id"], "perturbation": r["perturbation_type"],
                     "tier": tier, "share_of_equity": share, "R": r["R"]})
    d = pd.DataFrame(rows)
    if d.empty:
        return Result("R2", "robustness", "R by tier", np.nan), d
    t = d.dropna(subset=["tier", "R"])
    summary = t.groupby(["perturbation", "tier"])["R"].agg(["median", "mean", "count"])
    rho, p = stats.spearmanr(t["tier"], t["R"]) if len(t) > 3 else (np.nan, np.nan)
    return Result("R2", "robustness", "Spearman rho(tier, R)", float(rho), p=float(p), n=len(t),
                  note="median R by tier: " + "; ".join(
                      f"{k[0]} {k[1]:.0%} {v:.2f}" for k, v in summary["median"].items())), \
        summary.reset_index()


def r3_half_reps(runs: pd.DataFrame, sample: pd.DataFrame, draws: int = 100, seed: int = 0
                 ) -> Result:
    """H1 statistic with a random half of the reps per cell (draws)."""
    rng = np.random.default_rng(seed)
    val = runs[runs["schema_name"].fillna("valuation") == "valuation"]
    L = set(sample.loc[sample["group"] == "L", "firm_id"])
    c = val[(val["condition"] == "C") & val["firm_id"].isin(L)
            & val["perturbation_type"].isin(["none", "scale"])]
    reps = sorted(c["rep"].unique())
    stats_ = []
    for _ in range(draws):
        keep = set(rng.choice(reps, size=max(1, len(reps) // 2), replace=False))
        betas = firm_elasticity(c[c["rep"].isin(keep)])
        stats_.append(float(betas.loc[betas["condition"] == "C", "beta"].mean()))
    s = np.array(stats_)
    return Result("R3", "robustness", "mean beta_C (L) with half the reps (100 draws)",
                  float(np.mean(s)), (float(np.quantile(s, 0.025)), float(np.quantile(s, 0.975))),
                  n=draws)


def primary_on_subset(runs: pd.DataFrame, sample: pd.DataFrame, label: str) -> list[Result]:
    t = quick_table(runs, sample)
    out = []
    for r in (h1(t)[0], h2a(t)[0], h3(t)[0]):
        r.id, r.kind = f"{label}-{r.id}", "robustness"
        out.append(r)
    return out


def r4_anomaly(runs: pd.DataFrame, sample: pd.DataFrame) -> list[Result]:
    flag = runs["anomaly_flag"].astype("boolean").fillna(False)
    out = primary_on_subset(runs[~flag], sample, "R4")
    for r in out:
        r.note = f"anomaly-flagged runs excluded ({float(flag.mean()):.1%} of runs); " + r.note
    return out


def r8_low_validity(runs: pd.DataFrame, sample: pd.DataFrame) -> list[Result]:
    keys = ["firm_id", "condition", "perturbation_type", "perturbation_params", "experiment"]
    v = runs.groupby(keys)["valid"].transform("mean")
    out = primary_on_subset(runs[v >= LOW_VALIDITY], sample, "R8")
    for r in out:
        r.note = f"cells below {LOW_VALIDITY:.0%} validity excluded; " + r.note
    return out


def r5_comparison(ft_cmp: pd.DataFrame, ft_main: pd.DataFrame, firms: list[str]
                  ) -> list[Result]:
    out = []
    for name, t in (("comparison", ft_cmp), ("primary", ft_main)):
        sub = t[t["firm_id"].isin(firms)]
        b = sub["beta_C"].dropna()
        e = (sub["beta_D"] - sub["beta_C"]).dropna() if "beta_D" in sub else pd.Series(
            dtype=float)
        out.append(Result(f"R5-beta_C-{name}", "robustness", f"median beta_C ({name}, 30 firms)",
                          float(b.median()) if len(b) else np.nan,
                          p=wilcoxon_one_sided(b.to_numpy(float), 1, "less"), n=len(b),
                          direction="< 1"))
        out.append(Result(f"R5-E-{name}", "robustness", f"median E_i ({name}, 30 firms)",
                          float(e.median()) if len(e) else np.nan,
                          p=wilcoxon_one_sided(e.to_numpy(float), 0, "greater"), n=len(e),
                          direction="> 0"))
    return out


def r6_instruction(ft_p: pd.DataFrame, ft_instr: pd.DataFrame) -> Result:
    d = ft_p.set_index("firm_id")[["beta_C"]].join(
        ft_instr.set_index("firm_id")[["beta_C"]], rsuffix="_instr", how="inner").dropna()
    if len(d) < 3:
        return Result("R6", "robustness", "paired beta_C: instruction - none", np.nan,
                      n=len(d), note="too few firms")
    diff = d["beta_C_instr"] - d["beta_C"]
    return Result("R6", "robustness", "median paired beta_C: with rule 6 - without (P)",
                  float(diff.median()), p=float(stats.wilcoxon(diff).pvalue), n=len(d),
                  note=f"mean {diff.mean():.4f}")


def r7_complex_cb(sample: pd.DataFrame) -> Result:
    known = sample["cb_complex"].notna().sum() if "cb_complex" in sample else 0
    return Result("R7", "robustness", "H3 without complex CBs", np.nan, n=int(known),
                  note="not run: cb_complex is unknown for every firm (no structured field "
                       "for call options or net settlement, D2.8)")


def r9_median_beta(ft: pd.DataFrame) -> list[Result]:
    t = ft.assign(beta_C=ft["beta_median_C"], se_C=ft["se_C"])
    r = h1(t)[1]
    r.id, r.statistic = "R9-H1", "mean median-based beta_C (L), t test"
    return [r]
