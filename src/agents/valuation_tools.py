"""The single canonical DCF implementation (P5 §5.4).

Used by the tool agent (T), the synthetic agents, and the self-consistency recomputation
in P6. Units: amounts in KRW million, shares as counts, per-share values in KRW.

  FCFF_t = EBIT_t - tax_t + D&A_t - capex_t - dNWC_t
  TV     = FCFF_5 (1 + g) / (wacc - g)
  EV     = sum FCFF_t / (1 + wacc)^t + TV / (1 + wacc)^5          (end of year)
           with exponents t - 0.5 and 4.5 under the mid-year convention
  equity = EV - net_debt + non_operating_assets                     (D5.1)
  value  = equity / shares
Dilution (if-converted, research plan E8): v_conv = (E + F) / (N + dN), v_debt = E / N,
v* = min(v_conv, v_debt), so conversion lowers the value only when it is in the money.
"""

from __future__ import annotations

from src.parse.schema import (
    Calculation,
    Result,
    ToolInputs,
    ValuationOutput,
)

MN = 1e6  # KRW per KRW million


def fcff_from(ebit: float, tax: float, da: float, capex: float, d_nwc: float) -> float:
    return ebit - tax + da - capex - d_nwc


def dcf_value(fcff: list[float], wacc: float, g: float, convention: str = "end_of_year"
              ) -> tuple[float, float]:
    """(enterprise value, terminal value) for yearly FCFF over len(fcff) years."""
    if wacc <= g:
        raise ValueError("wacc must exceed terminal growth")
    shift = 0.5 if convention == "mid_year" else 0.0
    if convention not in ("end_of_year", "mid_year"):
        raise ValueError(f"unknown convention {convention}")
    n = len(fcff)
    pv = sum(f / (1 + wacc) ** (t - shift) for t, f in enumerate(fcff, 1))
    tv = fcff[-1] * (1 + g) / (wacc - g)
    return pv + tv / (1 + wacc) ** (n - shift), tv


def equity_bridge(ev: float, net_debt: float, non_op: float | None) -> float:
    return ev - net_debt + (non_op or 0.0)


def per_share(equity: float, shares: float) -> float:
    """KRW per share from KRW million and a share count."""
    return equity * MN / shares


def if_converted_shares(equity: float, shares: float, face: float, new_shares: float
                        ) -> tuple[float, float]:
    """(v_conv, v_debt) given the face amount (KRW mn) and the shares issued on conversion."""
    return per_share(equity + face, shares + new_shares), per_share(equity, shares)


def if_converted(equity: float, shares: float, face: float, conversion_price: float
                 ) -> tuple[float, float]:
    """(v_conv, v_debt); conversion price in KRW per share."""
    return if_converted_shares(equity, shares, face, face * MN / conversion_price)


def diluted_value(equity: float, shares: float, face: float, new_shares: float) -> float:
    return min(if_converted_shares(equity, shares, face, new_shares))


def value_from_inputs(inputs: ToolInputs, convention: str = "end_of_year") -> ValuationOutput:
    """Complete valuation from the tool agent's inputs; calculation fields are computed."""
    ex, a = inputs.extracted, inputs.assumptions
    fcff = [fcff_from(p.ebit, p.tax, p.depreciation_amortization, p.capex, p.change_in_nwc)
            for p in inputs.projections]
    ev, tv = dcf_value(fcff, a.wacc, a.terminal_growth, convention)
    net_debt = ex.total_borrowings - ex.cash_and_equivalents
    non_op = ex.non_operating_assets or 0.0
    equity = equity_bridge(ev, net_debt, non_op)
    shares = ex.shares_outstanding
    value = per_share(equity, shares)

    dil = inputs.dilution.model_copy()
    if dil.dilution_applied:
        face = ex.convertible_bonds_outstanding
        new_shares = dil.convertible_shares
        if new_shares is None and face and ex.conversion_price:
            new_shares = face * MN / ex.conversion_price
        if face is None and new_shares and ex.conversion_price:
            face = new_shares * ex.conversion_price / MN
        if new_shares:
            value = diluted_value(equity, shares, face or 0.0, new_shares)
            dil.convertible_shares = new_shares
            dil.diluted_shares = shares + new_shares
    crosscheck = None
    if inputs.ev_ebitda_multiple is not None:
        ebitda = ex.operating_income + (ex.depreciation_amortization or 0.0)
        crosscheck = per_share(equity_bridge(inputs.ev_ebitda_multiple * ebitda, net_debt,
                                             non_op), shares)
    return ValuationOutput(
        extracted=ex, assumptions=a,
        calculation=Calculation(fcff=fcff, terminal_value=tv, enterprise_value=ev,
                                net_debt=net_debt, non_operating_assets_added=non_op,
                                equity_value=equity, shares_used=shares,
                                discounting_convention=convention),
        dilution=dil,
        result=Result(value_per_share=value, ev_ebitda_crosscheck_per_share=crosscheck),
        meta=inputs.meta)


def recompute_value(out: ValuationOutput) -> float:
    """Per-share value implied by an output's own reported FCFF, rates and bridge items
    (self-consistency, research plan E1). Uses reported diluted shares when dilution was
    applied."""
    c, a = out.calculation, out.assumptions
    ev, _ = dcf_value(c.fcff, a.wacc, a.terminal_growth, c.discounting_convention)
    equity = equity_bridge(ev, c.net_debt, c.non_operating_assets_added)
    d = out.dilution
    if d.dilution_applied and d.convertible_shares:
        face = out.extracted.convertible_bonds_outstanding or 0.0
        return diluted_value(equity, c.shares_used, face, d.convertible_shares)
    return per_share(equity, c.shares_used)
