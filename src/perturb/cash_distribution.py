"""Cash distribution (E3): a special dividend of X paid in the latest fiscal year (P3 §5.2).

| BS cash (and its subtotals)                    | -X |
| BS retained earnings (and equity subtotals)    | -X |
| CF dividends paid (financing, net change, end) | -X economically |
| DPS (latest year)                              | +X / common shares outstanding (D3.2) |
The income statement is unchanged (forgone interest is ignored; documented limitation).
Theory: dV* = -X / N.
"""

from __future__ import annotations

from src.data.account_map import normalize_label
from src.data.package_schema import InputPackage, LineItem
from src.perturb.base import (
    PerturbationNotApplicable,
    PerturbationOutOfRange,
    PerturbMeta,
    add_line,
    apply_delta,
    outflow_sign,
    register,
)

DIVIDEND_LABEL = "배당금의 지급"


def dividend_line(pkg: InputPackage) -> LineItem:
    """The CF dividends-paid line: mapped line, else an unmapped financing line labelled as a
    dividend payment, else a new derived line under financing activities."""
    line = pkg.cf.find("dividends_paid")
    if line is not None:
        return line
    for ln in sorted(pkg.cf.lines, key=lambda x: x.order):
        label = normalize_label(ln.label)
        if ln.parent == "cff" and "배당금" in label and "지급" in label:
            return ln
    return add_line(pkg.cf, DIVIDEND_LABEL, "cff", pkg.years, canonical="dividends_paid")


@register("cash")
def cash_distribution(pkg: InputPackage, x_mn: float) -> PerturbMeta:
    y = pkg.latest_year
    cash = pkg.bs.find("cash")
    if cash is None or cash.values.get(y) is None:
        raise PerturbationNotApplicable("no BS cash line")
    if pkg.bs.find("retained_earnings") is None:
        raise PerturbationNotApplicable("no retained earnings line")
    if x_mn < 0:
        raise PerturbationOutOfRange(f"x_mn={x_mn} < 0")
    if x_mn > cash.values[y]:
        raise PerturbationOutOfRange(f"x_mn={x_mn:.1f} exceeds cash {cash.values[y]:.1f}")
    if pkg.shares.common_outstanding <= 0:
        raise PerturbationNotApplicable("no common shares outstanding")

    apply_delta(pkg, "BS", cash, y, -x_mn)
    apply_delta(pkg, "BS", "retained_earnings", y, -x_mn)
    div = dividend_line(pkg)
    apply_delta(pkg, "CF", div, y, -x_mn, leaf_delta=outflow_sign(pkg) * x_mn)
    dps = pkg.per_share.dps_common
    dps_delta = x_mn * 1e6 / pkg.shares.common_outstanding
    dps[y] = (dps.get(y) or 0.0) + dps_delta
    return PerturbMeta(type="cash", year=y,
                       params={"x_mn": x_mn, "dps_delta": dps_delta,
                               "dividend_line": div.line_id})
