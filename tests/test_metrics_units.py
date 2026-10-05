"""P6: metric functions on hand-made run tables."""

import json
import math

import numpy as np
import pandas as pd
import pytest

from src.conditions.identifiers import FirmIdentifiers
from src.metrics.baseline import baseline
from src.metrics.bootstrap import cell_bootstrap, median_diff_ci
from src.metrics.decomposition import components, decompose
from src.metrics.dilution import (
    cb_theory,
    dose_response,
    firm_dilution,
    placebo_shift,
    theoretical_diluted_value,
)
from src.metrics.elasticity import firm_elasticity, ols_hc3
from src.metrics.failure_modes import classify, stage_shares
from src.metrics.identification import identification_rate, is_correct
from src.metrics.memory_quiz import market_of, memory_strength, score_quiz
from src.metrics.response import min_perturbation, response_ratio, theoretical_delta
from src.metrics.self_consistency import epsilon, firm_epsilon, recompute, run_epsilons
from src.parse.schema import ValuationOutput
from tests.p5_helpers import valuation_dict


def row(firm="F1", cond="C", ptype="none", params=None, v=100.0, valid=True, rep=0,
        out=None, schema="valuation", shares=1e6, equity=None, agent="P", model="m"):
    return {"job_id": f"{firm}|{cond}|{ptype}|{json.dumps(params or {})}|{rep}",
            "firm_id": firm, "condition": cond, "perturbation_type": ptype,
            "perturbation_params": json.dumps(params or {}, sort_keys=True),
            "schema_name": schema, "agent_structure": agent, "model_key": model,
            "rep": rep, "valid": valid, "value_per_share": v, "shares_used": shares,
            "equity_value": equity if equity is not None else (v * shares / 1e6 if v else None),
            "anomaly_flag": False,
            "output_json": json.dumps(out, ensure_ascii=False) if out else None}


# ---------------------------------------------------------------- baseline


def test_baseline():
    runs = pd.DataFrame([row(v=v, rep=i) for i, v in enumerate([90, 100, 110])]
                        + [row(v=None, valid=False, rep=3), row(ptype="scale",
                                                                params={"k": 2}, v=1)])
    b = baseline(runs).iloc[0]
    assert (b.v0, b.n_valid, b.n_total, b.compliance) == (100, 3, 4, 0.75)
    assert b.sigma == pytest.approx(10) and b.mad == 10 and b.shares_agent == 1e6


# ---------------------------------------------------------------- elasticity


def scale_table(beta, cond="C", firm="F1", noise=0.0, reps=3, curve=0.0, v0=1000.0):
    rng = np.random.default_rng(1)
    rows = []
    for k in (0.5, 0.8, 1.0, 1.25, 2.0):
        for r in range(reps):
            lv = math.log(v0) + beta * math.log(k) + curve * math.log(k) ** 2
            v = math.exp(lv + rng.normal(0, noise))
            rows.append(row(firm, cond, "none" if k == 1 else "scale",
                            None if k == 1 else {"k": k}, v, rep=r))
    return rows


def test_elasticity_exact_and_curvature():
    e = firm_elasticity(pd.DataFrame(scale_table(0.7))).iloc[0]
    assert e.beta == pytest.approx(0.7) and e.se_hc3 == pytest.approx(0, abs=1e-9)
    assert e.beta_median_based == pytest.approx(0.7) and e.n_used == 15
    curved = firm_elasticity(pd.DataFrame(scale_table(1.0, noise=0.01, curve=0.5))).iloc[0]
    assert curved.beta_quad == pytest.approx(0.5, abs=0.05) and curved.p_quad < 0.01


def test_elasticity_drops_nonpositive():
    rows = scale_table(1.0)
    rows[0]["value_per_share"] = -5.0
    e = firm_elasticity(pd.DataFrame(rows)).iloc[0]
    assert e.n_nonpositive_dropped == 1 and e.n_used == 14 and e.beta == pytest.approx(1.0)
    one_k = firm_elasticity(pd.DataFrame([row(v=10), row(v=11, rep=1)])).iloc[0]
    assert math.isnan(one_k.beta)


def test_ols_hc3_matches_statsmodels():
    import statsmodels.api as sm

    rng = np.random.default_rng(0)
    x = rng.normal(size=50)
    y = 1 + 2 * x + rng.normal(size=50) * (1 + abs(x))
    X = sm.add_constant(x)
    b, se = ols_hc3(X, y)
    ref = sm.OLS(y, X).fit(cov_type="HC3")
    assert b == pytest.approx(ref.params) and se == pytest.approx(ref.bse)


# ---------------------------------------------------------------- response


