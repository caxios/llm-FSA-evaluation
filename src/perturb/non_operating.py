"""Non-operating asset perturbation (E3): an FVOCI financial asset worth X more (D2).

Latest year: the FVOCI asset line +X (created under non-current assets if absent) and the
accumulated OCI reserve +X (other equity, created if neither is reported), with all
subtotals. A fair-value gain on an FVOCI asset has no P&L and no cash effect, so the income
statement and cash-flow statement stay unchanged (the OCI line of the current year is not
edited; documented limitation). Theory: dV* = +X / N.
"""

from __future__ import annotations

from src.data.package_schema import InputPackage, LineItem
from src.perturb.base import (
    PerturbationOutOfRange,
    PerturbMeta,
    add_line,
    apply_delta,
    register,
    update_note,
)

FVOCI_LABEL = "기타포괄손익-공정가치 측정 금융자산"
OCI_LABEL = "기타포괄손익누계액"


def fvoci_line(pkg: InputPackage) -> LineItem:
    lines = pkg.bs.by_category("nonop:fvoci")
    for line in lines:
        if line.parent == "non_current_assets":
            return line
    if lines:
        return lines[0]
    return add_line(pkg.bs, FVOCI_LABEL, "non_current_assets", pkg.years,
                    category="nonop:fvoci")


def oci_line(pkg: InputPackage) -> LineItem:
    for canonical in ("oci_reserve", "other_equity"):
        line = pkg.bs.find(canonical)
        if line is not None:
            return line
    parent = "equity_owners" if pkg.bs.find("equity_owners") else "total_equity"
    return add_line(pkg.bs, OCI_LABEL, parent, pkg.years, canonical="oci_reserve")


@register("non_operating")
def non_operating(pkg: InputPackage, x_mn: float) -> PerturbMeta:
    if x_mn < 0:
        raise PerturbationOutOfRange(f"x_mn={x_mn} < 0")
    y = pkg.latest_year
    asset = fvoci_line(pkg)
    equity = oci_line(pkg)
    apply_delta(pkg, "BS", asset, y, x_mn)
    apply_delta(pkg, "BS", equity, y, x_mn)
    update_note(pkg.notes.non_operating_assets, asset, y)
    return PerturbMeta(type="non_operating", year=y,
                       params={"x_mn": x_mn, "asset_line": asset.line_id,
                               "equity_line": equity.line_id})
