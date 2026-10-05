"""Cell helpers over the run-level table (P6 §5.1).

A cell is firm x condition x perturbation (type + params) x agent structure x model.
Metric functions take a filtered DataFrame of the run table and never read files.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

AGENT_KEYS = ["agent_structure", "model_key"]
CELL_KEYS = ["firm_id", "condition", "perturbation_type", "perturbation_params", *AGENT_KEYS]


@lru_cache(maxsize=4096)
def _params(text: str | None) -> dict:
    return json.loads(text) if text else {}


def params(row_or_text) -> dict:
    text = row_or_text if isinstance(row_or_text, str) or row_or_text is None \
        else row_or_text["perturbation_params"]
    return dict(_params(text))


def param(runs: pd.DataFrame, name: str, default=np.nan) -> pd.Series:
    return runs["perturbation_params"].map(lambda t: params(t).get(name, default))


def valid(runs: pd.DataFrame) -> pd.DataFrame:
    return runs[runs["valid"].eq(True)]


def values(runs: pd.DataFrame) -> np.ndarray:
    return valid(runs)["value_per_share"].dropna().to_numpy(dtype=float)


def baseline_cell(runs: pd.DataFrame) -> pd.DataFrame:
    """The E0 cell (D6.2): condition C, unperturbed."""
    return runs[(runs["condition"] == "C") & (runs["perturbation_type"] == "none")]


def output(row) -> dict:
    text = row["output_json"]
    return json.loads(text) if isinstance(text, str) and text else {}


def k_of(runs: pd.DataFrame) -> pd.Series:
    """Scale factor per run: 1 for unperturbed rows, params k for scale rows."""
    k = param(runs, "k", np.nan)
    return k.where(runs["perturbation_type"] != "none", 1.0)
