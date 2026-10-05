import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.config import CONFIG_DIR, load_config, require_env

VALID_MODEL = {
    "provider": "openai_compatible",
    "model_id": "example/model",
    "base_url": "https://example.invalid/v1",
    "api_key_env": "PRIMARY_API_KEY",
    "training_cutoff": "2024-08-01",
    "cutoff_source": "https://example.invalid/model-card",
    "reasoning": False,
    "price_in_per_mtok": 0.1,
    "price_out_per_mtok": 0.3,
    "context_window": 128000,
}


@pytest.fixture
def cfg_dir(tmp_path: Path) -> Path:
    d = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, d)
    return d


def _edit(path: Path, **updates) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.update(updates)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def test_repo_config_loads():
    cfg = load_config()
    assert cfg.sample.groups["L"].size == 50
    assert 1.0 in cfg.experiments.k_grid
    assert cfg.experiments.size_floor == 0.05


def test_model_entry_loads_and_gets_key(cfg_dir):
    _edit(cfg_dir / "models.yaml", models={"primary": VALID_MODEL})
    cfg = load_config(cfg_dir)
    m = cfg.require_model("primary")
    assert m.key == "primary"
    assert m.temperature == 0.3


def test_missing_model_raises(cfg_dir):
    _edit(cfg_dir / "models.yaml", models={})
    cfg = load_config(cfg_dir)
    with pytest.raises(KeyError):
        cfg.require_model("primary")


def test_missing_required_model_field_raises(cfg_dir):
    bad = {k: v for k, v in VALID_MODEL.items() if k != "training_cutoff"}
    _edit(cfg_dir / "models.yaml", models={"primary": bad})
    with pytest.raises(ValidationError):
        load_config(cfg_dir)


@pytest.mark.parametrize("temp", [-0.1, 2.5])
def test_temperature_out_of_range_raises(cfg_dir, temp):
    _edit(cfg_dir / "models.yaml", models={"primary": {**VALID_MODEL, "temperature": temp}})
    with pytest.raises(ValidationError):
        load_config(cfg_dir)


def test_unknown_field_rejected(cfg_dir):
    _edit(cfg_dir / "experiments.yaml", n_defualt=10)
    with pytest.raises(ValidationError):
        load_config(cfg_dir)


def test_t_pre_must_precede_t_post(cfg_dir):
    _edit(cfg_dir / "sample.yaml", t_post="2023-04-03", t_pre="2026-04-01")
    with pytest.raises(ValidationError):
        load_config(cfg_dir)


def test_require_dates_when_unset(cfg_dir):
    _edit(cfg_dir / "sample.yaml", t_post=None, t_pre=None)
    with pytest.raises(ValueError):
        load_config(cfg_dir).require_dates()


def test_k_grid_needs_baseline(cfg_dir):
    _edit(cfg_dir / "experiments.yaml", k_grid=[0.5, 2.0])
    with pytest.raises(ValidationError):
        load_config(cfg_dir)


def test_require_env(monkeypatch):
    monkeypatch.setenv("FSA_TEST_SECRET", "abc")
    assert require_env("FSA_TEST_SECRET") == "abc"
    monkeypatch.delenv("FSA_TEST_SECRET")
    with pytest.raises(RuntimeError):
        require_env("FSA_TEST_SECRET")
