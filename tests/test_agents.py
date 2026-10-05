"""P5: prompts, plain / tool / synthetic agents."""

import math

import pytest

from src.agents.base import RunRequest, cache_key
from src.agents.llm_client import FakeClient
from src.agents.plain import PlainAgent
from src.agents.prompts.registry import FROZEN, PROMPTS, get_prompt, prompt_hashes
from src.agents.synthetic import (
    AnchoredAgent,
    CalcErrorAgent,
    MixtureAgent,
    NoDilutionAgent,
    OracleAgent,
    oracle_inputs,
)
from src.agents.tool import ToolAgent
from src.agents.valuation_tools import recompute_value, value_from_inputs
from src.data.render import USER_TEMPLATE_V1, render_user_prompt
from src.parse.schema import ValuationOutput
from src.perturb import PerturbMeta, perturb
from tests.fakes import load_package
from tests.p5_helpers import MODEL, tool_json, valuation_json


def request(firm="M001", messages=None, schema="valuation", structure="P", rep=0):
    return RunRequest(job_id=f"t|{firm}|{rep}", firm_id=firm, group=firm[0], experiment="T",
                      condition="C", perturbation=PerturbMeta(type="none"),
                      agent_structure=structure, model_key="fake", prompt_version="v1",
                      rep=rep, messages=messages or [{"role": "user", "content": firm}],
                      schema_name=schema)


# ---------------------------------------------------------------- prompts


def test_prompts_registered_and_hashed():
    hashes = prompt_hashes()
    assert set(hashes) == set(PROMPTS) and all(len(h) == 64 for h in hashes.values())
    for key, sha in FROZEN.items():  # pinned after the prereg-v1 tag
        assert hashes[key] == sha, f"frozen prompt {key} changed"
    with pytest.raises(KeyError):
        get_prompt("nope")


def test_user_template_matches_renderer_and_slots_filled():
    assert get_prompt("valuation_user_v1")[0] == USER_TEMPLATE_V1
    text = render_user_prompt(load_package("small_cb_single"), "C", include_cb=True)
    assert "{" not in text.replace("{\n", "")
    for header in ("[기업 정보]", "[재무제표]", "[주식 정보]", "[주석 요약]", "[추가 공시]"):
        assert header in text
    system = get_prompt("valuation_system_v1")[0]
    assert "end_of_year" in system and "non_operating_assets_added" in system
    assert "6." not in system and "6." in get_prompt("valuation_system_v1_instr")[0]


# ---------------------------------------------------------------- LLM agents


def test_plain_agent_valid_and_invalid():
    agent = PlainAgent(FakeClient([valuation_json()]), MODEL)
    rec = agent.run(request())
    assert rec.valid and rec.attempts == 1 and rec.model_reported == "fake-model"
    assert ValuationOutput.model_validate(rec.output)
    assert rec.cache_key == cache_key(request(), agent.identity())
    bad = PlainAgent(FakeClient(["x", "y", "z"]), MODEL).run(request())
    assert not bad.valid and bad.attempts == 3 and bad.error and bad.output is None


def test_tool_agent_computes_valuation():
    rec = ToolAgent(FakeClient([tool_json()]), MODEL).run(request(structure="T"))
    assert rec.valid
    out = ValuationOutput.model_validate(rec.output)
    assert out.dilution.dilution_applied and out.dilution.diluted_shares
    assert recompute_value(out) == pytest.approx(out.result.value_per_share)
    assert "tool_inputs" in rec.output
    # identification requests have no tool step
    ident = ToolAgent(FakeClient(['{"guess_name": "모른다", "confidence": 0}']), MODEL).run(
        request(schema="identification", structure="T"))
    assert ident.valid and ident.output["guess_name"] is None


# ---------------------------------------------------------------- synthetic agents


def test_oracle_zero_noise_reproduces_valuation_tools():
    pkg = load_package("small_cb_single")
    rec = OracleAgent(noise_sd=0.0).run(request("S001", structure="SYN"), pkg)
    expected = value_from_inputs(oracle_inputs(pkg)).result.value_per_share
    assert rec.valid and rec.output["result"]["value_per_share"] == pytest.approx(expected)
    assert rec.output["dilution"]["dilution_applied"] is True


def test_oracle_scale_elasticity_one_and_reproducible_noise():
    pkg = load_package("large_pref")
    a = OracleAgent(noise_sd=0.0)
    v1 = a.run(request("L001"), pkg).output["result"]["value_per_share"]
    v2 = a.run(request("L001"), perturb(pkg, "scale", k=2.0)[0]).output["result"][
        "value_per_share"]
    assert v2 == pytest.approx(2 * v1)
    noisy = OracleAgent(noise_sd=0.1)
    r1, r2 = noisy.run(request("L001"), pkg), noisy.run(request("L001"), pkg)
    assert r1.output == r2.output
    r3 = noisy.run(request("L001", rep=1), pkg)
    assert r3.output["result"]["value_per_share"] != r1.output["result"]["value_per_share"]


def test_other_synthetic_agents():
    pkg = load_package("small_cb_single")
    req = request("S001")
    oracle = OracleAgent(0.0).run(req, pkg).output["result"]["value_per_share"]
    nodil = NoDilutionAgent(0.0).run(req, pkg).output
    assert nodil["dilution"]["dilution_applied"] is False
    assert nodil["dilution"]["convertible_shares"] > 0
    assert nodil["result"]["value_per_share"] >= oracle
    calc = CalcErrorAgent(0.0).run(req, pkg).output
    assert calc["result"]["value_per_share"] == pytest.approx(1.1 * oracle)
    big = load_package("large_pref")
    anchored = AnchoredAgent({"L001": 123_000.0}, 0.0)
    for p in (big, perturb(big, "scale", k=2.0)[0]):            # ignores the package
        assert anchored.run(request("L001"), p).output["result"]["value_per_share"] == \
            pytest.approx(123_000.0)
    v_or = OracleAgent(0.0).run(request("L001"), big).output["result"]["value_per_share"]
    mix = MixtureAgent({"L001": 123_000.0}, w=0.25, noise_sd=0.0).run(request("L001"), big)
    assert mix.output["result"]["value_per_share"] == pytest.approx(
        math.exp(0.25 * math.log(v_or) + 0.75 * math.log(123_000.0)))
    with pytest.raises(ValueError):
        OracleAgent().run(req, None)


def test_synthetic_failure_is_invalid_record():
    pkg = load_package("mid")  # negative operating income -> negative oracle value
    rec = MixtureAgent({"M001": 1000.0}, w=0.5).run(request("M001"), pkg)
    assert not rec.valid and rec.error.startswith("synthetic")
