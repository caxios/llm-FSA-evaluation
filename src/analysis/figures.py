"""Figures F2–F7 (P10 §5.4) as PNG and PDF. F1 (design diagram) comes from the paper source.

One style for every figure: light surface, recessive grid, thin marks, categorical hues in a
fixed order (validated: CVD-safe adjacent pairs; two slots below 3:1 contrast, so every
figure carries a legend or direct labels, and every figure has a table in results/tables).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.analysis.common import FIGURES  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]      # fixed order: slots 1–4
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
GROUP_COLOR = {"L": SERIES[0], "M": SERIES[1], "S": SERIES[2]}
GROUP_NAME = {"L": "Large", "M": "Mid", "S": "Small"}
TITLES = True          # the paper build turns titles off (captions carry them)
OUT_DIR = None         # override of FIGURES (paper build)


def _style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
        "ytick.color": INK2, "text.color": INK, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
        "legend.frameon": False, "lines.linewidth": 2})


def _title(ax, text: str) -> None:
    if TITLES:
        ax.set_title(text)


def _save(fig, name: str) -> list[str]:
    out = OUT_DIR or FIGURES
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("png", "pdf"):
        p = out / f"{name}.{ext}"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        paths.append(str(p))
    plt.close(fig)
    return paths


def f2_beta_by_group(ft: pd.DataFrame) -> list[str]:
    _style()
    fig, ax = plt.subplots(figsize=(6, 3.4))
    rng = np.random.default_rng(0)
    for i, g in enumerate(("L", "M", "S")):
        b = ft.loc[ft["group"] == g, "beta_C"].dropna().to_numpy(float)
        if not len(b):
            continue
        x = i + rng.uniform(-0.18, 0.18, len(b))
        ax.scatter(x, b, s=22, color=GROUP_COLOR[g], edgecolor=SURFACE, linewidth=1,
                   label=f"{GROUP_NAME[g]} (n={len(b)})", zorder=3)
        ax.hlines(np.median(b), i - 0.3, i + 0.3, color=INK, linewidth=2, zorder=4)
    ax.axhline(1, color=INK2, linestyle="--", linewidth=1)
    ax.text(2.45, 1, "β = 1", va="center", color=INK2)
    ax.set_xticks([0, 1, 2], [GROUP_NAME[g] for g in ("L", "M", "S")])
    ax.set_ylabel("β_C (scale elasticity, real name)")
    _title(ax, "F2. Scale elasticity by size group (bar = median)")
    ax.legend(loc="upper left", fontsize=8)
    return _save(fig, "F2_beta_by_group")


def f3_decomposition(dec: pd.DataFrame) -> list[str]:
    _style()
    d = dec[dec["component"].isin(["industry_eff", "name_eff", "memory_eff"])]
    groups = [g for g in ("L", "M", "S", "all") if g in set(d["group"])]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    names = {"industry_eff": "Industry (A−B)", "name_eff": "Name (B−D)",
             "memory_eff": "Firm memory (D−C)"}
    width = 0.24
    for j, (c, label) in enumerate(names.items()):
        vals = [d[(d["group"] == g) & (d["component"] == c)]["mean"].squeeze() for g in groups]
        lo = [d[(d["group"] == g) & (d["component"] == c)]["ci_lo"].squeeze() for g in groups]
        hi = [d[(d["group"] == g) & (d["component"] == c)]["ci_hi"].squeeze() for g in groups]
        x = np.arange(len(groups)) + (j - 1) * width
        ax.bar(x, vals, width - 0.03, color=SERIES[j], label=label, zorder=3)
        ax.errorbar(x, vals, yerr=[np.subtract(vals, lo), np.subtract(hi, vals)], fmt="none",
                    ecolor=INK2, elinewidth=1, capsize=2, zorder=4)
    ax.axhline(0, color=INK2, linewidth=1)
    ax.set_xticks(np.arange(len(groups)),
                  [GROUP_NAME.get(g, "All") for g in groups])
    ax.set_ylabel("Δβ (mean, 95% CI)")
    _title(ax, "F3. Decomposition of attenuation (β_A − β_C)")
    ax.legend(fontsize=8, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    return _save(fig, "F3_decomposition")


def f4_memory_scatter(ft: pd.DataFrame) -> list[str]:
    _style()
    d = ft.dropna(subset=["memory_eff", "M_i"])
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    for g in ("L", "M", "S"):
        s = d[d["group"] == g]
        ax.scatter(s["M_i"], s["memory_eff"], s=22, color=GROUP_COLOR[g], edgecolor=SURFACE,
                   linewidth=1, label=GROUP_NAME[g], zorder=3)
    if len(d) > 2:
        b = np.polyfit(d["M_i"], d["memory_eff"], 1)
        xs = np.linspace(d["M_i"].min(), d["M_i"].max(), 50)
        ax.plot(xs, np.polyval(b, xs), color=INK, linewidth=1.5, label="OLS fit")
    ax.axhline(0, color=INK2, linewidth=1)
    ax.set_xlabel("M_i (memory quiz score)")
    ax.set_ylabel("E_i = β_D − β_C")
    _title(ax, "F4. Firm-memory effect vs memory strength")
    ax.legend(fontsize=8)
    return _save(fig, "F4_memory_scatter")


def f5_dose_response(dil: pd.DataFrame) -> list[str]:
    _style()
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    pts = []
    for _, r in dil.iterrows():
        for v in ("V0", "V2", "V3"):
            th, rd = r.get(f"theory_{v}"), r.get(f"R_dil_{v}")
            if pd.notna(th) and pd.notna(rd) and th != 0:
                pts.append((v, th, rd * th))
    if pts:
        p = pd.DataFrame(pts, columns=["variant", "theory", "observed"])
        for j, v in enumerate(("V0", "V2", "V3")):
            s = p[p["variant"] == v]
            ax.scatter(s["theory"], s["observed"], s=22, color=SERIES[j], edgecolor=SURFACE,
                       linewidth=1, label=v, zorder=3)
        lim = [min(p["theory"].min(), p["observed"].min()), 0]
        ax.plot(lim, lim, color=INK2, linestyle="--", linewidth=1, label="observed = theory")
    ax.set_xlabel("theoretical change in value per share (KRW)")
    ax.set_ylabel("observed median change (KRW)")
    _title(ax, "F5. CB dilution: observed vs theoretical change")
    ax.legend(fontsize=8)
    return _save(fig, "F5_dose_response")


def f6_stages(stages: pd.DataFrame) -> list[str]:
    _style()
    cols = ["extraction_failure", "reflection_failure", "computation_failure", "success"]
    labels = ["Extraction failure", "Reflection failure", "Computation failure", "Success"]
    fig, ax = plt.subplots(figsize=(6, 2.6))
    left = np.zeros(len(stages))
    for j, (c, lab) in enumerate(zip(cols, labels, strict=True)):
        v = stages[c].fillna(0).to_numpy(float)
        ax.barh(stages["structure"], v, left=left, color=SERIES[j], label=lab,
                edgecolor=SURFACE, linewidth=2, zorder=3)
        left += v
    ax.set_xlim(0, 1)
    ax.set_xlabel("share of classified runs (firm mean)")
    _title(ax, "F6. E9 failure stages by agent structure")
    ax.legend(fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.3))
    return _save(fig, "F6_stages")


def f7_tiers(tiers: pd.DataFrame) -> list[str]:
    _style()
    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    for j, (ptype, s) in enumerate(tiers.groupby("perturbation")):
        s = s.sort_values("tier")
        ax.plot(s["tier"] * 100, s["median"], marker="o", markersize=6, color=SERIES[j],
                label=ptype.replace("_", "-"))
    ax.axhline(1, color=INK2, linestyle="--", linewidth=1)
    ax.set_xlabel("perturbation size (% of book equity)")
    ax.set_ylabel("median R")
    _title(ax, "F7. Response ratio by perturbation size")
    ax.legend(fontsize=8)
    return _save(fig, "F7_tiers")


def f8_pooled(pool: pd.DataFrame) -> list[str]:
    """Pooled R (DL mean, 95% CI) per item: all firms, all sizes; CB variants for S."""
    _style()
    d = pool[((pool["size"] == "all sizes") & (pool["group"] == "all"))
             | (pool["size"] == "CB")].dropna(subset=["mean"]).iloc[::-1]
    names = {"cash": "Cash distribution", "non_operating": "Non-operating assets",
             "shares": "Shares x2", "V0": "CB dilution V0", "V2": "CB dilution V2",
             "V3": "CB dilution V3"}
    fig, ax = plt.subplots(figsize=(6, 3.2))
    y = np.arange(len(d))
    ax.hlines(y, d["ci_lo"], d["ci_hi"], color=SERIES[0], linewidth=2, zorder=3)
    ax.scatter(d["mean"], y, s=40, color=SERIES[0], edgecolor=SURFACE, linewidth=1.5,
               zorder=4)
    for yi, (_, r) in zip(y, d.iterrows(), strict=True):
        ax.text(max(r["ci_hi"], r["mean"]) + 0.05, yi, f"{r['mean']:.2f}  (firms {int(r['k'])})",
                va="center", fontsize=8, color=INK2)
    ax.axvline(1, color=INK2, linestyle="--", linewidth=1)
    ax.axvline(0, color=GRID, linewidth=1)
    ax.set_yticks(y, [names.get(i, i) for i in d["item"]])
    ax.set_xlabel("pooled response ratio R (1 = full reflection, 0 = none)")
    _title(ax, "F8. Average response across firms (DL random effects, 95% CI)")
    return _save(fig, "F8_pooled")
