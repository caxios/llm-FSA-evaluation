"""P9: RAG chunking and retrieval (fake embedder), RAG agent, E10 renderer and builder."""

import numpy as np

from src.agents.llm_client import FakeClient
from src.agents.rag import RagAgent, retrieve
from src.agents.retrieval import Retriever, chunk_prompt
from src.config import load_config
from src.data.render import render_user_prompt, render_user_prompt_e10
from src.experiments import builders as b
from src.runner.jobs import expand
from tests.fakes import FixtureStore
from tests.p5_helpers import MODEL, valuation_json

CFG = load_config()
STORE = FixtureStore()
TERMS = ["전환사채", "전환가액", "현금", "차입금", "매출액", "영업이익", "발행주식", "자기주식",
         "유형자산", "배당금", "기업명", "사채", "금융자산"]


class BagEmbedder:
    """Deterministic keyword-count embedding (no network)."""

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        return np.array([[t.count(w) for w in TERMS] + [1e-3] for t in texts], dtype=float)


def cb_firm():
    return next(f for f, p in STORE.pkgs.items() if p.cb is not None)


def test_chunks_cover_the_prompt_and_split_long_tables():
    pkg = STORE.package(cb_firm())
    text = render_user_prompt(pkg, "C", include_cb=True)
    chunks = chunk_prompt(text)
    assert chunks[0].text.startswith("[기업 정보]")
    assert [c.id for c in chunks] == [f"c{i:02d}" for i in range(len(chunks))]
    rows = [ln for ln in text.split("\n") if ln.startswith("| ") and not ln.startswith("| 계정")]
    got = [ln for c in chunks for ln in c.text.split("\n")
           if ln.startswith("| ") and not ln.startswith("| 계정")]
    assert sorted(got) == sorted(rows)               # every data row lands in exactly one chunk
    assert all(sum(ln.startswith("| ") for ln in c.text.split("\n")) <= 27 for c in chunks)


def test_cb_query_retrieves_the_cb_chunk():
    pkg = STORE.package(cb_firm())
    chunks = chunk_prompt(render_user_prompt(pkg, "C", include_cb=True))
    top = Retriever(BagEmbedder(), chunks).top_k("전환사채 미상환 잔액, 전환가액", 2)
    assert any("전환" in c.text for c in top)
    context, ids = retrieve(render_user_prompt(pkg, "C", include_cb=True), BagEmbedder())
    assert ids[0] == "c00" and "전환가액" in context and len(ids) < len(chunks) + 1


def test_rag_agent_sends_only_retrieved_context():
    fid = cb_firm()
    client = FakeClient(lambda m: valuation_json())
    agent = RagAgent(client, MODEL, embedder=BagEmbedder())
    specs = b.e8(CFG, STORE, [fid], reps=1, agent_structure="R", model_key="fake")
    req, pkg = next(expand(specs[0], STORE))
    rec = agent.run(req, pkg)
    assert rec.valid and rec.output["retrieved_chunks"][0] == "c00"
    sent = client.calls[0][-1]["content"]
    chunks = {c.id: c.text for c in chunk_prompt(req.messages[-1]["content"])}
    ids = rec.output["retrieved_chunks"]
    assert set(ids) <= set(chunks) and sent == "\n\n".join(chunks[i] for i in ids)
    assert agent.identity()["rag"]["k"] == 4


def test_e10_positions_same_text_different_place():
    pkg = STORE.package(cb_firm())
    filler = "\n".join(f"이사회 개최 내역 {i}" for i in range(400))
    front = render_user_prompt_e10(pkg, filler, "front")
    middle = render_user_prompt_e10(pkg, filler, "middle")
    assert abs(len(front) - len(middle)) <= 4
    assert sorted(front.split("\n")) == sorted(middle.split("\n")) or \
        abs(len(front.split("\n")) - len(middle.split("\n"))) <= 2
    cb = pkg.cb.filing_text.split("\n")[0]
    assert front.index(cb) < front.index("[재무제표]")
    assert middle.index(cb) > middle.index("[기타 공시]")
    pos = middle.index(cb)
    assert middle.index("이사회 개최 내역 10\n") < pos < middle.index("이사회 개최 내역 390")
    no_cb = pkg.model_copy(update={"cb": None})
    assert "없음" in render_user_prompt_e10(no_cb, filler, "front")


def test_e10_builder_two_positions(monkeypatch):
    fid = cb_firm()
    monkeypatch.setattr(STORE, "filler", lambda f: "가\n나\n다\n라", raising=False)
    specs = b.e10(CFG, STORE, [fid], reps=2, agent_structure="T", model_key="fake")
    assert [s.cb_position for s in specs] == ["front", "middle"]
    reqs = [r for s in specs for r, _ in expand(s, STORE)]
    assert len(reqs) == 2 * 2 * 2 and len({r.job_id for r in reqs}) == 8
    assert all("pos=" in r.job_id for r in reqs)
