"""P8: the frozen-code check detects edits after the tag; monitor thresholds trigger."""

import subprocess
from types import SimpleNamespace

import pandas as pd
import pytest

from src.runner.frozen import changed_since, tag_exists
from src.runner.monitor import batch_checks, cell_completeness, extreme_values, spend_usd


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    prompts = tmp_path / "src" / "agents" / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "tool.txt").write_text("v1\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    _git(tmp_path, "tag", "prereg-v1")
    return tmp_path


def test_frozen_clean_then_modified(repo):
    assert tag_exists("prereg-v1", repo)
    assert changed_since("prereg-v1", repo=repo) == []
    (repo / "README.md").write_text("changed outside the frozen paths\n", encoding="utf-8")
    assert changed_since("prereg-v1", repo=repo) == []
    (repo / "src/agents/prompts/tool.txt").write_text("v2\n", encoding="utf-8")
    assert changed_since("prereg-v1", repo=repo) == ["src/agents/prompts/tool.txt"]


def test_frozen_detects_new_and_committed_files(repo):
    (repo / "src/perturb").mkdir(parents=True)
    (repo / "src/perturb/new.py").write_text("x = 1\n", encoding="utf-8")
    assert changed_since("prereg-v1", repo=repo) == ["src/perturb/new.py"]
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "after tag")
    assert changed_since("prereg-v1", repo=repo) == ["src/perturb/new.py"]


def test_frozen_missing_tag(repo):
    assert not tag_exists("nope", repo)
    with pytest.raises(RuntimeError):
        changed_since("nope", repo=repo)


def _runs(n=100, valid=1.0, refusal=0.0, anomaly=0.0, models=("m",)):
    rows = []
    for i in range(n):
        ok = i < n * valid
        rows.append({
            "job_id": str(i), "cache_key": str(i), "experiment": "E2", "firm_id": f"F{i % 5}",
            "condition": "C", "perturbation_type": "none", "perturbation_params": "{}",
            "schema_name": "valuation", "valid": ok,
            "error": "refusal" if (not ok and i < n * valid + n * refusal) else None,
            "anomaly_flag": i < n * anomaly, "model_reported": models[i % len(models)],
            "latency_s": 2.0, "tokens_in": 1000, "tokens_out": 500,
            "value_per_share": 100.0 if i else 5000.0})
    return pd.DataFrame(rows)


def _alerts(runs, **kw):
    return {a.metric: a for a in batch_checks(runs, **kw)}


def test_monitor_quiet_batch():
    a = _alerts(_runs(), pilot_anomaly=0.05, spent=10, budget=100)
    assert not any(x.triggered for x in a.values())


def test_monitor_thresholds_trigger():
    assert _alerts(_runs(valid=0.85))["valid-run rate"].triggered
    assert _alerts(_runs(valid=0.95, refusal=0.03))["refusal rate"].triggered
    assert _alerts(_runs(anomaly=0.2), pilot_anomaly=0.05)["anomaly-flag rate"].triggered
    halt = _alerts(_runs(models=("m", "m-2")))["model_reported"]
    assert halt.triggered and halt.action == "halt"
    assert _alerts(_runs(), spent=85, budget=100)["spend / budget"].triggered
    assert not _alerts(_runs(), spent=85, budget=100, before_e8=False)["spend / budget"].triggered


def test_monitor_spend_cells_extremes():
    cfg = SimpleNamespace(price_in_per_mtok=1.0, price_out_per_mtok=2.0)
    runs = _runs(10)
    assert spend_usd(pd.concat([runs, runs]), cfg) == pytest.approx(10 * 2000 / 1e6)
    cells = cell_completeness(_runs(10, valid=0.5))
    assert cells["n_total"].sum() == 10 and cells["n_valid"].sum() == 5
    assert list(extreme_values(_runs(20))["job_id"]) == ["0"]
