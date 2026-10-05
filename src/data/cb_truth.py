"""Convertible-bond state as of the evaluation date, and the CB block for packages.

Starting point: the annual report's unredeemed-CB table (fiscal year end). Conversion
prices are updated with refixing disclosures effective after the fiscal year end and on or
before the evaluation date; series that matured before the evaluation date are dropped.
Conversions between the fiscal year end and the evaluation date are not observed (the face
amounts stay at their year-end values; documented limitation).

The disclosure text is generated from the structured data (D2.6), so that the P3
perturbations can edit amounts and prices reliably and V0-V4 share one template.
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd

from src.data.package_schema import CBBlock, CBInstrument

AMOUNT_FACTORS = (1.0, 1e-3, 1e3, 1e-6, 1e6)
SHARE_FACTORS = (1.0, 1e3, 1e6, 1e-3)
MIN_FACE_KRW = 1e7          # outstanding amounts below 10 million KRW are conversion residue
TOLERANCE = 0.05
FLOOR_BAND = (0.65, 1.001)  # 0.7 with rounding slack


def reconcile_units(face: float, price: float, shares: float | None) -> float | None:
    """Return the outstanding face in KRW, choosing the unit factor that makes
    face / price agree with the reported convertible shares (within 5%).

    Unit captions near the table are unreliable (a caption of a neighbouring table can be
    picked up, and share counts are sometimes in thousands), so the table's own numbers
    decide. Returns None when no combination agrees or the result is implausible.
    """
    if not face or not price or price <= 0:
        return None
    if shares is None or (isinstance(shares, float) and math.isnan(shares)) or shares <= 0:
        return None
    # Scaling amount and share units together is ambiguous (thousand KRW with thousand
    # shares looks consistent at factor 1), so keep searching until the face is plausible.
    for g in SHARE_FACTORS:
        for f in AMOUNT_FACTORS:
            implied = face * f / price
            face_krw = face * f
            if (abs(implied / (shares * g) - 1) <= TOLERANCE
                    and MIN_FACE_KRW <= face_krw <= 5e12):
                return face_krw
    return None


def current_instruments(outstanding: pd.DataFrame, refixings: pd.DataFrame,
                        terms: pd.DataFrame, eval_date: date) -> list[CBInstrument]:
    """Outstanding CB series for one firm as of `eval_date`."""
    out: list[CBInstrument] = []
    if outstanding.empty:
        return out
    refix = refixings.copy() if not refixings.empty else pd.DataFrame(
        columns=["series", "price_after", "effective_date"])
    if not refix.empty:
        refix = refix[refix["effective_date"].notna()]
        refix = refix[refix["effective_date"] <= eval_date].sort_values("effective_date")
    term_by_series = ({str(r["series"]): r for r in terms.to_dict("records")}
                      if not terms.empty else {})

    for row in outstanding.to_dict("records"):
        face = row.get("face_outstanding")
        price = row.get("conv_price")
        if not face or (isinstance(face, float) and math.isnan(face)) or face <= 0:
            continue
        maturity = row.get("maturity")
        if maturity is not None and not pd.isna(maturity) and maturity <= eval_date:
            continue
        series = str(row.get("series"))
        if not price or (isinstance(price, float) and math.isnan(price)) or price <= 0:
            continue
        # Units are reconciled at the year-end price, against the year-end share count.
        face = reconcile_units(float(face), float(price), row.get("convertible_shares"))
        if face is None:
            continue
        hits = refix[refix["series"].astype(str) == series] if not refix.empty else refix
        if not hits.empty:
            price = float(hits.iloc[-1]["price_after"])
        term = term_by_series.get(series, {})
        floor = term.get("refix_floor")
        floor = None if floor is None or (isinstance(floor, float) and math.isnan(floor)) \
            else float(floor)
        # The floor (70% of the initial price) comes from the issuance filing; capital changes
        # since then (reverse splits, capital reductions) make it stale. A valid floor lies
        # within [0.7, 1.0] x the current price; outside that band it is treated as unknown.
        if floor is not None and not (FLOOR_BAND[0] * price <= floor <= FLOOR_BAND[1] * price):
            floor = None
        issue = row.get("issue_date")
        out.append(CBInstrument(
            series=series,
            face_outstanding=float(face) / 1e6,
            conversion_price=float(price),
            convertible_shares=float(face) / float(price),
            refix_floor=floor,
            issue_date=None if issue is None or pd.isna(issue) else issue,
            maturity=None if maturity is None or pd.isna(maturity) else maturity,
            complex_terms=None,
        ))
    return out


def _won(v: float) -> str:
    return f"{round(v):,}"


def cb_filing_text(instruments: list[CBInstrument], eval_date: date) -> str:
    lines = [f"[전환사채 미상환 현황 및 주요 발행조건] (기준일: {eval_date.isoformat()})"]
    for ins in instruments:
        lines += [
            "",
            f"제{ins.series}회차 무기명식 무보증 전환사채",
            f"- 발행일: {ins.issue_date.isoformat() if ins.issue_date else '-'}, "
            f"만기일: {ins.maturity.isoformat() if ins.maturity else '-'}",
            f"- 미상환 권면총액: {_won(ins.face_outstanding * 1e6)}원",
            f"- 현재 전환가액: {_won(ins.conversion_price)}원"
            + (f" (시가하락에 따른 전환가액 조정 최저한도: {_won(ins.refix_floor)}원)"
               if ins.refix_floor else ""),
            f"- 전환 시 발행할 주식: 보통주 {_won(ins.convertible_shares)}주",
        ]
    return "\n".join(lines)


def cb_table_text(instruments: list[CBInstrument]) -> str:
    out = ["<미상환 전환사채 발행현황> (단위: 원, 주)",
           "| 회차 | 만기일 | 미상환 권면총액 | 전환가액 | 전환가능주식수 |",
           "|---|---|---|---|---|"]
    for ins in instruments:
        out.append(f"| {ins.series} | {ins.maturity.isoformat() if ins.maturity else '-'} | "
                   f"{_won(ins.face_outstanding * 1e6)} | {_won(ins.conversion_price)} | "
                   f"{_won(ins.convertible_shares)} |")
    total_face = sum(i.face_outstanding for i in instruments) * 1e6
    total_shares = sum(i.convertible_shares for i in instruments)
    out.append(f"| 합계 | - | {_won(total_face)} | - | {_won(total_shares)} |")
    return "\n".join(out)


def build_cb_block(instruments: list[CBInstrument], eval_date: date) -> CBBlock | None:
    if not instruments:
        return None
    return CBBlock(instruments=instruments, filing_text=cb_filing_text(instruments, eval_date),
                   outstanding_table_text=cb_table_text(instruments))
