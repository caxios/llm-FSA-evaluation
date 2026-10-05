"""CB variants V0-V4 for E8 (P3 §5.2).

| V0 | CB block as built (no change)                                                |
| V1 | CB information removed (the BS convertible-bond line stays)                  |
| V2 | outstanding face x 2, financed by cash: BS CB line +dF, BS cash +dF, CF       |
|    | proceeds from convertible bonds +dF (net debt and equity unchanged, D3)        |
| V3 | conversion price -> max(refix floor, 0.5 Pc), rounded up to the won (D3.3)    |
| V4 | placebo filing appended: a fully redeemed earlier CB, or an unrelated notice  |

The CB text is generated from the structured instruments (D2.6), so edited variants are
regenerated from the edited instruments with the same template (D3.6); `text_numbers` then
verifies that the old amounts and prices no longer appear and the new ones do.
"""

from __future__ import annotations

import math
import zlib
from datetime import date, timedelta
from pathlib import Path

from src.data.cb_truth import cb_filing_text, cb_table_text
from src.data.package_schema import CBInstrument, InputPackage, LineItem
from src.perturb.base import (
    Param,
    PerturbationInconsistent,
    PerturbationNotApplicable,
    PerturbMeta,
    add_line,
    apply_delta,
    register,
    update_note,
)
from src.perturb.text_numbers import find_amounts, find_prices

TEMPLATES = Path(__file__).parent / "templates"
CB_LABEL = "전환사채"
CB_PROCEEDS_LABEL = "전환사채의 발행"
FLOOR_FALLBACK = 0.7     # D3.3: undisclosed floor = 70% of the conversion price
V3_FACTOR = 0.5
PLACEBOS = ("redeemed_cb", "irrelevant")
ADDRESSES = [
    "경기도 성남시 분당구 판교로 255", "서울특별시 금천구 가산디지털1로 168",
    "경기도 화성시 동탄첨단산업1로 27", "인천광역시 연수구 송도과학로 32",
    "서울특별시 강남구 테헤란로 427", "경기도 안양시 동안구 시민대로 161",
    "대전광역시 유성구 테크노2로 187", "경기도 용인시 기흥구 흥덕중앙로 120",
]


def _require_cb(pkg: InputPackage) -> None:
    if pkg.cb is None or not pkg.cb.instruments:
        raise PerturbationNotApplicable("package has no CB block")


def regenerate(pkg: InputPackage) -> None:
    assert pkg.cb is not None
    pkg.cb.filing_text = cb_filing_text(pkg.cb.instruments, pkg.meta.eval_date)
    pkg.cb.outstanding_table_text = cb_table_text(pkg.cb.instruments)


def cb_text(pkg: InputPackage) -> str:
    assert pkg.cb is not None
    return f"{pkg.cb.filing_text}\n\n{pkg.cb.outstanding_table_text}"


def _instrument_meta(ins: CBInstrument, **extra: Param) -> dict[str, Param]:
    return {"series": ins.series, "face_mn": ins.face_outstanding,
            "conversion_price": ins.conversion_price,
            "convertible_shares": ins.convertible_shares,
            "refix_floor": ins.refix_floor, **extra}


def _totals(pkg: InputPackage) -> dict[str, Param]:
    assert pkg.cb is not None
    ins = pkg.cb.instruments
    return {"face_mn": sum(i.face_outstanding for i in ins),
            "convertible_shares": sum(i.convertible_shares for i in ins),
            "n_instruments": float(len(ins))}


def _verify(old_text: str, new_text: str, old_values: list[float], new_values: list[float],
            prices: bool) -> None:
    """Every changed amount (or price) is gone from the text and its new value is present."""
    find = find_prices if prices else find_amounts
    for old, new in zip(old_values, new_values, strict=True):
        if abs(old - new) < 0.5:
            continue
        if not find(old_text, old):
            raise PerturbationInconsistent(f"CB text: original value {old:,.0f} not found")
        if not find(new_text, new):
            raise PerturbationInconsistent(f"CB text: new value {new:,.0f} not rendered")
        if find(new_text, old) and not any(abs(old - v) < 0.5 for v in new_values):
            raise PerturbationInconsistent(f"CB text: value {old:,.0f} left unchanged")


@register("cb_v0")
def cb_v0(pkg: InputPackage) -> PerturbMeta:
    _require_cb(pkg)
    assert pkg.cb is not None
    return PerturbMeta(type="cb_v0", params=_totals(pkg),
                       instruments=[_instrument_meta(i) for i in pkg.cb.instruments])


@register("cb_v1")
def cb_v1(pkg: InputPackage) -> PerturbMeta:
    """The block is dropped entirely, so the prompt's additional-filings section reads
    '없음' rather than showing an empty disclosure."""
    _require_cb(pkg)
    pkg.cb = None
    return PerturbMeta(type="cb_v1")


def _cb_balance_line(pkg: InputPackage) -> LineItem:
    lines = pkg.bs.by_category("debt:convertible")
    y = pkg.latest_year
    if lines:
        return max(lines, key=lambda ln: abs(ln.values.get(y) or 0.0))
    return add_line(pkg.bs, CB_LABEL, "non_current_liabilities", pkg.years,
                    category="debt:convertible")


def _cb_proceeds_line(pkg: InputPackage) -> LineItem:
    line = pkg.cf.find("proceeds_from_convertible_bonds")
    if line is not None:
        return line
    return add_line(pkg.cf, CB_PROCEEDS_LABEL, "cff", pkg.years,
                    canonical="proceeds_from_convertible_bonds")


