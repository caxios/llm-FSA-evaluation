"""Bootstrap helpers (D6.4): resample runs within each cell, fixed seed."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

DEFAULT_REPS = 1000


def resample(rng: np.random.Generator, x: np.ndarray, reps: int) -> np.ndarray:
    """reps x len(x) matrix of within-cell resamples."""
    return x[rng.integers(0, len(x), size=(reps, len(x)))]


def median_diff_ci(base: np.ndarray, pert: np.ndarray, reps: int = DEFAULT_REPS,
                   seed: int = 0, alpha: float = 0.05) -> tuple[float, float, np.ndarray]:
    """Percentile CI of median(pert) - median(base); returns (lo, hi, replicates)."""
    rng = np.random.default_rng(seed)
    diffs = (np.median(resample(rng, pert, reps), axis=1)
             - np.median(resample(rng, base, reps), axis=1))
    lo, hi = np.quantile(diffs, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi), diffs


def cell_bootstrap(cells: Sequence[np.ndarray], stat: Callable[[list[np.ndarray]], float],
                   reps: int = DEFAULT_REPS, seed: int = 0) -> np.ndarray:
    """Replicates of `stat` with every cell resampled independently."""
    rng = np.random.default_rng(seed)
    out = np.empty(reps)
    for b in range(reps):
        out[b] = stat([c[rng.integers(0, len(c), len(c))] for c in cells])
    return out
