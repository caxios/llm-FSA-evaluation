"""P5: canonical DCF implementation."""

import pytest

from src.agents.valuation_tools import (
    dcf_value,
    diluted_value,
    equity_bridge,
    if_converted,
    per_share,
    recompute_value,
    value_from_inputs,
)
from src.parse.schema import ToolInputs
from tests.p5_helpers import tool_json


def test_dcf_end_of_year_by_hand():
    fcff, w, g = [100, 110, 120, 130, 140], 0.10, 0.02
    ev, tv = dcf_value(fcff, w, g)
    pv = 100 / 1.1 + 110 / 1.1**2 + 120 / 1.1**3 + 130 / 1.1**4 + 140 / 1.1**5
    assert tv == pytest.approx(140 * 1.02 / 0.08)
    assert ev == pytest.approx(pv + tv / 1.1**5)


def test_dcf_mid_year():
    ev, tv = dcf_value([100] * 5, 0.10, 0.0, "mid_year")
    expected = sum(100 / 1.1 ** (t - 0.5) for t in range(1, 6)) + 1000 / 1.1**4.5
    assert ev == pytest.approx(expected)
    assert ev > dcf_value([100] * 5, 0.10, 0.0)[0]
    with pytest.raises(ValueError):
        dcf_value([1] * 5, 0.02, 0.03)
    with pytest.raises(ValueError):
        dcf_value([1] * 5, 0.08, 0.02, "start")


def test_bridge_and_per_share():
    assert equity_bridge(1000, 300, 50) == 750 and equity_bridge(1000, 300, None) == 700
    assert per_share(100_000, 10_000_000) == pytest.approx(10_000)   # KRW mn -> KRW


def test_if_converted_worked_example():
    # research plan E8: E = 100bn, N = 10m, F = 20bn, Pc = 8,000 -> 9,600 vs 10,000
    v_conv, v_debt = if_converted(100_000, 10_000_000, 20_000, 8_000)
    assert v_conv == pytest.approx(9_600) and v_debt == pytest.approx(10_000)
    assert diluted_value(100_000, 10_000_000, 20_000, 2_500_000) == pytest.approx(9_600)
    # out of the money (Pc above E/N): conversion would raise the value -> keep v_debt
    assert min(if_converted(100_000, 10_000_000, 20_000, 12_000)) == pytest.approx(10_000)


def test_value_from_inputs_and_dilution_path():
    t = ToolInputs.model_validate_json(tool_json(apply_dilution=False))
    base = value_from_inputs(t)
    c = base.calculation
    assert c.net_debt == pytest.approx(t.extracted.total_borrowings
                                       - t.extracted.cash_and_equivalents)
    assert base.result.value_per_share == pytest.approx(per_share(c.equity_value,
                                                                  c.shares_used))
    assert recompute_value(base) == pytest.approx(base.result.value_per_share)

    t2 = ToolInputs.model_validate_json(tool_json(apply_dilution=True))
    dil = value_from_inputs(t2)
    face, n_new = t2.extracted.convertible_bonds_outstanding, t2.dilution.convertible_shares
    assert dil.dilution.diluted_shares == pytest.approx(c.shares_used + n_new)
    assert dil.result.value_per_share == pytest.approx(
        diluted_value(c.equity_value, c.shares_used, face, n_new))
    assert dil.result.value_per_share <= base.result.value_per_share
    assert recompute_value(dil) == pytest.approx(dil.result.value_per_share)


def test_dilution_shares_from_conversion_price_and_crosscheck():
    t = ToolInputs.model_validate_json(tool_json(apply_dilution=True))
    t.dilution.convertible_shares = None
    t.ev_ebitda_multiple = 8.0
    out = value_from_inputs(t)
    ex = t.extracted
    assert out.dilution.convertible_shares == pytest.approx(
        ex.convertible_bonds_outstanding * 1e6 / ex.conversion_price)
    ebitda = ex.operating_income + (ex.depreciation_amortization or 0)
    assert out.result.ev_ebitda_crosscheck_per_share == pytest.approx(
        per_share(8 * ebitda - out.calculation.net_debt
                  + out.calculation.non_operating_assets_added, ex.shares_outstanding))
