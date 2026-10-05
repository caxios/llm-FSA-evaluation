"""Perturbation size rule (research plan §6.8 v0.2, D3.5; P3 §5.4).

For the response ratio R = dV_obs / dV* to reach standard error s* with n runs per arm,
the theoretical per-share change must satisfy |dV*| >= sigma * sqrt(2 / n) / s*.

Single-item perturbations (cash, non-operating) of X KRW million:
    lower bound  lb = that per-share bound x shares used by the agent
    upper bound  ub = 10% of equity value (and the latest cash balance for cash)
    size         X = min(max(lb, 5% of equity value), ub)
If lb > ub, n is raised in steps of 5 up to n_max; failing that the firm is excluded.
Scale and share perturbations are large by construction; the rule only checks that their
theoretical change clears lb.

Units: v0 and sigma in KRW per share, shares_agent a share count, equity_value and
cash_latest in KRW million. Inputs come from E0 runs, so sizing runs after E0.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel

from src.config import ExperimentsConfig

SINGLE_ITEM = ("cash", "non_operating")
SCALE_LIKE = ("scale", "shares")


class SizeDecision(BaseModel):
    firm_id: str
    perturbation: str
    fraction: float | None = None    # X as a fraction of baseline equity value
    x_mn: float | None = None
    n: int
    status: Literal["ok", "increased_n", "excluded"]
    reason: str = ""


def lower_bound_per_share(sigma: float, n: int, target_se: float) -> float:
    return sigma * math.sqrt(2 / n) / target_se


def _n_steps(cfg: ExperimentsConfig) -> list[int]:
    return list(range(cfg.n_default, cfg.n_max + 1, 5))


def _theory_change(perturbation: str, v0: float, cfg: ExperimentsConfig) -> float:
    """Smallest per-share theoretical change the perturbation produces."""
    if perturbation == "scale":
        return abs(v0) * min(abs(k - 1) for k in cfg.k_grid if k != 1.0)
    return abs(v0) * abs(1 - 1 / cfg.share_multiplier)


def decide_size(firm_id: str, perturbation: str, v0: float, sigma: float,
                shares_agent: float, equity_value: float, cash_latest: float | None,
                cfg: ExperimentsConfig) -> SizeDecision:
    base = {"firm_id": firm_id, "perturbation": perturbation}
    if perturbation in SCALE_LIKE:
        change = _theory_change(perturbation, v0, cfg)
        for n in _n_steps(cfg):
            if change >= lower_bound_per_share(sigma, n, cfg.target_se):
                return SizeDecision(**base, n=n,
                                    status="ok" if n == cfg.n_default else "increased_n")
        return SizeDecision(**base, n=cfg.n_max, status="excluded",
                            reason="theoretical change below precision bound at n_max")
    if perturbation not in SINGLE_ITEM:
        raise ValueError(f"no size rule for '{perturbation}'")

    if equity_value <= 0 or shares_agent <= 0:
        return SizeDecision(**base, n=cfg.n_default, status="excluded",
                            reason="non-positive equity value or share count")
    ub = cfg.size_cap * equity_value
    if perturbation == "cash":
        if cash_latest is None or cash_latest <= 0:
            return SizeDecision(**base, n=cfg.n_default, status="excluded",
                                reason="no cash to distribute")
        ub = min(ub, cash_latest)
    floor = cfg.size_floor * equity_value
    for n in _n_steps(cfg):
        lb = lower_bound_per_share(sigma, n, cfg.target_se) * shares_agent / 1e6
        if lb <= ub:
            x = min(max(lb, floor), ub)
            return SizeDecision(**base, n=n, x_mn=x, fraction=x / equity_value,
                                status="ok" if n == cfg.n_default else "increased_n")
    lb = lower_bound_per_share(sigma, cfg.n_max, cfg.target_se) * shares_agent / 1e6
    return SizeDecision(**base, n=cfg.n_max, status="excluded",
                        reason=f"precision bound {lb:,.0f} exceeds upper bound {ub:,.0f} "
                               f"(KRW mn) at n_max")


def tier_sizes(equity_value: float, tiers: tuple[float, ...] | list[float] = (0.02, 0.05, 0.10)
               ) -> list[float]:
    return [t * equity_value for t in tiers]
