"""Synthetic validation (P6 §5.3): run synthetic agents through the runner and check that
the metrics recover the behaviour built into them.

| Agent                      | Expected                              | Pass band              |
| Oracle (noise 5%)          | beta ~ 1 (all conditions), R ~ 1,     | mean beta [0.95, 1.05] |
|                            | eps ~ 0, R_dil ~ 1, E9 success        | mean R [0.9, 1.1],     |
|                            |                                       | eps < 1%, >= 95% succ. |
| Anchored                   | beta ~ 0, R ~ 0                       | |beta| < .05, |R| < .1 |
| Mixture (w = 0.6)          | beta ~ 0.6                            | [0.55, 0.65]           |
| Condition mixture          | industry 0, name 0.2, memory 0.3      | each within +-0.05     |
|   (w = 1, 1, 0.8, 0.5)     |                                       |                        |
| NoDilution                 | R_dil ~ 0, E9 reflection failure      | |R_dil| < .1, >= 95%   |
| CalcError                  | eps ~ 10%, E9 computation failure     | [9%, 11%], >= 95%      |
Means are taken over firms where the metric is defined (positive values for beta; firms in
the money from the agent's own valuation for R_dil). Firms with a non-positive oracle value
are counted and reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.agents.synthetic import (
    AnchoredAgent,
    CalcErrorAgent,
    ConditionMixtureAgent,
    MixtureAgent,
    NoDilutionAgent,
    OracleAgent,
)
from src.config import Config
from src.experiments import builders as b
from src.metrics.baseline import baseline
from src.metrics.decomposition import decompose
from src.metrics.dilution import firm_dilution
from src.metrics.elasticity import firm_elasticity
from src.metrics.failure_modes import classify_runs
from src.metrics.response import firm_responses, response_ratio
from src.metrics.self_consistency import run_epsilons
from src.perturb.sizing import SizeDecision, decide_size
from src.runner.cache import NullCache
from src.runner.jobs import JobSpec, PackageStore, expand
from src.runner.run import Runner, flatten

COND_W = {"A": 1.0, "B": 1.0, "D": 0.8, "C": 0.5}


@dataclass
class Check:
    agent: str
    metric: str
    expected: str
    value: float
    passed: bool
    n: int
    note: str = ""


@dataclass
class ValidationResult:
    checks: list[Check] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def table(self) -> pd.DataFrame:
        return pd.DataFrame([c.__dict__ for c in self.checks])


def run_agent(agent, specs: list[JobSpec], store: PackageStore) -> pd.DataFrame:
    runner = Runner(agent, NullCache(), log_runs=False, max_workers=1)  # type: ignore[arg-type]
    s = runner.run(specs, store)
    return pd.DataFrame([flatten(r) for r in s.records])


def sizes_from(runs: pd.DataFrame, store: PackageStore, cfg: Config) -> list[SizeDecision]:
    """E3 sizes from the agent's own E0 cell (the design's E0 -> sizing -> E3 order)."""
    out = []
    for r in baseline(runs).query("condition == 'C'").itertuples():
        pkg = store.package(r.firm_id)
        cash = pkg.bs.find("cash")
        cash_latest = cash.values.get(pkg.latest_year) if cash else None
        sigma = 0.0 if np.isnan(r.sigma) else r.sigma
        for kind in ("cash", "non_operating"):
            out.append(decide_size(r.firm_id, kind, r.v0, sigma, r.shares_agent,
                                   r.equity_agent, cash_latest, cfg.experiments))
    return out


def with_e3(agent, cfg: Config, store: PackageStore, firm_ids: list[str], reps: int,
            model: str, base_specs: list[JobSpec]) -> pd.DataFrame:
    runs = run_agent(agent, base_specs, store)
    sizes = sizes_from(runs, store, cfg)
    e3 = run_agent(agent, b.e3(cfg, store, firm_ids, reps=reps, sizes=sizes, **_syn(model)),
                   store)
    parts = [df.dropna(axis=1, how="all") for df in (runs, e3) if not df.empty]
    return pd.concat(parts, ignore_index=True) if parts else runs


def oracle_anchor(store: PackageStore, firm_ids: list[str], factor: float = 1.5
                  ) -> dict[str, float]:
    """Anchor = factor x the zero-noise oracle value at k = 1 (positive values only)."""
    spec = JobSpec(experiment="anchor", firm_ids=firm_ids, conditions=["C"],
                   perturbations=[("none", {})], reps=1, agent_structure="SYN",
                   model_key="syn_oracle")
    oracle = OracleAgent(0.0)
    out = {}
    for req, pkg in expand(spec, store):
        v = oracle.run(req, pkg).output["result"]["value_per_share"]
        if v > 0:
            out[req.firm_id] = v * factor
    return out


def _mean(s: pd.Series) -> tuple[float, int]:
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    return (float(s.mean()) if len(s) else np.nan), int(len(s))


def _check(res: ValidationResult, agent: str, metric: str, expected: str, value: float,
           n: int, lo: float, hi: float, note: str = "") -> None:
    ok = bool(n > 0 and lo <= value <= hi)
    res.checks.append(Check(agent, metric, expected, value, ok, n, note))


def _syn(model: str, **kw) -> dict:
    return {"agent_structure": "SYN", "model_key": model, **kw}


def validate(cfg: Config, store: PackageStore, firm_ids: list[str], reps: int = 10,
             noise: float = 0.05, n_boot: int = 200, seed: int = 0) -> ValidationResult:
    res = ValidationResult()
    anchor = oracle_anchor(store, firm_ids)
    positive = sorted(anchor)
    res.info.update(firms=len(firm_ids), positive_oracle=len(positive),
                    nonpositive_oracle=sorted(set(firm_ids) - set(anchor)), reps=reps,
                    noise=noise)

    # Oracle: E2 (all conditions), E3, E8
    o = with_e3(OracleAgent(noise), cfg, store, firm_ids, reps, "syn_oracle",
                b.e0_e2(cfg, store, firm_ids, reps=reps, **_syn("syn_oracle"))
                + b.e8(cfg, store, firm_ids, reps=reps, **_syn("syn_oracle")))
    betas = firm_elasticity(o)
    for cond in ("A", "B", "D", "C"):
        v, n = _mean(betas.loc[betas.condition == cond, "beta"])
        _check(res, "oracle", f"mean beta ({cond})", "1", v, n, 0.95, 1.05)
    resp = firm_responses(o, baseline(o), n_boot, seed)
    for ptype in ("cash", "non_operating", "shares"):
        v, n = _mean(resp.loc[resp.perturbation_type == ptype, "R"])
        _check(res, "oracle", f"mean R ({ptype})", "1", v, n, 0.9, 1.1)
    eps = run_epsilons(o)
    v, n = _mean(eps["eps"])
    _check(res, "oracle", "mean eps", "0", v, n, 0.0, 0.01)
    dil = firm_dilution(o, n_boot, seed)
    for tag in ("V0", "V2", "V3"):
        col = f"R_dil_{tag}"
        v, n = _mean(dil[col]) if col in dil else (np.nan, 0)
        _check(res, "oracle", f"mean R_dil ({tag})", "1", v, n, 0.9, 1.1)
    basic = dict(zip(dil["firm_id"], dil["N_v1"], strict=False)) if not dil.empty else {}
    itm = set(dil.loc[dil["itm_agent"].eq(True), "firm_id"]) if not dil.empty else set()
    stages = classify_runs(o, basic)
    st = stages[stages.firm_id.isin(itm)]
    _check(res, "oracle", "E9 success share", ">= 95%",
           float((st.stage == "success").mean()) if len(st) else np.nan, len(st), 0.95, 1.0)
    res.info["oracle_itm_cb_firms"] = len(itm)

    # Anchored: E2 condition C and E3 (positive-oracle firms)
    a = with_e3(AnchoredAgent(anchor, noise), cfg, store, positive, reps, "syn_anchored",
                b.e0_e2(cfg, store, positive, reps=reps, conditions=["C"],
                        **_syn("syn_anchored")))
    v, n = _mean(firm_elasticity(a)["beta"])
    _check(res, "anchored", "mean beta (C)", "0", v, n, -0.05, 0.05)
    ra = firm_responses(a, baseline(a), n_boot, seed)
    v, n = _mean(ra["R"])
    _check(res, "anchored", "mean R (all types)", "0", v, n, -0.1, 0.1)

    # Mixture w = 0.6
    m = run_agent(MixtureAgent(anchor, 0.6, noise),
                  b.e0_e2(cfg, store, positive, reps=reps, conditions=["C"],
                          **_syn("syn_mixture")), store)
    v, n = _mean(firm_elasticity(m)["beta"])
    _check(res, "mixture(0.6)", "mean beta (C)", "0.6", v, n, 0.55, 0.65)

    # Condition-dependent mixture: decomposition
    cm = run_agent(ConditionMixtureAgent(anchor, COND_W, noise),
                   b.e0_e2(cfg, store, positive, reps=reps, **_syn("syn_cond_mixture")), store)
    dec = decompose(firm_elasticity(cm))
    for comp, target in (("industry_eff", 0.0), ("name_eff", 0.2), ("memory_eff", 0.3)):
        v, n = _mean(dec[comp]) if comp in dec else (np.nan, 0)
        _check(res, "condition mixture", f"mean {comp}", f"{target}", v, n,
               target - 0.05, target + 0.05)

    # NoDilution and CalcError on E8 (CalcError also on E0 for eps)
    nd = run_agent(NoDilutionAgent(noise),
                   b.e8(cfg, store, firm_ids, reps=reps, **_syn("syn_no_dilution")), store)
    dn = firm_dilution(nd, n_boot, seed)
    cols = [c for c in ("R_dil_V0", "R_dil_V2", "R_dil_V3") if c in dn]
    v, n = _mean(pd.concat([dn[c] for c in cols])) if cols else (np.nan, 0)
    _check(res, "no_dilution", "mean R_dil (V0, V2, V3)", "0", v, n, -0.1, 0.1)
    sn = classify_runs(nd, basic)
    sn = sn[sn.firm_id.isin(itm)]
    _check(res, "no_dilution", "E9 reflection share", ">= 95%",
           float((sn.stage == "reflection_failure").mean()) if len(sn) else np.nan, len(sn),
           0.95, 1.0)

    ce = run_agent(CalcErrorAgent(noise),
                   b.e0(cfg, store, firm_ids, reps=reps, **_syn("syn_calc_error"))
                   + b.e8(cfg, store, firm_ids, reps=reps, **_syn("syn_calc_error")), store)
    v, n = _mean(run_epsilons(ce)["eps"])
    _check(res, "calc_error", "mean eps", "10%", v, n, 0.09, 0.11)
    sc = classify_runs(ce, basic)
    sc = sc[sc.firm_id.isin(itm)]
    _check(res, "calc_error", "E9 computation share", ">= 95%",
           float((sc.stage == "computation_failure").mean()) if len(sc) else np.nan, len(sc),
           0.95, 1.0)
    return res


def ci_coverage(n_firms: int = 200, n: int = 10, sigma_rel: float = 0.05,
                delta_rel: float = 0.10, n_boot: int = 1000, seed: int = 0) -> float:
    """Share of simulated oracle firms whose bootstrap CI for R contains 1."""
    rng = np.random.default_rng(seed)
    hits = 0
    for i in range(n_firms):
        v0 = float(rng.uniform(1e3, 1e5))
        delta = v0 * delta_rel
        base = v0 + rng.normal(0, sigma_rel * v0, n)
        pert = v0 + delta + rng.normal(0, sigma_rel * v0, n)
        r = response_ratio(base, pert, delta, n_boot, seed + i)
        hits += int(r["ci_lo"] <= 1.0 <= r["ci_hi"])
    return hits / n_firms


def report(res: ValidationResult, coverage: float | None, title: str) -> str:
    t = res.table()
    lines = [f"# {title}", "",
             f"- Firms: {res.info.get('firms')}; positive oracle value: "
             f"{res.info.get('positive_oracle')}; reps {res.info.get('reps')}; "
             f"noise sd {res.info.get('noise')}",
             f"- CB firms in the money for the oracle: {res.info.get('oracle_itm_cb_firms')}",
             f"- Firms with a non-positive oracle value (excluded from log metrics and "
             f"anchored/mixture agents): {', '.join(res.info.get('nonpositive_oracle', []))}",
             f"- Overall: **{'PASS' if res.passed else 'FAIL'}**", "",
             "| agent | metric | expected | recovered | n | pass |", "|---|---|---|---|---|---|"]
    for r in t.itertuples():
        lines.append(f"| {r.agent} | {r.metric} | {r.expected} | {r.value:.4f} | {r.n} | "
                     f"{'✓' if r.passed else '✗'} |")
    if coverage is not None:
        ok = 0.93 <= coverage <= 0.97
        lines += ["", f"Bootstrap CI coverage (200 simulated oracle firms, n = 10, 95% CI for "
                      f"R): **{coverage:.1%}** ({'within' if ok else 'outside'} 93–97%)"]
    return "\n".join(lines) + "\n"