@register("cb_v2")
def cb_v2(pkg: InputPackage) -> PerturbMeta:
    _require_cb(pkg)
    assert pkg.cb is not None
    y = pkg.latest_year
    if pkg.bs.find("cash") is None:
        raise PerturbationNotApplicable("no BS cash line")
    old_text = cb_text(pkg)
    old_faces = [i.face_outstanding * 1e6 for i in pkg.cb.instruments]
    delta = sum(i.face_outstanding for i in pkg.cb.instruments)
    for ins in pkg.cb.instruments:
        ins.face_outstanding *= 2
        ins.convertible_shares *= 2
    regenerate(pkg)
    _verify(old_text, cb_text(pkg), old_faces,
            [i.face_outstanding * 1e6 for i in pkg.cb.instruments], prices=False)

    bal = _cb_balance_line(pkg)
    apply_delta(pkg, "BS", bal, y, delta)
    apply_delta(pkg, "BS", "cash", y, delta)
    proceeds = _cb_proceeds_line(pkg)
    apply_delta(pkg, "CF", proceeds, y, delta)  # inflows are positive under both conventions
    update_note(pkg.notes.borrowings, bal, y)
    return PerturbMeta(type="cb_v2", year=y,
                       params={**_totals(pkg), "delta_face_mn": delta,
                               "bs_line": bal.line_id, "cf_line": proceeds.line_id},
                       instruments=[_instrument_meta(i) for i in pkg.cb.instruments])


def v3_price(ins: CBInstrument) -> tuple[float, bool]:
    """(new conversion price, floor_assumed) per D3.3, rounded up to the won.

    The package carries the current conversion price only, so an undisclosed floor is
    approximated as 70% of the current price (equal to 70% of the initial price unless the
    series was already refixed downwards)."""
    assumed = ins.refix_floor is None
    floor = ins.conversion_price * FLOOR_FALLBACK if assumed else float(ins.refix_floor)
    return float(math.ceil(max(floor, V3_FACTOR * ins.conversion_price) - 1e-9)), assumed


@register("cb_v3")
def cb_v3(pkg: InputPackage) -> PerturbMeta:
    _require_cb(pkg)
    assert pkg.cb is not None
    old_text = cb_text(pkg)
    old_prices = [i.conversion_price for i in pkg.cb.instruments]
    details = []
    for ins in pkg.cb.instruments:
        new, assumed = v3_price(ins)
        flag = "yes" if assumed else "no"
        if new >= ins.conversion_price:
            details.append(_instrument_meta(ins, changed="no", reason="at_floor",
                                            floor_assumed=flag, ratio=1.0))
            continue
        ratio = new / ins.conversion_price
        ins.conversion_price = new
        ins.convertible_shares = ins.face_outstanding * 1e6 / new
        details.append(_instrument_meta(ins, changed="yes", ratio=ratio, floor_assumed=flag))
    if not any(d["changed"] == "yes" for d in details):
        raise PerturbationNotApplicable("every CB series is already at its refixing floor")
    regenerate(pkg)
    _verify(old_text, cb_text(pkg), old_prices,
            [i.conversion_price for i in pkg.cb.instruments], prices=True)
    return PerturbMeta(type="cb_v3", params=_totals(pkg), instruments=details)


def _shift_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 February
        return d.replace(year=d.year + years, day=28)


def placebo_text(pkg: InputPackage, placebo: str) -> str:
    """Placebo filing filled deterministically from the firm's own data."""
    assert pkg.cb is not None
    ins = pkg.cb.instruments
    if placebo == "redeemed_cb":
        numeric = [int(i.series) for i in ins if i.series.isdigit()]
        series = str(max(min(numeric) - 1, 1)) if numeric else "1"
        dates = [i.issue_date for i in ins if i.issue_date]
        issue = _shift_years(min(dates) if dates else pkg.meta.eval_date, -3)
        face_mn = sorted(i.face_outstanding for i in ins)[len(ins) // 2]
        price = sorted(i.conversion_price for i in ins)[len(ins) // 2]
        return (TEMPLATES / "redeemed_cb.txt").read_text(encoding="utf-8").format(
            series=series, issue_date=issue.isoformat(),
            maturity=_shift_years(issue, 3).isoformat(), face=f"{round(face_mn * 1e6):,}",
            price=f"{round(price):,}", redeem_date=_shift_years(issue, 2).isoformat()
        ).rstrip()
    if placebo == "irrelevant":
        seed = zlib.crc32(pkg.meta.firm_id.encode())
        old = seed % len(ADDRESSES)
        new = (old + 1 + (seed >> 8) % (len(ADDRESSES) - 1)) % len(ADDRESSES)
        ev = pkg.meta.eval_date
        return (TEMPLATES / "irrelevant.txt").read_text(encoding="utf-8").format(
            old_address=ADDRESSES[old], new_address=ADDRESSES[new],
            move_date=(ev - timedelta(days=7)).isoformat(),
            board_date=(ev - timedelta(days=21)).isoformat()).rstrip()
    raise ValueError(f"unknown placebo '{placebo}' (expected one of {PLACEBOS})")


@register("cb_v4")
def cb_v4(pkg: InputPackage, placebo: str) -> PerturbMeta:
    """The redeemed-CB placebo is always generated from the template: the package does not
    carry the firm's redeemed series, and a template keeps the placebos comparable."""
    _require_cb(pkg)
    assert pkg.cb is not None
    pkg.cb.filing_text = f"{pkg.cb.filing_text}\n\n{placebo_text(pkg, placebo)}"
    return PerturbMeta(type="cb_v4", params={**_totals(pkg), "placebo": placebo},
                       instruments=[_instrument_meta(i) for i in pkg.cb.instruments])
