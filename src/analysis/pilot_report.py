"""Pilot report (P7 §6): gates G1-G5, sigma stability, n rule, extraction diagnostics,
cost re-estimate. Builds from run-level tables; `render` writes the markdown report.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.agents.synthetic import true_extraction
from src.config import Config, ModelConfig
from src.metrics.baseline import baseline
from src.metrics.cells import output, params
from src.metrics.elasticity import firm_elasticity
from src.metrics.response import firm_responses
from src.metrics.self_consistency import run_epsilons
from src.perturb.sizing import SizeDecision

HANGUL = re.compile(r"[가-힣]")
# main-design new calls by schema (P5 dry run; E7 and E8-V1 reuse E2 prompts)
MAIN_CALLS = {"valuation": 30_000 + 4_320 + 2_960 - 500, "identification": 2_700, "quiz": 450}


@dataclass
class Gate:
    name: str
    metric: str
    value: float | None
    threshold: str
    passed: bool | None          # None = not evaluated yet
    note: str = ""


@dataclass
class PilotResult:
    gates: list[Gate] = field(default_factory=list)
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    numbers: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------- diagnostics


def extraction_check(runs: pd.DataFrame, packages: dict) -> pd.DataFrame:
    """Reported vs true base-year values per valid valuation run (ratio; unit slips are
    ratios off by a factor of 10 or more)."""
    rows = []
    for _, r in runs[runs["valid"].eq(True)].iterrows():
        pkg = packages.get(r["firm_id"])
        out = output(r)
        if pkg is None or "extracted" not in out:
            continue
        truth = true_extraction(pkg)
        ex = out["extracted"]
        k = (params(r["perturbation_params"]).get("k", 1.0)
             if r["perturbation_type"] == "scale" else 1.0)
        row = {"job_id": r["job_id"], "firm_id": r["firm_id"]}
        for f in ("revenue", "operating_income", "cash_and_equivalents", "shares_outstanding"):
            t, v = getattr(truth, f), ex.get(f)
            if f != "shares_outstanding" and t is not None:
                t = t * k
            row[f"{f}_ratio"] = v / t if t and v is not None else np.nan
        ratios = [row[k] for k in row if k.endswith("_ratio") and not math.isnan(row[k])]
        row["unit_slip"] = any(abs(math.log10(abs(x))) >= 1 for x in ratios if x)
        rationale = (out.get("assumptions") or {}).get("assumption_rationale", "")
        row["korean_rationale"] = bool(HANGUL.search(rationale or ""))
        rows.append(row)
    return pd.DataFrame(rows)


def sigma_stability(e0: pd.DataFrame, steps=(5, 10, 15, 20)) -> pd.DataFrame:
    """sigma from the first n reps relative to sigma from all reps, per firm."""
    rows = []
    ok = e0[e0["valid"].eq(True)].sort_values("rep")
    for firm, g in ok.groupby("firm_id"):
        v = g["value_per_share"].to_numpy(float)
        full = np.std(v, ddof=1) if len(v) > 1 else np.nan
        row = {"firm_id": firm, "n_valid": len(v), "sigma_all": full,
               "cv_all": full / abs(np.median(v)) if len(v) and np.median(v) else np.nan}
        for n in steps:
            if len(v) >= n and full:
                row[f"rel_{n}"] = np.std(v[:n], ddof=1) / full
        rows.append(row)
    return pd.DataFrame(rows)


def n_rule(sigma: float, delta: float, cfg: Config) -> int:
    """Reps needed for SE(R) <= s*: n = 2 (sigma / (s* |delta|))^2, clamped (P7 Step 4)."""
    exp = cfg.experiments
    if not delta or math.isnan(sigma):
        return exp.n_max
    n = math.ceil(2 * (sigma / (exp.target_se * abs(delta))) ** 2)
    return int(min(max(n, exp.n_min), exp.n_max))


def cost_estimate(runs: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    rows = []
    v = runs[runs["tokens_in"] > 0]
    schema = v["schema_name"].fillna("valuation") if "schema_name" in v else "valuation"
    v = v.assign(schema_name=schema)
    for name, calls in MAIN_CALLS.items():
        g = v[v["schema_name"] == name]
        if g.empty:
            continue
        tin, tout = g["tokens_in"].mean(), g["tokens_out"].mean()
        usd = calls * (tin * cfg.price_in_per_mtok + tout * cfg.price_out_per_mtok) / 1e6
        rows.append({"schema": name, "main_calls": calls, "mean_tokens_in": tin,
                     "mean_tokens_out": tout, "usd": usd})
    return pd.DataFrame(rows)


def _bootstrap_mean_ci(x: np.ndarray, level: float = 0.90, reps: int = 2000,
                       seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), (reps, len(x)))].mean(axis=1)
    a = (1 - level) / 2
    lo, hi = np.quantile(means, [a, 1 - a])
    return float(lo), float(hi)


# ---------------------------------------------------------------- gates


def evaluate(runs: pd.DataFrame, cfg: Config, sizes: list[SizeDecision] | None = None,
             packages: dict | None = None, n_boot: int = 1000) -> PilotResult:
    res = PilotResult()
    val = runs[runs["schema_name"].fillna("valuation") == "valuation"] \
        if "schema_name" in runs else runs

    # G1 schema compliance (all modules, after retries)
    g1 = float(runs["valid"].mean()) if len(runs) else np.nan
    res.gates.append(Gate("G1 Schema", "valid / all runs", g1, ">= 95%", g1 >= 0.95,
                          f"{int(runs['valid'].sum())}/{len(runs)} runs"))

    # G2 calculation reliability (structure P)
    eps = run_epsilons(val[val["agent_structure"] == "P"])
    share = float((eps["eps"] > 0.05).mean()) if len(eps) else np.nan
    res.gates.append(Gate("G2 Calculation", "share of valid P runs with eps > 5%", share,
                          "< 30%", bool(share < 0.30) if len(eps) else None,
                          f"median eps {eps['eps'].median():.3%}" if len(eps) else ""))
    res.tables["epsilon"] = eps

    # G3 signal: large caps, mean(beta_A - beta_C) with 90% bootstrap CI over firms
    betas = firm_elasticity(val)
    res.tables["betas"] = betas
    wide = betas.pivot_table(index="firm_id", columns="condition", values="beta")
    if {"A", "C"} <= set(wide.columns):
        d = (wide["A"] - wide["C"]).dropna()
        d = d[d.index.str.startswith("L")]
        if len(d) >= 2:
            lo, hi = _bootstrap_mean_ci(d.to_numpy(float))
            m = float(d.mean())
            ok = (lo > 0 or hi < 0) or abs(m) >= 0.10
            res.gates.append(Gate("G3 Signal", "large caps mean(beta_A - beta_C)", m,
                                  "90% CI excludes 0 or |mean| >= 0.10", ok,
                                  f"90% CI [{lo:.3f}, {hi:.3f}], {len(d)} firms"))
    if not any(g.name.startswith("G3") for g in res.gates):
        res.gates.append(Gate("G3 Signal", "large caps mean(beta_A - beta_C)", None,
                              "90% CI excludes 0 or |mean| >= 0.10", None,
                              "needs E2 runs in conditions A and C"))

    # G4 measurability (cash perturbation sizing)
    if sizes:
        cash = [s for s in sizes if s.perturbation == "cash"]
        ok = [s for s in cash if s.status in ("ok", "increased_n") and s.n <= 20]
        g4 = len(ok) / len(cash) if cash else np.nan
        res.gates.append(Gate("G4 Measurability", "firms with a feasible cash size at n <= 20",
                              g4, ">= 80%", bool(g4 >= 0.80) if cash else None,
                              f"{len(ok)}/{len(cash)} firms"))
    else:
        res.gates.append(Gate("G4 Measurability", "firms with a feasible cash size at n <= 20",
                              None, ">= 80%", None, "needs sizing from E0"))

    res.gates.append(Gate("G5 Data", "ITM small caps with CB truth; E8 validity", None,
                          ">= 30 firms; >= 90% valid", None,
                          "pending: S selection waits for KRX KOSDAQ prices"))

    # diagnostics
    base = baseline(val)
    res.tables["baseline"] = base
    res.tables["responses"] = firm_responses(val, base, n_boot) if len(val) else pd.DataFrame()
    c0 = base[base["condition"] == "C"]
    res.numbers["nonpositive_baseline_firms"] = int((c0["v0"] <= 0).sum())
    res.numbers["nonpositive_run_share"] = float(
        (val.loc[val["valid"].eq(True), "value_per_share"] <= 0).mean()) if len(val) else np.nan
    anomaly = val[val["valid"].eq(True)].groupby("perturbation_type")["anomaly_flag"].apply(
        lambda s: float(s.astype("boolean").fillna(False).mean()))
    res.tables["anomaly"] = anomaly.rename("anomaly_rate").reset_index()
    res.numbers["refusal_or_invalid_share"] = 1 - g1 if len(runs) else np.nan
    res.numbers["mean_latency_s"] = float(runs["latency_s"].mean()) if len(runs) else np.nan
    if packages:
        ex = extraction_check(val, packages)
        res.tables["extraction"] = ex
        if len(ex):
            res.numbers["unit_slip_share"] = float(ex["unit_slip"].mean())
            res.numbers["korean_rationale_share"] = float(ex["korean_rationale"].mean())
    e0 = val[(val["experiment"] == "E0")]
    if len(e0):
        res.tables["sigma"] = sigma_stability(e0)
    return res


def size_table(sizes: list[SizeDecision]) -> pd.DataFrame:
    return pd.DataFrame([s.model_dump() for s in sizes])


def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    if isinstance(v, float):
        return f"{v:.3f}" if abs(v) < 100 else f"{v:,.0f}"
    return str(v)


def md_table(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int = 60) -> str:
    if df is None or df.empty:
        return "(none)"
    df = df[cols] if cols else df
    head = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "---|" * len(df.columns)
    rows = ["| " + " | ".join(_fmt(v) for v in r) + " |"
            for r in df.head(max_rows).itertuples(index=False)]
    return "\n".join([head, sep, *rows])


def render(res: PilotResult, title: str, extra: str = "", cost: pd.DataFrame | None = None,
           sizes: pd.DataFrame | None = None) -> str:
    out = [f"# {title}", ""]
    out += ["## Gates", "", "| gate | metric | value | threshold | result | note |",
            "|---|---|---|---|---|---|"]
    for g in res.gates:
        result = "pending" if g.passed is None else ("PASS" if g.passed else "FAIL")
        out.append(f"| {g.name} | {g.metric} | {_fmt(g.value)} | {g.threshold} | {result} | "
                   f"{g.note} |")
    out += ["", "## Diagnostics", ""]
    for k, v in res.numbers.items():
        out.append(f"- {k}: {_fmt(v)}")
    if "betas" in res.tables:
        out += ["", "### Elasticities", "", md_table(res.tables["betas"], [
            "firm_id", "condition", "beta", "se_hc3", "n_used", "n_nonpositive_dropped"])]
    if "baseline" in res.tables:
        out += ["", "### Baseline (E0 / k = 1)", "", md_table(res.tables["baseline"], [
            "firm_id", "condition", "v0", "sigma", "n_valid", "n_total", "shares_agent"])]
    if "sigma" in res.tables:
        out += ["", "### Sigma stability (sigma from first n reps / sigma from all)", "",
                md_table(res.tables["sigma"])]
    if sizes is not None:
        out += ["", "### Size decisions", "", md_table(sizes)]
    if "responses" in res.tables and len(res.tables["responses"]):
        out += ["", "### Response ratios", "", md_table(res.tables["responses"], [
            "firm_id", "perturbation_type", "perturbation_params", "R", "ci_lo", "ci_hi"])]
    if "anomaly" in res.tables:
        out += ["", "### Anomaly-flag rate by perturbation", "", md_table(res.tables["anomaly"])]
    if cost is not None:
        out += ["", "### Main-run cost re-estimate", "", md_table(cost)]
    if extra:
        out += ["", extra]
    return "\n".join(out) + "\n"

