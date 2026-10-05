"""Baseline (E0): V0, noise and compliance per firm x condition x agent x model."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.metrics.cells import AGENT_KEYS

GROUP = ["firm_id", "condition", *AGENT_KEYS]


def _summary(g: pd.DataFrame) -> pd.Series:
    v = g.loc[g["valid"].eq(True), "value_per_share"].dropna().to_numpy(dtype=float)
    ok = g[g["valid"].eq(True)]
    return pd.Series({
        "v0": float(np.median(v)) if len(v) else np.nan,
        "sigma": float(np.std(v, ddof=1)) if len(v) > 1 else np.nan,
        "mad": float(np.median(np.abs(v - np.median(v)))) if len(v) else np.nan,
        "n_valid": int(len(v)), "n_total": int(len(g)),
        "compliance": len(v) / len(g) if len(g) else np.nan,
        "shares_agent": float(ok["shares_used"].median()) if len(ok) else np.nan,
        "equity_agent": float(ok["equity_value"].median()) if len(ok) else np.nan,
        "n_nonpositive": int((v <= 0).sum()),
    })


def baseline(runs: pd.DataFrame) -> pd.DataFrame:
    """Unperturbed cells only (perturbation_type == 'none')."""
    base = runs[runs["perturbation_type"] == "none"]
    if base.empty:
        return pd.DataFrame(columns=[*GROUP, "v0", "sigma"])
    return base.groupby(GROUP, sort=True).apply(_summary, include_groups=False).reset_index()
