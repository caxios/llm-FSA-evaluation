"""Job builders for the experiment modules (P5 §5.7; research plan §6.7).

| E0    | condition C, unperturbed, n reps (identical prompts to the E2 k = 1 cells)   |
| E2    | conditions A/B/D/C x k grid x n reps                                         |
| E3    | condition C; cash / non-operating sized per firm (SizeDecision), shares m   |
| E5    | identification prompts, conditions A/B/D, k in {1, 1.5}, 3 reps              |
| E6    | memory quiz per firm (name only, no package), 3 reps                         |
| E7    | conditions A and C at k = 1 for E7 candidates (same prompts as E2: cached)   |
| E8    | condition C, CB V0-V4 (two placebos) for small caps with a CB block          |
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from src.config import PROJECT_ROOT, Config
from src.perturb.base import book_equity
from src.perturb.cb import PLACEBOS
from src.perturb.sizing import SizeDecision
from src.runner.jobs import JobSpec, PackageStore

GROUND_TRUTH = PROJECT_ROOT / "data" / "ground_truth"
IDENT_REPS = 3
QUIZ_REPS = 3


def e0_e2(cfg: Config, store: PackageStore, firm_ids: list[str], *, reps: int | None = None,
          conditions: list[str] | None = None, **common) -> list[JobSpec]:
    exp = cfg.experiments
    perts = [("none", {})] + [("scale", {"k": k}) for k in exp.k_grid if k != 1.0]
    return [JobSpec(experiment="E2", firm_ids=firm_ids,
                    conditions=conditions or ["A", "B", "D", "C"], perturbations=perts,
                    reps=reps or exp.n_default, **common)]


def e0(cfg: Config, store: PackageStore, firm_ids: list[str], *, reps: int | None = None,
       **common) -> list[JobSpec]:
    """Baseline: condition C, unperturbed (the same prompts as the E2 k = 1 cells)."""
    return [JobSpec(experiment="E0", firm_ids=firm_ids, conditions=["C"],
                    perturbations=[("none", {})], reps=reps or cfg.experiments.n_default,
                    **common)]


def e3(cfg: Config, store: PackageStore, firm_ids: list[str], *, reps: int | None = None,
       sizes: list[SizeDecision] | None = None, tiers: bool = False,
       **common) -> list[JobSpec]:
    """Without `sizes` (before E0) cash and non-operating use the 5% floor of book equity
    as a placeholder; tag the run accordingly."""
    exp = cfg.experiments
    n = reps or exp.n_default
    specs = [JobSpec(experiment="E3", firm_ids=firm_ids, conditions=["C"],
                     perturbations=[("shares", {"m": exp.share_multiplier})], reps=n,
                     **common)]
    for kind in ("cash", "non_operating"):
        perts: dict[str, list[tuple[str, dict]]] = {}
        nreps: dict[str, int] = {}
        if sizes is not None:
            for d in sizes:
                if d.perturbation == kind and d.status != "excluded" and d.x_mn is not None \
                        and d.firm_id in firm_ids:
                    perts[d.firm_id] = [(kind, {"x_mn": d.x_mn})]
                    nreps[d.firm_id] = reps or d.n
        else:
            for fid in firm_ids:
                eq = book_equity(store.package(fid))
                if eq and eq > 0:
                    perts[fid] = [(kind, {"x_mn": exp.size_floor * eq})]
                    nreps[fid] = n
        if tiers:   # every firm with positive book equity (D7.8), not only rule-size firms
            for fid in firm_ids:
                eq = book_equity(store.package(fid))
                if eq and eq > 0:
                    perts.setdefault(fid, [])
                    perts[fid] += [(kind, {"x_mn": t * eq}) for t in exp.tiers]
                    nreps.setdefault(fid, n)
        specs.append(JobSpec(experiment="E3", firm_ids=sorted(perts), conditions=["C"],
                             perturbations=perts, reps=nreps, **common))
    return specs


def e5(cfg: Config, store: PackageStore, firm_ids: list[str], *, reps: int | None = None,
       **common) -> list[JobSpec]:
    perts = [("none", {}) if k == 1.0 else ("scale", {"k": k})
             for k in cfg.experiments.k_identification]
    return [JobSpec(experiment="E5", firm_ids=firm_ids, conditions=["A", "B", "D"],
                    perturbations=perts, reps=reps or IDENT_REPS,
                    schema_name="identification", **common)]


def e6(cfg: Config, store: PackageStore, firm_ids: list[str], *, reps: int | None = None,
       **common) -> list[JobSpec]:
    return [JobSpec(experiment="E6", firm_ids=firm_ids, conditions=["C"],
                    perturbations=[("none", {})], reps=reps or QUIZ_REPS, schema_name="quiz",
                    **common)]


def e7_candidates() -> set[str]:
    path = GROUND_TRUTH / "anchor_prices.parquet"
    if not path.exists():
        return set()
    df = pd.read_parquet(path)
    return set(df.loc[df["e7_candidate"].eq(True), "firm_id"])


def e7(cfg: Config, store: PackageStore, firm_ids: list[str], *, reps: int | None = None,
       **common) -> list[JobSpec]:
    cands = [f for f in firm_ids if f in e7_candidates()]
    return [JobSpec(experiment="E7", firm_ids=cands, conditions=["A", "C"],
                    perturbations=[("none", {})], reps=reps or cfg.experiments.n_default,
                    **common)]


def e8(cfg: Config, store: PackageStore, firm_ids: list[str], *, reps: int | None = None,
       **common) -> list[JobSpec]:
    cb_firms = [f for f in firm_ids if store.package(f).cb is not None]
    perts = [(v, {}) for v in ("cb_v0", "cb_v1", "cb_v2", "cb_v3")]
    perts += [("cb_v4", {"placebo": p}) for p in PLACEBOS]
    return [JobSpec(experiment="E8", firm_ids=cb_firms, conditions=["C"], perturbations=perts,
                    reps=reps or cfg.experiments.n_default, include_cb=True, **common)]


def e10(cfg: Config, store: PackageStore, firm_ids: list[str], *, reps: int | None = None,
        **common) -> list[JobSpec]:
    """E10 (P9 §5.5): E8 V0 and V1 with the CB block at the front vs in the middle of a
    fixed-length filler. V1 shows "없음" in the CB slot, so each position has its own V1
    baseline."""
    cb_firms = [f for f in firm_ids if store.package(f).cb is not None]
    return [JobSpec(experiment="E10", firm_ids=cb_firms, conditions=["C"],
                    perturbations=[("cb_v0", {}), ("cb_v1", {})],
                    reps=reps or cfg.experiments.n_default, include_cb=True,
                    cb_position=pos, **common)
            for pos in ("front", "middle")]


BUILDERS: dict[str, Callable[..., list[JobSpec]]] = {
    "E0": e0, "E2": e0_e2, "E3": e3, "E5": e5, "E6": e6, "E7": e7, "E8": e8, "E10": e10}
