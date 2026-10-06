"""Main-run monitoring (P8 §5.3): per-batch QA numbers and stop thresholds.

| Metric                  | Stop threshold                                   | Action  |
| Valid-run rate          | < 90% in a batch                                  | pause   |
| Refusal rate            | > 2%                                              | pause   |
| Anomaly-flag rate       | > 2x the pilot rate for the same module           | inspect |
| model_reported values   | more than one distinct value                      | halt    |
| Spend vs budget         | > 80% of the P8 budget before module 7 (E8)       | levers  |
| Median latency          | informational                                     | -       |
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.config import ModelConfig


@dataclass
class Alert:
    metric: str
    value: float | str | None
    threshold: str
    action: str           # pause | halt | inspect | levers | info
    triggered: bool


def spend_usd(runs: pd.DataFrame, cfg: ModelConfig) -> float:
    """Cost of the distinct calls in `runs` (cache hits share a cache key)."""
    calls = runs.drop_duplicates("cache_key")
    return float((calls["tokens_in"].fillna(0) * cfg.price_in_per_mtok
                  + calls["tokens_out"].fillna(0) * cfg.price_out_per_mtok).sum() / 1e6)


def anomaly_rate(runs: pd.DataFrame) -> float:
    ok = runs[runs["valid"].eq(True)]
    if ok.empty:
        return np.nan
    return float(ok["anomaly_flag"].astype("boolean").fillna(False).mean())


def batch_checks(runs: pd.DataFrame, pilot_anomaly: float | None = None,
                 spent: float | None = None, budget: float | None = None,
                 before_e8: bool = True) -> list[Alert]:
    out = []
    n = len(runs)
    valid = float(runs["valid"].mean()) if n else np.nan
    out.append(Alert("valid-run rate", valid, ">= 90%", "pause", bool(n and valid < 0.90)))
    refusal = float(runs["error"].eq("refusal").mean()) if n else np.nan
    out.append(Alert("refusal rate", refusal, "<= 2%", "pause", bool(n and refusal > 0.02)))
    val = runs[runs["schema_name"].fillna("valuation") == "valuation"]
    rate = anomaly_rate(val) if len(val) else np.nan
    if pilot_anomaly is not None and not np.isnan(rate):
        hit = rate > 2 * pilot_anomaly if pilot_anomaly > 0 else rate > 0.05
        out.append(Alert("anomaly-flag rate", rate, f"<= 2 x pilot ({pilot_anomaly:.3f})",
                         "inspect", bool(hit)))
    else:
        out.append(Alert("anomaly-flag rate", rate, "no pilot rate", "info", False))
    models = sorted(runs["model_reported"].dropna().unique())
    out.append(Alert("model_reported", ", ".join(models), "one distinct value", "halt",
                     len(models) > 1))
    if spent is not None and budget:
        share = spent / budget
        out.append(Alert("spend / budget", share, "<= 80% before E8", "levers",
                         bool(before_e8 and share > 0.80)))
    lat = float(runs["latency_s"].median()) if n else np.nan
    out.append(Alert("median latency (s)", lat, "-", "info", False))
    return out


def cell_completeness(runs: pd.DataFrame) -> pd.DataFrame:
    """Valid reps per firm x condition x perturbation cell (QA: incomplete and low-validity
    cells, P8 §5.5)."""
    keys = ["experiment", "firm_id", "condition", "perturbation_type", "perturbation_params"]
    g = runs.groupby(keys, dropna=False)
    cells = g.agg(n_total=("valid", "size"), n_valid=("valid", "sum")).reset_index()
    cells["validity"] = cells["n_valid"] / cells["n_total"]
    return cells


def extreme_values(runs: pd.DataFrame, factor: float = 10.0) -> pd.DataFrame:
    """Valid valuation runs more than `factor` x the absolute cell median (manual review)."""
    v = runs[runs["valid"].eq(True) & runs["value_per_share"].notna()]
    keys = ["experiment", "firm_id", "condition", "perturbation_type", "perturbation_params"]
    med = v.groupby(keys, dropna=False)["value_per_share"].transform("median").abs()
    return v[(v["value_per_share"].abs() > factor * med) & (med > 0)]
