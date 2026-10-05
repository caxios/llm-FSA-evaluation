# P9 — Extension Experiments

| Item | Value |
|---|---|
| Roadmap | R§11 |
| Weeks | 12–15 (overlaps with the end of P8) |
| Status | Provisional (finalize with P7 outputs and P8 spend) |
| Version | v0.1 (2026-10-05) |
| Depends on | P7 (prereg), P8 spend through module 5 |
| Unlocks | P10 (H4, model and instruction robustness) |

## 1. Objective

Run the secondary experiments that test H4 (agent structure) and the robustness rows of §7.5 that need new model calls: agent structures R and T, comparison model, instruction effect, and optionally the information-position experiment E10.

## 2. Entry conditions

- P8 modules 1–5 complete, remaining budget known.
- Extension subsets defined in the preregistration (firm lists hashed).

## 3. Decisions resolved in this phase

| ID | Decision | Recommendation |
|---|---|---|
| D9.1 | Embedding model for RAG | A multilingual open model run locally (e.g., a BGE-M3–class model), so no extra API dependency; record the exact checkpoint |
| D9.2 | RAG chunking | One chunk per statement section (BS current/non-current, IS, CF sections), per share-info block, per notes block, and ~500-token windows for filing text |
| D9.3 | Run order under a limited budget | 1) Structure T (H4 core), 2) instruction effect, 3) comparison model, 4) structure R, 5) E10 |

## 4. Deliverables

```
src/agents/rag.py
src/agents/retrieval.py
src/experiments/ext_structures.py
src/experiments/ext_comparison.py
src/experiments/ext_instruction.py
src/experiments/e10.py
src/data/render.py               # + cb_position option
tests/test_rag.py
tests/test_e10_render.py
results/runs/EXT_*.parquet
results/qa/extensions_qa.md
```

## 5. Design

### 5.1 Subsets

| Extension | Firms | Modules | Reps | Calls (approx.) |
|---|---|---|---|---|
| Structure T | 30 (10 L, 10 M, 10 S; seeded stratified draw, fixed in prereg) | E2 condition C (5 k) + E8 V0–V4 for 20 S firms | 10 | 1,500 + 1,000 |
| Structure R | Same 30 / 20 | Same | 10 | 1,500 + 1,000 |
| Comparison model | Same 30 | E2 conditions C and D | 10 | 3,000 |
| Instruction effect | Same 30 | E2 condition C with `valuation_system_v1_instr` | 10 | 1,500 |
| E10 (optional) | 20 S firms | E8 V0 and V1 with CB text at front vs middle | 10 | 800 |

Using the same 30 firms across extensions allows within-firm comparisons across structures, models, and instructions. If structure T became the primary structure in P7 (G2), then "structure P" takes T's place in this table.

### 5.2 RAG agent (`rag.py`, `retrieval.py`)

```python
class Retriever:
    def __init__(self, embedder, chunks: list[Chunk]): ...
    def top_k(self, query: str, k: int = 4) -> list[Chunk]

class RagAgent(Agent):
    QUERIES = {   # one query per extraction group in the output schema (Korean)
        "income": "매출액, 영업이익, 감가상각비",
        "balance": "현금및현금성자산, 차입금, 사채, 전환사채, 금융자산, 관계기업투자",
        "cashflow": "유형자산 취득, 운전자본, 배당금 지급",
        "shares": "발행주식수, 자기주식",
        "cb": "전환사채 미상환 잔액, 전환가액, 전환가능 주식수",
    }
    def run(self, req): ...
    # build chunks from the conditioned package -> retrieve per query -> dedupe ->
    # one valuation call with only the retrieved chunks + the same system prompt -> validate
```
- Retrieved chunk ids are stored in the run record (to separate retrieval failures from reasoning failures in E9: if the CB chunk was not retrieved, an extraction failure is a retrieval failure).
- Embeddings are cached per package hash.

### 5.3 Comparison model

Config-only: `--model comparison`. If it is a reasoning model, record reasoning-token usage separately (cost and latency). Same prompts and schema; if the provider has a structured-output mode, enable it for both models only if it was enabled for the primary model too (otherwise document the asymmetry).

### 5.4 Instruction effect

`--prompt-version v1_instr` (sha256 registered in the prereg). Compared against the main E2 condition-C runs for the same 30 firms.

### 5.5 E10 information position

`render_user_prompt(..., cb_position="front" | "middle")`:
- `front`: CB block directly after the company block.
- `middle`: CB block inserted in the middle of a long filler section. The filler is the firm's own periodic-report text sections that do not affect value (e.g., corporate governance, board meeting summaries), truncated to a fixed token length (e.g., 20k tokens) for every firm.
- Both positions use the same total text, so only the position differs.

## 6. Step-by-step tasks

1. Implement `ext_*` builders reading subsets from the prereg; dry-run all extensions; choose what fits the budget using D9.3.
2. Run structure T (agent already built in P5). QA.
3. Run the instruction effect. QA.
4. Run the comparison model. QA (check schema compliance separately for this model; a low-compliance comparison model weakens its robustness value).
5. Implement and test RAG (`test_rag.py`: retrieval returns the CB chunk for the CB query on fixtures; chunk ids logged). Run structure R. QA.
6. E10 (optional): implement the renderer option with tests (same total length; CB block position verified); run.
7. Rebuild `firm_level.parquet` with extension columns keyed by `(model_key, agent_structure, prompt_version)`; tag `data-v2`.

## 7. Tests

`test_rag.py`, `test_e10_render.py`, plus builder job-count tests.

## 8. Exit criteria & verification

- [ ] Every extension that was run has QA in `results/qa/extensions_qa.md` with validity ≥ 90% (or documented).
- [ ] Extensions not run (budget) are listed with a reason; the paper reports them as not run.
- [ ] `data-v2` tag.

## 9. Risks & fallbacks

| Risk | Fallback |
|---|---|
| RAG on a short (~8k-token) package is artificial for E2 | Report RAG mainly for E8 (long CB filings), where retrieval matters; E2 RAG results are secondary |
| Comparison model refuses or flags data often | Report refusal/flag rates; analyze the valid subset; do not tune prompts for it (prompts are frozen) |
| Budget exhausted | Follow D9.3 order; skip E10 first |

## 10. Assumptions to revalidate

- Budget remaining after P8.
- Whether structure T is primary (P7 G2), which changes the comparison set.
