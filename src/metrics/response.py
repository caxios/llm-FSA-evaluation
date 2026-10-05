"""Response ratio R (E3; research plan §5.2).

R = (median of perturbed runs - median of baseline runs) / theoretical change, with the
theoretical change computed from the agent's own baseline cell (D6.1, D6.2): V0 and the
median `shares_used` of the E0 cell. Percentile bootstrap CI (D6.4).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.metrics.bootstrap import DEFAULT_REPS, median_diff_ci
from src.metrics.cells import AGENT_KEYS, params, values
from src.perturb.sizing import lower_bound_per_share

SINGLE_ITEM = ("cash", "non_operating", "shares")


def theoretical_delta(ptype: str, p: dict, v0: float, shares_agent: float) -> float:
    """Theoretical per-share change in KRW."""
    if ptype == "cash":
        return -p["x_mn"] * 1e6 / shares_agent
    if ptype == "non_operating":
        return p["x_mn"] * 1e6 / shares_agent
    if ptype == "shares":
        return v0 / p["m"] - v0
    if ptype == "scale":
        return v0 * (p["k"] - 1)
    if ptype == "none":
        return 0.0
    raise ValueError(f"no theoretical delta for '{ptype}'")


def response_ratio(base: np.ndarray, pert: np.ndarray, delta_star: float,
                   n_boot: int = DEFAULT_REPS, seed: int = 0) -> dict:
    out = {"R": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "delta_obs": np.nan,
           "delta_star": delta_star, "n_base": len(base), "n_pert": len(pert)}
    if len(base) == 0 or len(pert) == 0:
        return out
    delta_obs = float(np.median(pert) - np.median(base))
    out["delta_obs"] = delta_obs
    if not delta_star or not math.isfinite(delta_star):
        return out
    lo, hi, _ = median_diff_ci(base, pert, n_boot, seed)
    a, b = sorted((lo / delta_star, hi / delta_star))
    out.update(R=delta_obs / delta_star, ci_lo=a, ci_hi=b)
    return out


def min_perturbation(sigma: float, n: int, target_se: float = 0.1) -> float:
    return lower_bound_per_share(sigma, n, target_se)


def firm_responses(runs: pd.DataFrame, base_summary: pd.DataFrame, n_boot: int = DEFAULT_REPS,
                   seed: int = 0) -> pd.DataFrame:
    """R per firm x perturbation cell (single-item types) against the E0 cell.

    `base_summary` is `baseline()` output; its condition-C rows give V0 and shares_agent.
    """
    rows = []
    bsum = base_summary[base_summary["condition"] == "C"].set_index(["firm_id", *AGENT_KEYS])
    base_runs = runs[(runs["condition"] == "C") & (runs["perturbation_type"] == "none")]
    pert = runs[runs["perturbation_type"].isin(SINGLE_ITEM) & (runs["condition"] == "C")]
    keys = ["firm_id", "perturbation_type", "perturbation_params", *AGENT_KEYS]
    for key, g in pert.groupby(keys, sort=True):
        firm, ptype, ptext, agent, model = key
        if (firm, agent, model) not in bsum.index:
            continue
        b = bsum.loc[(firm, agent, model)]
        base = values(base_runs[(base_runs.firm_id == firm) & (base_runs.agent_structure == agent)
                                & (base_runs.model_key == model)])
        delta = theoretical_delta(ptype, params(ptext), b["v0"], b["shares_agent"])
        res = response_ratio(base, values(g), delta, n_boot, seed)
        rows.append({"firm_id": firm, "perturbation_type": ptype, "perturbation_params": ptext,
                     "agent_structure": agent, "model_key": model, **res})
    return pd.DataFrame(rows)
