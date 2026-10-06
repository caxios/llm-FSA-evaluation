"""Shared analysis helpers (P10 §5): run selection, firm tables per variant, weighting,
Holm correction, one-sided tests and table writers.

A *variant* is one (tag, agent structure, model, prompt version) combination. The firm-level
metrics are computed separately per variant because the metric functions key firms by
(agent structure, model) only.
"""

from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.config import PROJECT_ROOT

RUNS_DIR = PROJECT_ROOT / "results" / "runs"
TABLES = PROJECT_ROOT / "results" / "tables"
FIGURES = PROJECT_ROOT / "results" / "figures"
TRUTH = PROJECT_ROOT / "data" / "ground_truth"


@dataclass(frozen=True)
class Variant:
    name: str
    tag: str
    agent: str
    model: str
    prompt: str


MAIN = Variant("main", "main", "T", "primary", "v1.2")
VARIANTS = {
    "main": MAIN,
    "ext_P": Variant("ext_P", "ext", "P", "primary", "v1.2"),
    "ext_R": Variant("ext_R", "ext", "R", "primary", "v1.2"),
    "ext_instr": Variant("ext_instr", "ext", "P", "primary", "v1.2_instr"),
    "ext_cmp": Variant("ext_cmp", "ext", "T", "comparison", "v1.2"),
    "ext_e10": Variant("ext_e10", "ext", "T", "primary", "v1.2"),
}


def load_runs(runs_dir: Path = RUNS_DIR) -> pd.DataFrame:
    tables = [pd.read_parquet(p).dropna(axis=1, how="all")
              for p in sorted(runs_dir.glob("E*.parquet"))]
    if not tables:
        return pd.DataFrame()
    return pd.concat(tables, ignore_index=True).drop_duplicates("job_id")


def select(runs: pd.DataFrame, v: Variant) -> pd.DataFrame:
    """Runs of one variant. Quiz/identification runs carry the tag and model only; structure-T
    runs of the main variant that the extension re-uses come from the cache with tag "main"."""
    if runs.empty:
        return runs
    schema = runs["schema_name"].fillna("valuation")
    val = (runs["tag"] == v.tag) & (runs["agent_structure"] == v.agent) \
        & (runs["model_key"] == v.model) & (runs["prompt_version"] == v.prompt) \
        & (schema == "valuation")
    other = (runs["tag"] == v.tag) & (runs["model_key"] == v.model) & (schema != "valuation")
    out = runs[val | other] if v.name == "main" else runs[val]
    if v.name == "ext_e10":
        out = out[out["experiment"] == "E10"]
    elif v.tag == "ext":
        out = out[out["experiment"] != "E10"]
    return out


@dataclass
class Result:
    """One hypothesis test or estimate."""
    id: str
    kind: str                      # primary | exploratory | robustness
    statistic: str
    estimate: float
    ci: tuple[float, float] = (np.nan, np.nan)
    p: float = np.nan
    n: int = 0
    direction: str = ""
    note: str = ""
    p_holm: float = np.nan
    extra: dict = field(default_factory=dict)


def holm(pvalues: list[float]) -> list[float]:
    """Holm step-down adjusted p-values (NaN kept as NaN)."""
    idx = [i for i, p in enumerate(pvalues) if not math.isnan(p)]
    order = sorted(idx, key=lambda i: pvalues[i])
    m, out, running = len(order), [np.nan] * len(pvalues), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        out[i] = running
    return out


def dl_weighted_mean(est: np.ndarray, se: np.ndarray) -> tuple[float, float, float]:
    """DerSimonian–Laird random-effects mean: (mean, se, tau2)."""
    ok = np.isfinite(est) & np.isfinite(se) & (se > 0)
    y, v = est[ok], se[ok] ** 2
    if len(y) < 2:
        return (float(y[0]) if len(y) else np.nan), np.nan, np.nan
    w = 1 / v
    mu_fe = np.sum(w * y) / np.sum(w)
    q = np.sum(w * (y - mu_fe) ** 2)
    c = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    tau2 = max(0.0, (q - (len(y) - 1)) / c) if c > 0 else 0.0
    w_re = 1 / (v + tau2)
    mu = float(np.sum(w_re * y) / np.sum(w_re))
    return mu, float(math.sqrt(1 / np.sum(w_re))), float(tau2)


def one_sided_z(mean: float, se: float, null: float, alternative: str) -> float:
    if not (np.isfinite(mean) and np.isfinite(se)) or se <= 0:
        return np.nan
    z = (mean - null) / se
    return float(stats.norm.cdf(z) if alternative == "less" else stats.norm.sf(z))


def wilcoxon_one_sided(x: np.ndarray, null: float, alternative: str) -> float:
    x = x[np.isfinite(x)] - null
    x = x[x != 0]
    if len(x) < 3:
        return np.nan
    return float(stats.wilcoxon(x, alternative=alternative).pvalue)


def t_one_sided(x: np.ndarray, null: float, alternative: str) -> tuple[float, float, float]:
    """(mean, p, 95% CI half-width-based lower/upper as tuple via ci())."""
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return (float(x.mean()) if len(x) else np.nan), np.nan, np.nan
    res = stats.ttest_1samp(x, null, alternative=alternative)
    return float(x.mean()), float(res.pvalue), float(x.std(ddof=1) / math.sqrt(len(x)))


def mean_ci(x: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return np.nan, np.nan
    h = stats.t.ppf(0.5 + level / 2, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x))
    return float(x.mean() - h), float(x.mean() + h)


def wilson(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    if n == 0:
        return np.nan, np.nan
    z = stats.norm.ppf(0.5 + level / 2)
    p = k / n
    d = 1 + z ** 2 / n
    c = (p + z ** 2 / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / d
    return c - h, c + h


def provenance() -> str:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
                                capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = "unknown"
    return f"code {commit}"


def write_table(df: pd.DataFrame, name: str, title: str = "") -> Path:
    TABLES.mkdir(parents=True, exist_ok=True)
    path = TABLES / f"{name}.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(f"# {title} ({provenance()})\n")
        df.to_csv(f, index=False)
    return path


def results_frame(results: list[Result]) -> pd.DataFrame:
    return pd.DataFrame([{
        "id": r.id, "kind": r.kind, "statistic": r.statistic, "estimate": r.estimate,
        "ci_lo": r.ci[0], "ci_hi": r.ci[1], "p": r.p, "p_holm": r.p_holm, "n": r.n,
        "direction": r.direction, "note": r.note} for r in results])