def test_theoretical_deltas():
    assert theoretical_delta("cash", {"x_mn": 100}, 5000, 1e6) == -100
    assert theoretical_delta("non_operating", {"x_mn": 100}, 5000, 1e6) == 100
    assert theoretical_delta("shares", {"m": 2}, 5000, 1e6) == -2500
    assert theoretical_delta("scale", {"k": 1.5}, 5000, 1e6) == 2500
    assert theoretical_delta("none", {}, 1, 1) == 0
    with pytest.raises(ValueError):
        theoretical_delta("cb_v2", {}, 1, 1)


def test_response_ratio_and_bootstrap_determinism():
    base, pert = np.array([100, 101, 99, 100.0]), np.array([90, 91, 89, 90.0])
    r = response_ratio(base, pert, -10.0, n_boot=500, seed=3)
    assert r["R"] == pytest.approx(1.0) and r["ci_lo"] <= 1 <= r["ci_hi"]
    assert r == response_ratio(base, pert, -10.0, n_boot=500, seed=3)
    assert math.isnan(response_ratio(base, pert, 0.0)["R"])
    assert math.isnan(response_ratio(np.array([]), pert, 1.0)["R"])
    lo, hi, reps = median_diff_ci(base, pert, 100, 0)
    assert len(reps) == 100 and lo <= hi
    assert cell_bootstrap([base, pert], lambda c: c[0].mean(), reps=5).shape == (5,)
    assert min_perturbation(1000, 10) == pytest.approx(1000 * math.sqrt(0.2) / 0.1)


# ---------------------------------------------------------------- self-consistency


def test_epsilon_consistent_and_injected_errors():
    d = valuation_dict("large_pref")
    out = ValuationOutput.model_validate(d)
    e = epsilon(out)
    assert e["eps"] == pytest.approx(0, abs=1e-12) and e["ev_gap"] == pytest.approx(0, abs=1e-12)
    assert e["eps_alt"] > 0
    off = ValuationOutput.model_validate(d)
    off.result.value_per_share *= 1.1
    assert epsilon(off)["eps"] == pytest.approx(0.1) and epsilon(off)["vps_gap"] > 0.09
    bridge = ValuationOutput.model_validate(d)
    bridge.calculation.equity_value += 1000
    g = epsilon(bridge)
    assert g["equity_gap"] > 0 and g["ev_gap"] == pytest.approx(0, abs=1e-12)
    assert recompute(out).vps_re == pytest.approx(out.result.value_per_share)


def test_run_and_firm_epsilon():
    d = valuation_dict("large_pref")
    runs = pd.DataFrame([row(out=d, rep=0), row(out=d, rep=1), row(valid=False, rep=2)])
    eps = run_epsilons(runs)
    assert len(eps) == 2 and eps["eps"].max() < 1e-9
    f = firm_epsilon(eps).iloc[0]
    assert f.share_eps_gt_5pct == 0 and f.n_eps == 2


# ---------------------------------------------------------------- decomposition


def test_decomposition_identity():
    c = components({"A": 1.0, "B": 0.95, "D": 0.8, "C": 0.5})
    assert c["total_atten"] == pytest.approx(c["industry_eff"] + c["name_eff"] + c["memory_eff"])
    assert c["memory_eff"] == pytest.approx(0.3) and c["name_eff_share"] == pytest.approx(0.3)
    betas = pd.DataFrame([{"firm_id": "F1", "condition": k, "agent_structure": "P",
                           "model_key": "m", "beta": v}
                          for k, v in {"A": 1, "B": 1, "D": 0.8, "C": 0.5}.items()])
    d = decompose(betas).iloc[0]
    assert d.memory_eff == pytest.approx(0.3) and d.industry_eff == 0
    assert decompose(betas[betas.condition != "B"]).empty


# ---------------------------------------------------------------- quiz / identification


TRUTH = pd.DataFrame([{"firm_id": "F1", "market": "KOSDAQ", "price": 10_000.0,
                       "market_cap_krw": 5e11, "revenue_prev_mn": 200_000.0,
                       "op_income_prev_mn": -10_000.0, "main_business": "반도체|메모리"}])


def quiz(q, rep=0):
    return row(schema="quiz", out=q, rep=rep)


def test_quiz_scoring():
    responses = pd.DataFrame([
        quiz({"q1_market_cap": 5500, "q2_revenue": 2000, "q3_operating_income": -110,
              "q4_share_price": 11_000, "q5_main_business": "메모리 반도체",
              "q6_market": "코스닥"}),
        quiz({"q1_market_cap": None, "q2_revenue": 3000, "q3_operating_income": 100,
              "q4_share_price": 9_000, "q5_main_business": "자동차 부품",
              "q6_market": "유가증권시장"}, rep=1)])
    scores, review = score_quiz(responses, TRUTH)
    s = scores.set_index(["rep", "item"])["score"]
    assert s[(0, "q1_market_cap")] == 1 and s[(0, "q3_operating_income")] == 1
    assert s[(1, "q1_market_cap")] == 0 and s[(1, "q2_revenue")] == 0
    assert s[(1, "q3_operating_income")] == 0          # wrong sign
    assert s[(0, "q5_main_business")] == 1 and math.isnan(s[(1, "q5_main_business")])
    assert len(review) == 1 and s[(1, "q6_market")] == 0
    m = memory_strength(scores, responses).iloc[0]
    # item means: q1 .5, q2 .5, q3 .5, q4 1, q5 1 (one scored), q6 .5
    assert m.M_i == pytest.approx((0.5 + 0.5 + 0.5 + 1 + 1 + 0.5) / 6)
    assert m.p_mem == pytest.approx(10_000)
    assert market_of("KOSPI 상장") == "KOSPI" and market_of("모름") is None


