"""P7: the pilot report builds from a synthetic run table."""

import math

import pandas as pd
import pytest

from src.agents.synthetic import CalcErrorAgent, OracleAgent
from src.analysis.pilot_report import (
    cost_estimate,
    evaluate,
    extraction_check,
    n_rule,
    render,
    sigma_stability,
    size_table,
)
from src.config import load_config
from src.experiments import builders as b
from src.metrics.synthetic_validation import run_agent, sizes_from
from tests.fakes import FixtureStore
from tests.p5_helpers import MODEL

CFG = load_config()
STORE = FixtureStore()
FIRMS = ["L001", "S001"]
SYN = {"agent_structure": "P", "model_key": "syn"}   # treated as structure P in the gates


@pytest.fixture(scope="module")
def runs():
    e0 = run_agent(OracleAgent(0.03), b.e0(CFG, STORE, FIRMS, reps=20, **SYN), STORE)
    e2 = run_agent(OracleAgent(0.03), b.e0_e2(CFG, STORE, FIRMS, reps=5,
                                              conditions=["C", "A"], **SYN), STORE)
    return pd.concat([e0, e2], ignore_index=True)


def test_gates_from_synthetic_runs(runs):
    sizes = sizes_from(runs[runs.experiment == "E0"], STORE, CFG)
    res = evaluate(runs, CFG, sizes=sizes, packages=STORE.pkgs, n_boot=50)
    g = {x.name.split()[0]: x for x in res.gates}
    assert g["G1"].passed and g["G1"].value == 1.0
    assert g["G2"].passed and g["G2"].value == 0.0
    assert g["G3"].passed is None or isinstance(g["G3"].passed, bool)
    assert g["G4"].value is not None and g["G5"].passed is None
    assert res.numbers["unit_slip_share"] == 0.0
    assert set(res.tables["sigma"]["firm_id"]) == set(FIRMS)
    text = render(res, "test", cost=cost_estimate(runs.assign(tokens_in=100, tokens_out=10),
                                                  MODEL), sizes=size_table(sizes))
    assert "G5 Data" in text and "pending" in text and "Size decisions" in text


def test_calc_errors_fail_g2():
    r = run_agent(CalcErrorAgent(0.0), b.e0(CFG, STORE, ["L001"], reps=3, **SYN), STORE)
    res = evaluate(r, CFG, n_boot=10)
    g2 = next(x for x in res.gates if x.name.startswith("G2"))
    assert g2.value == 1.0 and g2.passed is False


def test_extraction_slip_detected(runs):
    one = runs[runs.perturbation_type == "none"].head(1).copy()
    import json

    d = json.loads(one["output_json"].iloc[0])
    d["extracted"]["shares_outstanding"] /= 1000
    one["output_json"] = json.dumps(d)
    assert extraction_check(one, STORE.pkgs)["unit_slip"].all()


def test_n_rule_and_sigma_stability():
    assert n_rule(5.0, 100.0, CFG) == CFG.experiments.n_min             # 2 (5/10)^2 -> 1
    assert n_rule(1000.0, 100.0, CFG) == CFG.experiments.n_max
    assert n_rule(30.0, 100.0, CFG) == max(math.ceil(2 * (30 / 10) ** 2), CFG.experiments.n_min)
    assert n_rule(float("nan"), 1.0, CFG) == CFG.experiments.n_max
    df = pd.DataFrame({"firm_id": "F", "rep": range(20), "valid": True,
                       "value_per_share": [100 + (i % 5) for i in range(20)]})
    s = sigma_stability(df).iloc[0]
    assert s.rel_20 == pytest.approx(1.0) and s.n_valid == 20
