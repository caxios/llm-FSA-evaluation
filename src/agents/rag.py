"""RAG agent (structure R, P9 §5.2): the rendered package is chunked and embedded; one query
per extraction group retrieves chunks; a single valuation call sees only the retrieved
chunks (in their original order) with the plain system prompt. The model does the
arithmetic, as in structure P.

The retrieved chunk ids are stored in the output (`retrieved_chunks`), so E9 can separate
retrieval failures (CB chunk not retrieved) from reasoning failures.
"""

from __future__ import annotations

from src.agents.base import RunRecord, RunRequest, make_record
from src.agents.llm_client import LLMClient, decoding
from src.agents.retrieval import CHUNKING, EMBED_MODEL, Embedder, Retriever, chunk_prompt
from src.config import ModelConfig
from src.data.package_schema import InputPackage
from src.parse.schema import SCHEMAS
from src.parse.validate import run_with_retries

QUERIES = {   # one query per extraction group in the output schema
    "income": "매출액, 영업이익, 감가상각비",
    "balance": "현금및현금성자산, 차입금, 사채, 전환사채, 금융자산, 관계기업투자",
    "cashflow": "유형자산 취득, 운전자본, 배당금 지급",
    "shares": "발행주식수, 자기주식",
    "cb": "전환사채 미상환 잔액, 전환가액, 전환가능 주식수",
}
TOP_K = 4


def retrieve(text: str, embedder) -> tuple[str, list[str]]:
    """(retrieved context, chunk ids). The company block (first chunk) is always kept."""
    chunks = chunk_prompt(text)
    retriever = Retriever(embedder, chunks)
    keep = {chunks[0].id}
    for q in QUERIES.values():
        keep |= {c.id for c in retriever.top_k(q, TOP_K)}
    picked = [c for c in chunks if c.id in keep]
    return "\n\n".join(c.text for c in picked), [c.id for c in picked]


class RagAgent:
    structure = "R"

    def __init__(self, client: LLMClient, cfg: ModelConfig, embedder=None,
                 max_retries: int = 2):
        self.client, self.cfg, self.max_retries = client, cfg, max_retries
        self.embedder = embedder or Embedder()

    def identity(self) -> dict:
        return {"model_id": self.cfg.model_id, "decoding": decoding(self.cfg),
                "rag": {"embed": EMBED_MODEL, "k": TOP_K, "chunking": CHUNKING}}

    def run(self, req: RunRequest, package: InputPackage | None = None) -> RunRecord:
        if req.schema_name != "valuation":
            msgs, ids = req.messages, []
        else:
            system, user = req.messages[0], req.messages[-1]
            context, ids = retrieve(user["content"], self.embedder)
            msgs = [system, {"role": "user", "content": context}]
        out, raws, err = run_with_retries(self.client, msgs, self.cfg,
                                          SCHEMAS[req.schema_name], self.max_retries)
        result = out.model_dump(mode="json") if out else None
        if result is not None and ids:
            result["retrieved_chunks"] = ids
        return make_record(req, self.identity(), valid=result is not None, output=result,
                           raws=raws, error=err)
