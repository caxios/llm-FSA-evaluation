"""Share-count perturbation (E3): all share counts x m, as if an m-for-1 split (D3.1).

Paid-in capital is unchanged; EPS and DPS are divided by m in every year, so V* = V0 / m.
A CB block, when present, gets the standard anti-dilution adjustment: conversion price and
refixing floor / m, convertible shares x m (the dilution ratio is unchanged).
"""

from __future__ import annotations

from src.data.package_schema import InputPackage
from src.perturb.base import PerturbMeta, register
from src.perturb.cb import regenerate


@register("shares")
def shares(pkg: InputPackage, m: float) -> PerturbMeta:
    if m <= 0:
        raise ValueError("m must be positive")
    s = pkg.shares
    s.common_issued *= m
    s.common_treasury *= m
    s.preferred_issued *= m
    s.preferred_treasury *= m
    for values in (pkg.per_share.eps, pkg.per_share.dps_common):
        for y, v in values.items():
            if v is not None:
                values[y] = v / m
    for line in pkg.is_.lines:
        if line.kind == "per_share":
            for y, v in line.values.items():
                if v is not None:
                    line.values[y] = v / m
    if pkg.cb is not None:
        for ins in pkg.cb.instruments:
            ins.conversion_price /= m
            ins.convertible_shares *= m
            if ins.refix_floor is not None:
                ins.refix_floor /= m
        regenerate(pkg)
    return PerturbMeta(type="shares", params={"m": m})
