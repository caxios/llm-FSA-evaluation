"""P5: job expansion and experiment builders."""

import pytest

from src.config import load_config
from src.experiments import builders as b
from src.perturb.sizing import SizeDecision
from src.runner.jobs import ExpandStats, JobSpec, expand
from tests.fakes import FixtureStore

CFG = load_config()
STORE = FixtureStore()
FIRMS = list(STORE.pkgs)              # L001, M001, S035, S001, S033
N = CFG.experiments.n_default


def count(specs):
    stats = ExpandStats()
    reqs = [r for s in specs for r, _ in expand(s, STORE, stats)]
    return reqs, stats


def test_e2_and_e0_counts():
    reqs, stats = count(b.e0_e2(CFG, STORE, FIRMS))
    assert len(reqs) == len(FIRMS) * 4 * len(CFG.experiments.k_grid) * N
    assert stats.cells == len(FIRMS) * 4 * len(CFG.experiments.k_grid)
    assert len({r.job_id for r in reqs}) == len(reqs)
    e0, _ = count(b.e0(CFG, STORE, FIRMS))
    assert len(e0) == len(FIRMS) * N and {r.condition for r in e0} == {"C"}
    # E0 prompts are exactly the E2 k = 1, condition C prompts
    e2_c1 = {(r.firm_id, r.rep): r.messages for r in reqs
             if r.condition == "C" and r.perturbation.type == "none"}
    assert all(e2_c1[(r.firm_id, r.rep)] == r.messages for r in e0)


def test_e2_excludes_cb_text_and_conditions_differ():
    reqs, _ = count(b.e0_e2(CFG, STORE, ["S001"], reps=1))
    for r in reqs:
        assert "전환가액" not in r.messages[1]["content"]
    c = next(r for r in reqs if r.condition == "C" and r.perturbation.type == "none")
    a = next(r for r in reqs if r.condition == "A" and r.perturbation.type == "none")
    assert STORE.real_name("S001") in c.messages[1]["content"]
    assert STORE.real_name("S001") not in a.messages[1]["content"]


def test_e3_with_sizes_and_proxy():
    sizes = [SizeDecision(firm_id="L001", perturbation="cash", x_mn=1000.0, fraction=0.05,
                          n=15, status="increased_n"),
             SizeDecision(firm_id="M001", perturbation="cash", n=10, status="excluded"),
             SizeDecision(firm_id="L001", perturbation="non_operating", x_mn=500.0,
                          fraction=0.05, n=10, status="ok")]
    reqs, _ = count(b.e3(CFG, STORE, ["L001", "M001"], sizes=sizes))
    kinds = {}
    for r in reqs:
        kinds.setdefault((r.firm_id, r.perturbation.type), 0)
        kinds[(r.firm_id, r.perturbation.type)] += 1
    assert kinds == {("L001", "shares"): N, ("M001", "shares"): N, ("L001", "cash"): 15,
                     ("L001", "non_operating"): N}
    proxy, stats = count(b.e3(CFG, STORE, FIRMS, reps=2, tiers=True))
    assert {r.perturbation.type for r in proxy} == {"shares", "cash", "non_operating"}
    assert stats.skipped  # tier sizes above the cash balance are skipped, not failed


def test_e5_e6_e7_e8():
    e5, _ = count(b.e5(CFG, STORE, FIRMS))
    assert len(e5) == len(FIRMS) * 3 * 2 * 3
    assert {r.schema_name for r in e5} == {"identification"}
    assert all("이 회사가 어느 회사인지" in r.messages[0]["content"] for r in e5)
    e6, _ = count(b.e6(CFG, STORE, FIRMS))
    assert len(e6) == len(FIRMS) * 3 and e6[0].schema_name == "quiz"
    assert STORE.real_name(e6[0].firm_id) in e6[0].messages[0]["content"]
    assert "2026년 4월 1일" in e6[0].messages[0]["content"]
    e8, stats = count(b.e8(CFG, STORE, FIRMS, reps=1))
    cb_firms = [f for f in FIRMS if STORE.package(f).cb is not None]
    assert {r.firm_id for r in e8} == set(cb_firms)
    assert len(e8) == len(cb_firms) * 6 - len(stats.skipped)
    v0 = next(r for r in e8 if r.perturbation.type == "cb_v0")
    assert "전환가액" in v0.messages[1]["content"]
    # V1 (CB removed) renders exactly the E2 k = 1 condition-C prompt -> shared cache
    v1 = next(r for r in e8 if r.perturbation.type == "cb_v1")
    e2, _ = count(b.e0_e2(CFG, STORE, [v1.firm_id], reps=1, conditions=["C"]))
    assert v1.messages == next(r for r in e2 if r.perturbation.type == "none").messages
    assert isinstance(b.e7(CFG, STORE, FIRMS), list)


def test_spec_helpers_and_tool_prompt():
    spec = JobSpec(experiment="X", firm_ids=["L001"], conditions=["C"],
                   perturbations={"L001": [("none", {})]}, reps={"L001": 2},
                   agent_structure="T")
    reqs = [r for r, _ in expand(spec, STORE)]
    assert len(reqs) == 2 and "계산 도구" in reqs[0].messages[0]["content"]
    assert spec.perturbations_for("M001") == [] and spec.reps_for("M001") == 0
    with pytest.raises(KeyError):
        list(expand(spec.model_copy(update={"agent_structure": "P",
                                            "prompt_version": "v9"}), STORE))
