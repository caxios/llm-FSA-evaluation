"""P6: synthetic agents through the full runner path recover their built-in behaviour
(fixture packages; the 150-firm run is scripts/synthetic_validation.py)."""

import pandas as pd
import pytest

from src.agents.synthetic import OracleAgent
from src.config import load_config
from src.experiments import builders as b
from src.metrics.firm_table import build_firm_table, load_runs, write_firm_table
from src.metrics.synthetic_validation import ci_coverage, report, run_agent, validate
from tests.fakes import FixtureStore

CFG = load_config()
STORE = FixtureStore()


@pytest.fixture(scope="module")
def result():
    # lower noise than the 150-firm script: the fixtures have only 2-3 firms per check
    return validate(CFG, STORE, list(STORE.pkgs), reps=10, noise=0.02, n_boot=100)


def test_all_pass_bands(result):
    failed = result.table().query("not passed")
    assert failed.empty, failed.to_string()
    assert result.info["oracle_itm_cb_firms"] >= 1


def test_report_and_coverage(result):
    text = report(result, 0.95, "fixture")
    assert "PASS" in text and "93–97%" in text
    assert 0.90 <= ci_coverage(n_firms=60, n=10, n_boot=300) <= 1.0


def test_firm_table_columns(tmp_path):
    syn = {"agent_structure": "SYN", "model_key": "syn_oracle"}
    firms = list(STORE.pkgs)
    runs = run_agent(OracleAgent(0.02),
                     b.e0_e2(CFG, STORE, firms, reps=3, **syn)
                     + b.e3(CFG, STORE, firms, reps=3, **syn)
                     + b.e8(CFG, STORE, firms, reps=3, **syn), STORE)
    sample = pd.DataFrame({"firm_id": firms, "group": [STORE.group(f) for f in firms]})
    table = build_firm_table(runs, sample=sample, n_boot=20)
    for col in ("v0_C", "sigma_C", "beta_A", "beta_C", "se_C", "memory_eff", "memory_eff_se",
                "R_shares", "eps_mean", "R_dil_V0", "dose_slope", "success",
                "n_low_validity_cells", "anomaly_rate", "group"):
        assert col in table.columns, col
    assert set(table["firm_id"]) == set(firms) and len(table) == len(firms)
    runs.to_parquet(tmp_path / "E2.parquet", index=False)
    assert len(load_runs(tmp_path)) == len(runs) and load_runs(tmp_path / "none").empty
    assert write_firm_table(table, tmp_path / "f.parquet").exists()
