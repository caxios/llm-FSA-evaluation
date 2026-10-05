"""CB dilution metrics (E8; research plan E8, D6.3).

Theory per variant from the agent's own V1 cell (CB terms removed): E = median equity
value (KRW million), N = median shares used. F (KRW million) and the shares issued on
conversion come from the variant's perturbation metadata (V0: as built, V2: doubled face,
V3: lowered conversion price); V1 and the V4 placebos have no theoretical change.
  v_debt = E / N, v_conv = (E + F) / (N + dN), v* = min(v_conv, v_debt), delta = v* - v_debt
Firms out of the money from the agent's own valuation (E/N <= Pc) have delta = 0 and are
excluded from R_dil (reported separately with their actual change).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.agents.valuation_tools import if_converted, if_converted_shares
from src.metrics.bootstrap import DEFAULT_REPS, median_diff_ci
from src.metrics.cells import AGENT_KEYS, params, values
from src.metrics.elasticity import ols_hc3
from src.metrics.response import response_ratio

THEORY_VARIANTS = ("cb_v0", "cb_v2", "cb_v3")


def theoretical_diluted_value(E: float, N: float, F: float, Pc: float
                              ) -> tuple[float, float, float]:
    """(v_star, v_debt, delta) with E, F in KRW million and Pc in KRW."""
    v_conv, v_debt = if_converted(E, N, F, Pc)
    v_star = min(v_conv, v_debt)
    return v_star, v_debt, v_star - v_debt


def cb_theory(variant: str, E: float, N: float, p: dict) -> float:
    if variant not in THEORY_VARIANTS:
        return 0.0
    F, dn = p.get("face_mn"), p.get("convertible_shares")
    if not F or not dn or N <= 0:
        return 0.0
    v_conv, v_debt = if_converted_shares(E, N, F, dn)
    return min(v_conv, v_debt) - v_debt


def r_dil(v1: np.ndarray, vj: np.ndarray, delta_star: float, n_boot: int = DEFAULT_REPS,
          seed: int = 0) -> dict:
    return response_ratio(v1, vj, delta_star, n_boot, seed)


def dose_response(v1: np.ndarray, by_variant: dict[str, np.ndarray],
                  theory: dict[str, float]) -> dict:
    """Within-firm regression of (v_run - median V1) on theory_j over V0/V2/V3 runs, with the
    V1 runs at theory 0."""
    base = float(np.median(v1))
    xs, ys = [np.zeros(len(v1))], [v1 - base]
    for v, runs in by_variant.items():
        if v in theory and len(runs):
            xs.append(np.full(len(runs), theory[v]))
            ys.append(runs - base)
    x, y = np.concatenate(xs), np.concatenate(ys)
    if len(np.unique(x)) < 2:
        return {"dose_slope": np.nan, "dose_se": np.nan, "dose_intercept": np.nan}
    b, se = ols_hc3(np.column_stack([np.ones_like(x), x]), y)
    return {"dose_slope": float(b[1]), "dose_se": float(se[1]), "dose_intercept": float(b[0])}


def placebo_shift(ref: np.ndarray, v4: np.ndarray, n_boot: int = DEFAULT_REPS,
                  seed: int = 0) -> dict:
    """Median shift of a placebo variant against its reference (V0), with bootstrap SE and
    CI (inputs for an equivalence test)."""
    if len(ref) == 0 or len(v4) == 0:
        return {"shift": np.nan, "shift_se": np.nan, "shift_lo": np.nan, "shift_hi": np.nan}
    lo, hi, reps = median_diff_ci(ref, v4, n_boot, seed)
    return {"shift": float(np.median(v4) - np.median(ref)), "shift_se": float(np.std(reps)),
            "shift_lo": lo, "shift_hi": hi,
            "shift_rel": float((np.median(v4) - np.median(ref)) / abs(np.median(ref)))
            if np.median(ref) else np.nan}


def firm_dilution(runs: pd.DataFrame, n_boot: int = DEFAULT_REPS, seed: int = 0
                  ) -> pd.DataFrame:
    """One row per firm x agent x model with R_dil per variant, dose response and placebos."""
    cb = runs[runs["perturbation_type"].str.startswith("cb_")]
    rows = []
    for key, g in cb.groupby(["firm_id", *AGENT_KEYS], sort=True):
        v1_cell = g[g["perturbation_type"] == "cb_v1"]
        ok = v1_cell[v1_cell["valid"].eq(True)]
        if ok.empty:
            continue
        E, N = float(ok["equity_value"].median()), float(ok["shares_used"].median())
        v1 = values(v1_cell)
        row = dict(zip(["firm_id", *AGENT_KEYS], key, strict=True)) | {"E_v1": E, "N_v1": N}
        theory, by_variant = {}, {}
        for variant in THEORY_VARIANTS:
            cell = g[g["perturbation_type"] == variant]
            if cell.empty:
                continue
            p = params(cell["perturbation_params"].iloc[0])
            theory[variant] = cb_theory(variant, E, N, p)
            by_variant[variant] = values(cell)
            tag = variant.removeprefix("cb_").upper()
            row[f"theory_{tag}"] = theory[variant]
            if theory[variant] != 0:
                res = r_dil(v1, by_variant[variant], theory[variant], n_boot, seed)
                row |= {f"R_dil_{tag}": res["R"], f"R_dil_{tag}_lo": res["ci_lo"],
                        f"R_dil_{tag}_hi": res["ci_hi"]}
            else:
                row[f"delta_obs_{tag}_otm"] = (float(np.median(by_variant[variant])
                                                     - np.median(v1))
                                               if len(by_variant[variant]) and len(v1)
                                               else np.nan)
        row["itm_agent"] = any(t != 0 for t in theory.values())
        row |= dose_response(v1, by_variant, theory) if row["itm_agent"] else {}
        v0 = by_variant.get("cb_v0", np.array([]))
        for _, cell in g[g["perturbation_type"] == "cb_v4"].groupby("perturbation_params"):
            name = params(cell["perturbation_params"].iloc[0]).get("placebo", "v4")
            ps = placebo_shift(v0, values(cell), n_boot, seed)
            row |= {f"placebo_{name}_{k}": v for k, v in ps.items()}
        rows.append(row)
    return pd.DataFrame(rows)
