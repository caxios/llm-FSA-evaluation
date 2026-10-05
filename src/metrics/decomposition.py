"""Information-condition decomposition (E4).

Per firm: total attenuation = bA - bC = industry (bA - bB) + name (bB - bD) + memory
(bD - bC = E_i). Bootstrap SEs re-estimate all four betas per replicate with runs
resampled within each condition x k cell (D6.4).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.metrics.bootstrap import DEFAULT_REPS
from src.metrics.cells import AGENT_KEYS
from src.metrics.elasticity import beta_from, scale_runs

CONDS = ("A", "B", "D", "C")


def components(b: dict[str, float]) -> dict[str, float]:
    total = b["A"] - b["C"]
    out = {"total_atten": total, "industry_eff": b["A"] - b["B"], "name_eff": b["B"] - b["D"],
           "memory_eff": b["D"] - b["C"]}
    for k in ("industry_eff", "name_eff", "memory_eff"):
        out[f"{k}_share"] = out[k] / total if total else np.nan
    return out


def decompose(betas: pd.DataFrame) -> pd.DataFrame:
    """Point decomposition from `firm_elasticity` output (one beta per firm x condition)."""
    rows = []
    for key, g in betas.groupby(["firm_id", *AGENT_KEYS], sort=True):
        b = dict(zip(g["condition"], g["beta"], strict=True))
        if not all(c in b for c in CONDS):
            continue
        rows.append(dict(zip(["firm_id", *AGENT_KEYS], key, strict=True)) | components(b))
    return pd.DataFrame(rows)


def bootstrap_decomposition(runs: pd.DataFrame, reps: int = DEFAULT_REPS, seed: int = 0
                            ) -> pd.DataFrame:
    """Bootstrap SEs of the components per firm (positive values only, as in beta)."""
    r = scale_runs(runs)
    r = r[r["valid"].eq(True) & (r["value_per_share"] > 0)]
    rows = []
    for key, g in r.groupby(["firm_id", *AGENT_KEYS], sort=True):
        cells = {}
        for (cond, k), c in g.groupby(["condition", "k"]):
            cells[(cond, k)] = np.log(c["value_per_share"].to_numpy(float))
        if not all(any(cc == c for cc, _ in cells) for c in CONDS):
            continue
        rng = np.random.default_rng(seed)
        draws = {n: [] for n in ("total_atten", "industry_eff", "name_eff", "memory_eff")}
        for _ in range(reps):
            b = {}
            for cond in CONDS:
                ks, vs = [], []
                for (cc, k), v in cells.items():
                    if cc == cond:
                        s = v[rng.integers(0, len(v), len(v))]
                        ks.append(np.full(len(s), np.log(k)))
                        vs.append(s)
                b[cond] = beta_from(np.concatenate(ks), np.concatenate(vs))
            comp = components(b)
            for n in draws:
                draws[n].append(comp[n])
        rows.append(dict(zip(["firm_id", *AGENT_KEYS], key, strict=True))
                    | {f"{n}_se": float(np.nanstd(v, ddof=1)) for n, v in draws.items()})
    return pd.DataFrame(rows)
