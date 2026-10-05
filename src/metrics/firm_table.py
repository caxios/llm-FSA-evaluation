"""Firm-level table (P6 §5.2): one row per firm x agent structure x model.

`build_firm_table` combines every metric from the run-level tables; `load_runs` and
`write_firm_table` do the I/O (results/runs/*.parquet -> results/firm_level.parquet).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.conditions.identifiers import FirmIdentifiers
from src.config import PROJECT_ROOT
from src.metrics.baseline import baseline
from src.metrics.bootstrap import DEFAULT_REPS
from src.metrics.cells import AGENT_KEYS
from src.metrics.decomposition import bootstrap_decomposition, decompose
from src.metrics.dilution import firm_dilution
from src.metrics.elasticity import firm_elasticity
from src.metrics.failure_modes import classify_runs, stage_shares
from src.metrics.identification import identification_rate
from src.metrics.memory_quiz import memory_strength, score_quiz
from src.metrics.response import firm_responses
from src.metrics.self_consistency import firm_epsilon, run_epsilons
from src.parse.validate import LOW_VALIDITY

RUNS_DIR = PROJECT_ROOT / "results" / "runs"
KEY = ["firm_id", *AGENT_KEYS]
RESPONSE_NAMES = {"cash": "R_cash", "shares": "R_shares", "non_operating": "R_nonop"}


def load_runs(runs_dir: Path = RUNS_DIR) -> pd.DataFrame:
    tables = [pd.read_parquet(p) for p in sorted(runs_dir.glob("*.parquet"))]
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


def _schema(runs: pd.DataFrame, name: str) -> pd.DataFrame:
    if "schema_name" not in runs:
        return runs if name == "valuation" else runs.iloc[0:0]
    s = runs["schema_name"].fillna("valuation")
    return runs[s == name]


def _merge(left: pd.DataFrame, right: pd.DataFrame, on=KEY) -> pd.DataFrame:
    if right is None or right.empty:
        return left
    return left.merge(right, on=on, how="left")


def build_firm_table(runs: pd.DataFrame, *, sample: pd.DataFrame | None = None,
                     quiz_truth: pd.DataFrame | None = None,
                     identifiers: dict[str, FirmIdentifiers] | None = None,
                     anchors: pd.DataFrame | None = None, n_boot: int = DEFAULT_REPS,
                     seed: int = 0) -> pd.DataFrame:
    val = _schema(runs, "valuation")
    base = baseline(val)
    base_c = base[base["condition"] == "C"].rename(columns={
        "v0": "v0_C", "sigma": "sigma_C", "compliance": "compliance_C"})
    table = base_c[[*KEY, "v0_C", "sigma_C", "compliance_C", "shares_agent", "equity_agent",
                    "n_nonpositive"]].copy()
    if table.empty:
        table = val[KEY].drop_duplicates().reset_index(drop=True)

    betas = firm_elasticity(val)
    if not betas.empty:
        wide = betas.pivot_table(index=KEY, columns="condition",
                                 values=["beta", "se_hc3"], aggfunc="first")
        wide.columns = [f"{'beta' if a == 'beta' else 'se'}_{c}" for a, c in wide.columns]
        quad = betas[betas["condition"] == "C"][[*KEY, "beta_quad", "p_quad",
                                                 "beta_median_based"]]
        table = _merge(_merge(table, wide.reset_index()), quad.rename(
            columns={"beta_quad": "beta_quad_C", "p_quad": "p_quad_C",
                     "beta_median_based": "beta_median_C"}))
        dec = decompose(betas)
        if not dec.empty:
            table = _merge(table, dec)
            if n_boot:
                table = _merge(table, bootstrap_decomposition(val, n_boot, seed))

    resp = firm_responses(val, base, n_boot, seed)
    if not resp.empty:
        for ptype, name in RESPONSE_NAMES.items():
            sub = resp[resp["perturbation_type"] == ptype]
            if sub.empty:
                continue
            first = sub.sort_values("perturbation_params").groupby(KEY).first().reset_index()
            table = _merge(table, first[[*KEY, "R", "ci_lo", "ci_hi"]].rename(columns={
                "R": name, "ci_lo": f"{name}_lo", "ci_hi": f"{name}_hi"}))

    table = _merge(table, firm_epsilon(run_epsilons(val)))

    quiz = _schema(runs, "quiz")
    if quiz_truth is not None and not quiz.empty:
        scores, _ = score_quiz(quiz, quiz_truth)
        mem = memory_strength(scores, quiz)
        table = table.merge(mem, on="firm_id", how="left")
    ident = _schema(runs, "identification")
    if identifiers and not ident.empty:
        ids = identification_rate(ident, identifiers)
        if not ids.empty:
            wide = ids.pivot_table(index="firm_id", columns="condition", values="id_rate")
            wide.columns = [f"id_rate_{c}" for c in wide.columns]
            table = table.merge(wide.reset_index(), on="firm_id", how="left")

    if anchors is not None and not anchors.empty:
        e7 = val[val["perturbation_type"] == "none"]
        med = e7[e7["condition"].isin(["A", "C"]) & e7["valid"].eq(True)].pivot_table(
            index=KEY, columns="condition", values="value_per_share", aggfunc="median")
        med.columns = [f"v_{c}_e7" for c in med.columns]
        table = _merge(table, med.reset_index())
        table = table.merge(anchors[["firm_id", "p_old", "p_new"]], on="firm_id", how="left")

    dil = firm_dilution(val, n_boot, seed)
    table = _merge(table, dil)
    if not dil.empty:
        basic = dict(zip(dil["firm_id"], dil["N_v1"], strict=False))
        table = _merge(table, stage_shares(classify_runs(val, basic)))

    cells = val.groupby(["firm_id", "condition", "perturbation_type", "perturbation_params",
                         *AGENT_KEYS])["valid"].mean()
    low = (cells < LOW_VALIDITY).groupby(level=KEY).sum().rename("n_low_validity_cells")
    anomaly = val[val["valid"].eq(True)].groupby(KEY)["anomaly_flag"].apply(
        lambda s: float(s.astype("boolean").fillna(False).mean())).rename("anomaly_rate")
    table = _merge(table, pd.concat([low, anomaly], axis=1).reset_index())

    if sample is not None:
        cols = [c for c in ("firm_id", "group", "ksic2", "market_cap", "newsworthiness",
                            "cb_complex") if c in sample]
        table = sample[cols].merge(table, on="firm_id", how="right")
    return table.replace([np.inf, -np.inf], np.nan)


def write_firm_table(table: pd.DataFrame,
                     path: Path = PROJECT_ROOT / "results" / "firm_level.parquet") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(path, index=False)
    return path
