"""Project configuration.

All modules read configuration through `load_config()` and secrets through `require_env()`.
Values that are not known yet (models, evaluation dates, budget) may be left empty in the YAML
files; the `require_*` helpers raise a clear error when code needs them.
"""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- models.yaml


class ModelConfig(StrictModel):
    key: str
    provider: Literal["openai_compatible", "anthropic", "openai", "google"]
    model_id: str
    base_url: str | None = None
    api_key_env: str
    training_cutoff: date
    cutoff_source: HttpUrl
    reasoning: bool
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    max_output_tokens: int = Field(4096, gt=0)
    max_concurrency: int = Field(4, gt=0)
    price_in_per_mtok: float = Field(ge=0.0)
    price_out_per_mtok: float = Field(ge=0.0)
    context_window: int = Field(gt=0)
    structured_output: bool = False


# ---------------------------------------------------------------- sample.yaml


class GroupSpec(StrictModel):
    size: int = Field(gt=0)
    market: Literal["KOSPI", "KOSDAQ"]
    description: str


class ExclusionSpec(StrictModel):
    ksic_prefixes: list[str]
    admin_issue: bool = True
    trading_halt: bool = True
    capital_impairment: bool = True
    min_years: int = Field(3, ge=1)


class SampleConfig(StrictModel):
    t_post: date | None = None
    t_pre: date | None = None
    groups: dict[Literal["L", "M", "S"], GroupSpec]
    mid_rank_band: tuple[int, int] = (101, 400)
    exclusions: ExclusionSpec
    cb_search_years: int = Field(6, gt=0)
    seed: int = 20261019

    @model_validator(mode="after")
    def _check_dates(self) -> SampleConfig:
        if self.t_post and self.t_pre and not self.t_pre < self.t_post:
            raise ValueError("t_pre must be earlier than t_post")
        lo, hi = self.mid_rank_band
        if not 0 < lo < hi:
            raise ValueError("mid_rank_band must be (low, high) with 0 < low < high")
        return self


# ---------------------------------------------------------------- experiments.yaml


class ExperimentsConfig(StrictModel):
    k_grid: list[float] = [0.5, 0.8, 1.0, 1.25, 2.0]
    k_identification: list[float] = [1.0, 1.5]
    n_default: int = Field(10, gt=0)
    n_min: int = Field(5, gt=0)
    n_max: int = Field(40, gt=0)
    target_se: float = Field(0.1, gt=0)
    size_floor: float = Field(0.05, gt=0, lt=1)
    size_cap: float = Field(0.10, gt=0, lt=1)
    tiers: list[float] = [0.02, 0.05, 0.10]
    share_multiplier: float = Field(2.0, gt=0)
    bootstrap_reps: int = Field(1000, gt=0)

    @model_validator(mode="after")
    def _check(self) -> ExperimentsConfig:
        if 1.0 not in self.k_grid:
            raise ValueError("k_grid must contain the baseline k = 1.0")
        if any(k <= 0 for k in self.k_grid):
            raise ValueError("k values must be positive")
        if not self.n_min <= self.n_default <= self.n_max:
            raise ValueError("require n_min <= n_default <= n_max")
        if not self.size_floor <= self.size_cap:
            raise ValueError("size_floor must not exceed size_cap")
        return self


# ---------------------------------------------------------------- budget.yaml


class BudgetConfig(StrictModel):
    total_usd: float | None = Field(None, ge=0)
    reserved_extensions_usd: float | None = Field(None, ge=0)


# ---------------------------------------------------------------- root


class Config(StrictModel):
    models: dict[str, ModelConfig]
    sample: SampleConfig
    experiments: ExperimentsConfig
    budget: BudgetConfig

    def require_model(self, key: str) -> ModelConfig:
        if key not in self.models:
            raise KeyError(f"model '{key}' is not configured in config/models.yaml")
        return self.models[key]

    def require_dates(self) -> tuple[date, date]:
        if self.sample.t_post is None or self.sample.t_pre is None:
            raise ValueError("t_post / t_pre are not set in config/sample.yaml (decided in P0)")
        return self.sample.t_post, self.sample.t_pre


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_config(root: Path = CONFIG_DIR) -> Config:
    """Load and validate every config file under `root`."""
    raw_models = _read_yaml(root / "models.yaml").get("models") or {}
    models = {key: {"key": key, **spec} for key, spec in raw_models.items()}
    return Config(
        models=models,
        sample=_read_yaml(root / "sample.yaml"),
        experiments=_read_yaml(root / "experiments.yaml"),
        budget=_read_yaml(root / "budget.yaml"),
    )


@lru_cache(maxsize=1)
def get_config() -> Config:
    return load_config()


# ---------------------------------------------------------------- secrets


def require_env(name: str) -> str:
    """Return a secret from the environment or the project `.env`; raise if missing."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"environment variable {name} is not set (see .env.example)")
    return value