def test_identification():
    ids = FirmIdentifiers(firm_id="F1", names=["삼성전자", "SAMSUNG ELECTRONICS"],
                          ticker="005930")
    assert is_correct({"guess_name": "삼성전자(주)"}, ids)
    assert is_correct({"guess_name": "Samsung Electronics Co., Ltd."}, ids)
    assert is_correct({"guess_name": "모름", "guess_ticker": "5930"}, ids)
    assert not is_correct({"guess_name": "SK하이닉스", "guess_ticker": "000660"}, ids)
    assert not is_correct({"guess_name": None}, ids)
    resp = pd.DataFrame([row(cond="A", schema="identification", rep=i,
                             out={"guess_name": n, "confidence": 0.5})
                         for i, n in enumerate(["삼성전자", "LG전자", None])])
    rate = identification_rate(resp, {"F1": ids}).iloc[0]
    assert rate.id_rate == pytest.approx(1 / 3) and rate.n == 3


# ---------------------------------------------------------------- dilution / failure stages


def test_worked_example_and_otm():
    v_star, v_debt, delta = theoretical_diluted_value(100_000, 10_000_000, 20_000, 8_000)
    assert (v_star, v_debt, delta) == pytest.approx((9_600, 10_000, -400))
    assert theoretical_diluted_value(100_000, 10_000_000, 20_000, 12_000)[2] == 0
    p = {"face_mn": 20_000, "convertible_shares": 2_500_000}
    assert cb_theory("cb_v0", 100_000, 10_000_000, p) == pytest.approx(-400)
    assert cb_theory("cb_v4", 100_000, 10_000_000, p) == 0
    assert cb_theory("cb_v0", 100_000, 10_000_000, {}) == 0


def test_firm_dilution_end_to_end():
    p0 = {"face_mn": 20_000, "convertible_shares": 2_500_000}
    p2 = {"face_mn": 40_000, "convertible_shares": 5_000_000}
    rows = []
    for r in range(5):
        jitter = (r - 2) * 1.0
        rows.append(row(ptype="cb_v1", v=10_000 + jitter, rep=r, shares=1e7, equity=100_000))
        rows.append(row(ptype="cb_v0", params=p0, v=9_600 + jitter, rep=r, shares=1e7))
        rows.append(row(ptype="cb_v2", params=p2, v=1.4e11 / 1.5e7 + jitter, rep=r,
                        shares=1e7))
        rows.append(row(ptype="cb_v4", params={"placebo": "irrelevant"}, v=9_600 + jitter,
                        rep=r, shares=1e7))
    d = firm_dilution(pd.DataFrame(rows), n_boot=100).iloc[0]
    assert d.R_dil_V0 == pytest.approx(1.0) and d.R_dil_V2 == pytest.approx(1.0)
    assert d.dose_slope == pytest.approx(1.0, abs=1e-6) and d.itm_agent
    assert d.placebo_irrelevant_shift == pytest.approx(0)
    ps = placebo_shift(np.array([]), np.array([1.0]))
    assert math.isnan(ps["shift"])
    dr = dose_response(np.array([1.0, 1.0]), {}, {})
    assert math.isnan(dr["dose_slope"])


def test_failure_stages():
    base = valuation_dict("small_cb_single")       # oracle output with dilution applied
    out = ValuationOutput.model_validate(base)
    truth = out.dilution.convertible_shares
    basic = out.calculation.shares_used
    assert classify(out, truth, basic) == "success"
    assert classify(out, truth * 1.2, basic) == "extraction_failure"
    nodil = ValuationOutput.model_validate(base)
    nodil.dilution.dilution_applied = False
    assert classify(nodil, truth, basic) == "reflection_failure"
    calc = ValuationOutput.model_validate(base)
    calc.result.value_per_share *= 1.05
    assert classify(calc, truth, basic) == "computation_failure"
    missing = ValuationOutput.model_validate(base)
    missing.dilution.convertible_shares = None
    assert classify(missing, truth, basic) == "extraction_failure"
    st = pd.DataFrame([{"firm_id": "F", "agent_structure": "P", "model_key": "m",
                        "stage": s} for s in ("success", "success", "reflection_failure")])
    shares = stage_shares(st).iloc[0]
    assert shares.success == pytest.approx(2 / 3) and shares.extraction_failure == 0
