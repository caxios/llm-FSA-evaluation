"""Self-consistency epsilon (E1).

The reported per-share value is recomputed from the agent's own reported FCFF, rates and
bridge items (`valuation_tools`, the same code the tool agent uses). Stage gaps show where
the reported number departs from its own chain: discounting (EV), bridge (equity given the
reported EV) or division (per share given the reported equity). FCFF itself is not
recomputed from growth and margin assumptions: the schema does not carry every FCFF
component (documented limitation).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.agents.valuation_tools import (
    dcf_value,
    diluted_value,
    equity_bridge,
    per_share,
)
from src.metrics.cells import AGENT_KEYS, output
from src.parse.schema import ValuationOutput


@dataclass
class Recomputed:
    ev_re: float
    equity_re: float
    vps_re: float
    vps_re_alt: float          # other discounting convention
    ev_gap: float
    equity_gap: float
    vps_gap: float


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b) if b else (0.0 if a == b else math.inf)


def _vps(out: ValuationOutput, equity: float) -> float:
    d, c = out.dilution, out.calculation
    if d.dilution_applied and d.convertible_shares:
        face = out.extracted.convertible_bonds_outstanding or 0.0
        return diluted_value(equity, c.shares_used, face, d.convertible_shares)
    return per_share(equity, c.shares_used)


def recompute(out: ValuationOutput) -> Recomputed:
    c, a = out.calculation, out.assumptions
    other = "mid_year" if c.discounting_convention == "end_of_year" else "end_of_year"
    ev_re, _ = dcf_value(c.fcff, a.wacc, a.terminal_growth, c.discounting_convention)
    ev_alt, _ = dcf_value(c.fcff, a.wacc, a.terminal_growth, other)
    equity_re = equity_bridge(ev_re, c.net_debt, c.non_operating_assets_added)
    vps_re = _vps(out, equity_re)
    vps_alt = _vps(out, equity_bridge(ev_alt, c.net_debt, c.non_operating_assets_added))
    eq_given_ev = equity_bridge(c.enterprise_value, c.net_debt, c.non_operating_assets_added)
    return Recomputed(ev_re=ev_re, equity_re=equity_re, vps_re=vps_re, vps_re_alt=vps_alt,
                      ev_gap=_rel(c.enterprise_value, ev_re),
                      equity_gap=_rel(c.equity_value, eq_given_ev),
                      vps_gap=_rel(out.result.value_per_share, _vps(out, c.equity_value)))


def epsilon(out: ValuationOutput) -> dict:
    r = recompute(out)
    v = out.result.value_per_share
    return {"eps": _rel(v, r.vps_re), "eps_alt": _rel(v, r.vps_re_alt), "vps_re": r.vps_re,
            "ev_gap": r.ev_gap, "equity_gap": r.equity_gap, "vps_gap": r.vps_gap}


def run_epsilons(runs: pd.DataFrame) -> pd.DataFrame:
    """One row per valid valuation run."""
    rows = []
    for _, row in runs[runs["valid"].eq(True)].iterrows():
        d = output(row)
        if "calculation" not in d:
            continue
        try:
            e = epsilon(ValuationOutput.model_validate(d))
        except (ValueError, ZeroDivisionError):
            e = {"eps": np.nan}
        rows.append({"job_id": row["job_id"], "firm_id": row["firm_id"],
                     "condition": row["condition"], **{k: row[k] for k in AGENT_KEYS}, **e})
    return pd.DataFrame(rows)


def firm_epsilon(eps_runs: pd.DataFrame, threshold: float = 0.05) -> pd.DataFrame:
    if eps_runs.empty:
        return pd.DataFrame(columns=["firm_id", *AGENT_KEYS, "eps_mean"])
    g = eps_runs.replace([np.inf], np.nan).groupby(["firm_id", *AGENT_KEYS])["eps"]
    return pd.DataFrame({"eps_mean": g.mean(), "eps_median": g.median(),
                         "share_eps_gt_5pct": g.apply(lambda s: float((s > threshold).mean())),
                         "n_eps": g.count()}).reset_index()
