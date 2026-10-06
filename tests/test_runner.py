"""P5: runner end to end with fake and synthetic agents (no network)."""

import pandas as pd
import pytest

from src.agents.llm_client import FakeClient
from src.agents.plain import PlainAgent
from src.agents.synthetic import OracleAgent
from src.config import load_config
from src.experiments import builders as b
from src.runner.cache import CallCache
from src.runner.cost import estimate, mean_tokens
from src.runner.run import COLUMNS, ModelChanged, Runner, main, write_table
from tests.fakes import FixtureStore
from tests.p5_helpers import MODEL, valuation_json

CFG = load_config()
STORE = FixtureStore()


def specs(**kw):
    return b.e0_e2(CFG, STORE, ["L001", "M001"], reps=2, conditions=["C"],
                   agent_structure=kw.get("agent_structure", "P"),
                   model_key=kw.get("model_key", "fake"))


def test_dry_run_makes_no_calls(tmp_path):
    client = FakeClient([])
    runner = Runner(PlainAgent(client, MODEL), CallCache(tmp_path / "c.sqlite"),
                    runs_dir=tmp_path)
    s = runner.run(specs(), STORE, dry_run=True, cfg=MODEL)
    assert client.calls == [] and s.pending == 2 * 5 * 2 and s.executed == 0
    assert s.cost[0].calls == 20 and s.cost[0].source == "default" and s.cost[0].usd > 0


def test_run_then_all_cache_hits_and_identical_table(tmp_path):
    cache = CallCache(tmp_path / "c.sqlite")
    client = FakeClient(lambda m: valuation_json())
    runner = Runner(PlainAgent(client, MODEL), cache, runs_dir=tmp_path)
    first = runner.run(specs(), STORE)
    assert first.executed == 20 and first.cached == 0 and len(client.calls) == 20
    t1 = pd.read_parquet(write_table(first.records, "E2", tmp_path))
    second = runner.run(specs(), STORE)
    assert second.executed == 0 and second.cached == 20 and len(client.calls) == 20
    t2 = pd.read_parquet(write_table(second.records, "E2", tmp_path))
    pd.testing.assert_frame_equal(t1, t2)
    assert list(t1.columns) == COLUMNS and t1["valid"].all()
    assert (tmp_path / "E2").exists()                     # JSONL log of new records only
    lines = sum(len(p.read_text(encoding="utf-8").splitlines())
                for p in (tmp_path / "E2").glob("*.jsonl"))
    assert lines == 20
    measured = mean_tokens(cache.records("fake"))
    assert estimate({"valuation": 10}, MODEL, measured)[0].source == "cache"


def test_limit_and_relabelled_cache_hits(tmp_path):
    cache = CallCache(tmp_path / "c.sqlite")
    runner = Runner(PlainAgent(FakeClient(lambda m: valuation_json()), MODEL), cache,
                    runs_dir=tmp_path, log_runs=False)
    s = runner.run(specs(), STORE, limit=5)
    assert s.executed == 5 and s.pending == 15
    e7 = b.e7  # E7-like request with identical prompts is served from the E2 cache
    e0 = b.e0(CFG, STORE, ["L001"], reps=2, agent_structure="P", model_key="fake")
    s2 = runner.run(e0, STORE)
    assert s2.cached + s2.executed == 2
    assert all(r.request.experiment == "E0" for r in s2.records)
    assert e7 is not None


def test_synthetic_agent_through_runner(tmp_path):
    runner = Runner(OracleAgent(0.0), CallCache(tmp_path / "c.sqlite"), runs_dir=tmp_path)
    s = runner.run(specs(agent_structure="SYN", model_key="syn_oracle"), STORE)
    assert s.executed == 20 and all(r.valid for r in s.records if r.request.firm_id == "L001")
    table = pd.read_parquet(write_table(s.records, "E2", tmp_path))
    l001 = table[(table.firm_id == "L001")]
    k1 = l001[l001.perturbation_type == "none"].value_per_share.iloc[0]
    k2 = l001[l001.perturbation_params.str.contains('"k": 2.0')].value_per_share.iloc[0]
    assert k2 == pytest.approx(2 * k1)


def test_model_change_halts(tmp_path):
    names = iter(["m-1"] * 3 + ["m-2"] * 50)

    class Switching(FakeClient):
        def complete(self, messages, cfg=None):
            r = super().complete(messages, cfg)
            return r.model_copy(update={"model_reported": next(names)})

    runner = Runner(PlainAgent(Switching(lambda m: valuation_json()), MODEL),
                    CallCache(tmp_path / "c.sqlite"), runs_dir=tmp_path, max_workers=1)
    with pytest.raises(ModelChanged):
        runner.run(specs(), STORE)


def test_cli_with_synthetic_agent(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("src.runner.run.RUNS_DIR", tmp_path)
    monkeypatch.setattr("src.runner.logger.RUNS_DIR", tmp_path)
    cache = CallCache(tmp_path / "c.sqlite")
    s = main(["--experiment", "E2", "--agent", "SYN:oracle", "--firms", "L001",
              "--conditions", "C", "--k", "1,2", "--reps", "1"], store=STORE, cache=cache)
    assert s.executed == 2
    s = main(["--experiment", "E2", "--agent", "SYN:oracle", "--firms", "L001",
              "--conditions", "C", "--k", "1,2", "--reps", "1", "--dry-run"],
             store=STORE, cache=cache)
    assert s.cached == 2 and s.pending == 0
    assert "estimated cost" in capsys.readouterr().out


def test_transient_failures_skip_job_and_keep_the_rest(tmp_path):
    from src.agents.llm_client import TransientError

    calls = {"n": 0}

    def flaky(messages):
        calls["n"] += 1
        if calls["n"] % 5 == 0:
            raise TransientError("getaddrinfo failed")
        return valuation_json()

    cache = CallCache(tmp_path / "c.sqlite")
    runner = Runner(PlainAgent(FakeClient(flaky), MODEL), cache, runs_dir=tmp_path,
                    max_workers=1)
    first = runner.run(specs(), STORE)
    assert first.failed == 4 and first.executed == 16 and len(first.records) == 16
    second = Runner(PlainAgent(FakeClient(lambda m: valuation_json()), MODEL), cache,
                    runs_dir=tmp_path).run(specs(), STORE)
    assert second.cached == 16 and second.executed == 4 and second.failed == 0
