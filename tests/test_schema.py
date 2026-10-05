"""P5: output schemas."""

import copy

import pytest
from pydantic import ValidationError

from src.parse.schema import IdentificationOutput, QuizOutput, ToolInputs, ValuationOutput
from tests.p5_helpers import tool_json, valuation_dict

APPENDIX_A = {
    "extracted": {"base_year": 2025, "unit": "KRW_million", "revenue": 1000,
                  "operating_income": 100, "depreciation_amortization": 30, "capex": 40,
                  "change_in_working_capital": 5, "cash_and_equivalents": 200,
                  "total_borrowings": 300, "non_operating_assets": 50,
                  "shares_outstanding": 1_000_000, "convertible_bonds_outstanding": None,
                  "conversion_price": None},
    "assumptions": {"revenue_growth": [0.05] * 5, "operating_margin": [0.1] * 5,
                    "tax_rate": 0.22, "wacc": 0.08, "terminal_growth": 0.02,
                    "assumption_rationale": "근거"},
    "calculation": {"fcff": [70, 72, 75, 78, 80], "terminal_value": 1360,
                    "enterprise_value": 1225, "net_debt": 100,
                    "non_operating_assets_added": 50, "equity_value": 1175,
                    "shares_used": 1_000_000, "discounting_convention": "end_of_year"},
    "dilution": {"dilution_applied": False, "convertible_shares": None,
                 "diluted_shares": None},
    "result": {"value_per_share": 1175, "ev_ebitda_crosscheck_per_share": 1100},
    "meta": {"data_anomaly_flag": False, "data_anomaly_note": "", "sources_used": "재무제표"},
}


def test_appendix_a_example_passes():
    out = ValuationOutput.model_validate(APPENDIX_A)
    assert out.result.value_per_share == 1175 and not out.assumptions.normalized_percent
    assert ValuationOutput.model_validate(valuation_dict())


@pytest.mark.parametrize("path", [("result", "value_per_share"), ("calculation", "fcff"),
                                  ("extracted", "shares_outstanding"), ("meta",)])
def test_missing_fields_fail(path):
    d = copy.deepcopy(APPENDIX_A)
    target = d
    for p in path[:-1]:
        target = target[p]
    del target[path[-1]]
    with pytest.raises(ValidationError):
        ValuationOutput.model_validate(d)


def test_percent_normalization():
    d = copy.deepcopy(APPENDIX_A)
    d["assumptions"].update(wacc=8.5, terminal_growth=2, tax_rate=22,
                            revenue_growth=[5, 4, 3, 3, 3])
    a = ValuationOutput.model_validate(d).assumptions
    assert a.normalized_percent
    assert (a.wacc, a.terminal_growth, a.tax_rate) == pytest.approx((0.085, 0.02, 0.22))
    assert a.revenue_growth == pytest.approx([0.05, 0.04, 0.03, 0.03, 0.03])


@pytest.mark.parametrize("patch", [
    {"wacc": 0.02, "terminal_growth": 0.03},          # wacc <= g
    {"revenue_growth": [0.05] * 4},                  # four years
])
def test_invalid_assumptions(patch):
    d = copy.deepcopy(APPENDIX_A)
    d["assumptions"].update(patch)
    with pytest.raises(ValidationError):
        ValuationOutput.model_validate(d)


def test_bad_convention_and_shares():
    d = copy.deepcopy(APPENDIX_A)
    d["calculation"]["discounting_convention"] = "start"
    with pytest.raises(ValidationError):
        ValuationOutput.model_validate(d)
    d = copy.deepcopy(APPENDIX_A)
    d["calculation"]["shares_used"] = 0
    with pytest.raises(ValidationError):
        ValuationOutput.model_validate(d)


def test_tool_inputs_need_five_years():
    t = ToolInputs.model_validate_json(tool_json())
    assert len(t.projections) == 5
    d = t.model_dump()
    d["projections"] = d["projections"][:3]
    with pytest.raises(ValidationError):
        ToolInputs.model_validate(d)


def test_identification_and_quiz():
    i = IdentificationOutput.model_validate({"guess_name": "모른다", "guess_ticker": None,
                                             "confidence": 30})
    assert i.guess_name is None and i.confidence == pytest.approx(0.3)
    q = QuizOutput.model_validate({"q1_market_cap": "5,000", "q2_revenue": "모른다",
                                   "q3_operating_income": -120, "q4_share_price": 15000,
                                   "q5_main_business": "반도체", "q6_market": "코스닥"})
    assert q.q1_market_cap == 5000 and q.q2_revenue is None and q.q3_operating_income == -120
    assert q.q5_main_business == "반도체"
    with pytest.raises(ValidationError):
        QuizOutput.model_validate({"q1_market_cap": "약 오천억"})
