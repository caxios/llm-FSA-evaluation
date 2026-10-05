"""Shared builders for the P5 tests."""

from __future__ import annotations

import json

from src.agents.synthetic import oracle_inputs
from src.agents.valuation_tools import value_from_inputs
from src.config import ModelConfig
from tests.fakes import load_package

MODEL = ModelConfig(
    key="fake", provider="openai_compatible", model_id="fake-model",
    base_url="https://example.invalid/v1", api_key_env="FAKE_API_KEY",
    training_cutoff="2025-01-01", cutoff_source="https://example.invalid/card",
    reasoning=False, temperature=0.3, max_output_tokens=4096, max_concurrency=2,
    price_in_per_mtok=0.1, price_out_per_mtok=0.4, context_window=100000)


def valuation_dict(name: str = "mid") -> dict:
    return value_from_inputs(oracle_inputs(load_package(name))).model_dump(mode="json")


def valuation_json(name: str = "mid") -> str:
    return json.dumps(valuation_dict(name), ensure_ascii=False)


def tool_json(name: str = "small_cb_single", apply_dilution: bool = True) -> str:
    return oracle_inputs(load_package(name), apply_dilution=apply_dilution).model_dump_json()
