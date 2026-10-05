"""Accounting identity checks for input packages (P2 §5.4, shared with P3).

Checks per fiscal year (values in KRW million):
  bs_balance        total_assets = total_liabilities + total_equity
  bs_le_total       total_liabilities_and_equity = total_assets            (if reported)
  bs_assets_split   current_assets + non_current_assets (+ held-for-sale assets reported
                    outside both) = total_assets
  bs_liab_split     same for liabilities
  bs_equity_split   total_equity = equity_owners + non_controlling_interest (if both reported)
  cf_cash_roll      ending_cash = beginning_cash + net_change (+ fx if net change is pre-fx)
  cf_continuity     beginning_cash[y] = ending_cash[y-1]
  cf_bs_cash        ending_cash = BS cash                       (soft: warning only)
The EPS relation is checked on perturbation deltas in P3, not on raw packages.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.data.package_schema import InputPackage, Statement

SOFT_CHECKS = {"cf_bs_cash"}


@dataclass(frozen=True)
class IdentityViolation:
    check: str
    year: int
    lhs: float
    rhs: float

    @property
    def gap(self) -> float:
        return self.lhs - self.rhs


def _v(st: Statement, canonical: str, year: int) -> float | None:
    line = st.find(canonical)
    if line is None:
        return None
    return line.values.get(year)


def _close(a: float, b: float, rel_tol: float, abs_tol: float) -> bool:
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))


def _extras(st: Statement, year: int, keyword: str | None = None) -> float:
    """Sum of top-level, non-canonical monetary lines (deduplicated by label and values).

    Examples: '매각예정자산' outside current/non-current assets; cash-flow adjustments such
    as '해외사업장환산손익' or hyperinflation effects next to the FX line.
    """
    seen, total = set(), 0.0
    for ln in st.lines:
        if ln.parent is not None or ln.canonical is not None or ln.kind != "monetary":
            continue
        if keyword and keyword not in ln.label:
            continue
        key = (ln.label.replace(" ", ""), tuple(sorted(ln.values.items())))
        if key in seen:
            continue
        seen.add(key)
        total += ln.values.get(year) or 0.0
    return total


def cash_roll_ok(pkg: InputPackage, year: int, rel_tol: float = 1e-6,
                 abs_tol: float = 1.0) -> tuple[bool | None, bool | None]:
    """(passes, net_change_includes_fx) for the cash roll-forward of one year.

    Accepted forms: end = beg + net | beg + pre + fx | beg + net + fx, each optionally plus
    other top-level adjustment lines (FX translation, hyperinflation).
    """
    cf = pkg.cf
    beg, end = _v(cf, "beginning_cash", year), _v(cf, "ending_cash", year)
    if beg is None or end is None:
        return None, None
    fx = _v(cf, "fx_effect_on_cash", year) or 0.0
    net = _v(cf, "net_change_in_cash", year)
    pre = _v(cf, "net_change_before_fx", year)
    if net is None and pre is None:
        parts = [_v(cf, c, year) for c in ("cfo", "cfi", "cff")]
        if any(p is None for p in parts):
            return False, None
        pre = sum(parts)  # type: ignore[arg-type]
    extra = _extras(cf, year)
    for add in (0.0, extra):
        if net is not None and _close(end, beg + net + add, rel_tol, abs_tol):
            return True, True
        if pre is not None and _close(end, beg + pre + fx + add, rel_tol, abs_tol):
            return True, False
        if net is not None and _close(end, beg + net + fx + add, rel_tol, abs_tol):
            return True, False
    return False, None


def _split_ok(parts: tuple[float | None, ...], total: float | None, extra: float,
              rel_tol: float, abs_tol: float) -> bool:
    if total is None or any(p is None for p in parts):
        return True
    s = sum(parts)  # type: ignore[arg-type]
    return _close(s, total, rel_tol, abs_tol) or _close(s + extra, total, rel_tol, abs_tol)


def check_identities(pkg: InputPackage, rel_tol: float = 1e-6, abs_tol: float = 1.0,
                     include_soft: bool = False) -> list[IdentityViolation]:
    out: list[IdentityViolation] = []
    bs, cf = pkg.bs, pkg.cf

    def check(name: str, year: int, lhs: float | None, rhs: float | None) -> None:
        if lhs is None or rhs is None:
            return
        if not _close(lhs, rhs, rel_tol, abs_tol):
            out.append(IdentityViolation(name, year, lhs, rhs))

    def total(*vals: float | None) -> float | None:
        return None if any(v is None for v in vals) else sum(vals)  # type: ignore[arg-type]

    for y in pkg.years:
        ta = _v(bs, "total_assets", y)
        tl = _v(bs, "total_liabilities", y)
        te = _v(bs, "total_equity", y)
        check("bs_balance", y, ta, total(tl, te))
        check("bs_le_total", y, _v(bs, "total_liabilities_and_equity", y), ta)
        ca, nca = _v(bs, "current_assets", y), _v(bs, "non_current_assets", y)
        if not _split_ok((ca, nca), ta, _extras(bs, y, "자산"), rel_tol, abs_tol):
            out.append(IdentityViolation("bs_assets_split", y, total(ca, nca) or 0.0, ta or 0.0))
        cl, ncl = _v(bs, "current_liabilities", y), _v(bs, "non_current_liabilities", y)
        if not _split_ok((cl, ncl), tl, _extras(bs, y, "부채"), rel_tol, abs_tol):
            out.append(IdentityViolation("bs_liab_split", y, total(cl, ncl) or 0.0, tl or 0.0))
        owners, nci = _v(bs, "equity_owners", y), _v(bs, "non_controlling_interest", y)
        if owners is not None and nci is not None:
            check("bs_equity_split", y, te, owners + nci)

        ok, _ = cash_roll_ok(pkg, y, rel_tol, abs_tol)
        if ok is False:
            out.append(IdentityViolation("cf_cash_roll", y, _v(cf, "ending_cash", y) or 0.0,
                                         _v(cf, "beginning_cash", y) or 0.0))
        if include_soft:
            check("cf_bs_cash", y, _v(cf, "ending_cash", y), _v(bs, "cash", y))

    for prev, y in zip(pkg.years, pkg.years[1:], strict=False):
        check("cf_continuity", y, _v(cf, "beginning_cash", y), _v(cf, "ending_cash", prev))
    return out
