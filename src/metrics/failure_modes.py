"""Failure-stage classification for CB runs (E9; research plan E9).

Applied in order to V0/V2/V3 runs where dilution is theoretically relevant:
  1 extraction_failure   convertible shares missing or off the truth by more than 5%
  2 reflection_failure   the shares behind the per-share value are the basic shares (within
                         0.5%): the dilution was read but not used
  3 computation_failure  the reported value differs from the recomputation by more than 2%
  4 success
The shares behind the per-share value are the reported diluted shares when the agent says it
applied dilution, else `shares_used`.
"""

from __future__ import annotations

import pandas as pd

from src.metrics.cells import AGENT_KEYS, output, params
from src.metrics.self_consistency import recompute
from src.parse.schema import ValuationOutput

STAGES = ("extraction_failure", "reflection_failure", "computation_failure", "success")


def classify(out: ValuationOutput, truth_convertible_shares: float, basic_shares: float,
             extraction_tol: float = 0.05, reflection_tol: float = 0.005,
             computation_tol: float = 0.02) -> str:
    cs = out.dilution.convertible_shares
    if not cs or abs(cs / truth_convertible_shares - 1) > extraction_tol:
        return "extraction_failure"
    d, c = out.dilution, out.calculation
    effective = d.diluted_shares if d.dilution_applied and d.diluted_shares else c.shares_used
    if not d.dilution_applied or abs(effective / basic_shares - 1) <= reflection_tol:
        return "reflection_failure"
    vre = recompute(out).vps_re
    if vre == 0 or abs(out.result.value_per_share - vre) / abs(vre) > computation_tol:
        return "computation_failure"
    return "success"


def classify_runs(runs: pd.DataFrame, basic_shares: dict[str, float]) -> pd.DataFrame:
    """Stage per valid V0/V2/V3 run; truth convertible shares from the variant metadata."""
    rows = []
    cb = runs[runs["perturbation_type"].isin(["cb_v0", "cb_v2", "cb_v3"])
              & runs["valid"].eq(True)]
    for _, r in cb.iterrows():
        truth = params(r["perturbation_params"]).get("convertible_shares")
        basic = basic_shares.get(r["firm_id"])
        if not truth or not basic:
            continue
        try:
            stage = classify(ValuationOutput.model_validate(output(r)), truth, basic)
        except (ValueError, ZeroDivisionError):
            stage = "computation_failure"
        rows.append({"job_id": r["job_id"], "firm_id": r["firm_id"],
                     "perturbation_type": r["perturbation_type"],
                     **{k: r[k] for k in AGENT_KEYS}, "stage": stage})
    return pd.DataFrame(rows)


def stage_shares(stages: pd.DataFrame) -> pd.DataFrame:
    if stages.empty:
        return pd.DataFrame(columns=["firm_id", *AGENT_KEYS, *STAGES])
    t = pd.crosstab([stages["firm_id"], stages["agent_structure"], stages["model_key"]],
                    stages["stage"], normalize="index")
    for s in STAGES:
        if s not in t:
            t[s] = 0.0
    return t[list(STAGES)].reset_index()
