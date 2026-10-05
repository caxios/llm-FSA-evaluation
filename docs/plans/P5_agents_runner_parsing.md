# P5 — Agent, Runner & Parsing Infrastructure

| Item | Value |
|---|---|
| Roadmap | R§7 |
| Weeks | 3–6 |
| Status | Ready |
| Version | v0.1 (2026-10-05) |
| Depends on | P0 (model config, prompt language); P2 Step 2.1 + renderer for end-to-end runs |
| Unlocks | P6, P7 |

## 1. Objective

Build everything between a conditioned, perturbed package and a validated, logged result row: output schema, prompt templates, LLM client, agent structures P and T, synthetic agents, JSON validation with retries, call cache, JSONL logs, experiment job builders, and a CLI runner with cost dry-runs.

## 2. Entry conditions

- `config/models.yaml` filled (P0).
- Fixture packages and a renderer available (P2 Steps 2.1 and 2.4). Before those exist, develop against a hard-coded fixture prompt.

## 3. Decisions resolved in this phase

| ID | Decision | Recommendation |
|---|---|---|
| D4 | Discounting convention in the schema | Add `calculation.discounting_convention` (`end_of_year` / `mid_year`) and `calculation.shares_used`. The prompt asks for end-of-year discounting and requires the field anyway |
| D5 | Prompt language | **Resolved 2026-10-05: Korean** |
| D5.1 | Equity bridge definition | The prompt states it explicitly: `equity_value = enterprise_value − net_debt + non_operating_assets`, `value_per_share = equity_value / shares_used`. This removes ambiguity in the self-consistency recomputation |
| D5.2 | Tool agent design | **Resolved 2026-10-05.** One structured call (extraction + assumptions + FCFF inputs + dilution decision), then deterministic Python valuation. Simpler and model-agnostic. Differs from the research plan's "3–5× tokens" multi-turn picture; update the cost estimate accordingly |
| D5.3 | Cache key input | Hash of the **fully rendered messages** (covers condition, perturbation, and template) + model id + decoding config + rep + agent structure |
| D5.4 | Retry semantics | Schema retries are part of the same rep (same cache key); attempts are logged. A rep that fails after 2 retries is stored as invalid and never re-run automatically |

## 4. Deliverables

```
src/parse/schema.py
src/parse/validate.py
src/agents/prompts/valuation_system_v1.txt
src/agents/prompts/valuation_system_v1_instr.txt     # + rule 6 (instruction condition)
src/agents/prompts/valuation_user_v1.txt
src/agents/prompts/tool_system_v1.txt
src/agents/prompts/identification_v1.txt             # E5
src/agents/prompts/memory_quiz_v1.txt                # E6
src/agents/prompts/registry.py                       # version -> file, sha256
src/agents/llm_client.py
src/agents/base.py
src/agents/plain.py
src/agents/tool.py
src/agents/valuation_tools.py
src/agents/synthetic.py
src/runner/cache.py
src/runner/logger.py
src/runner/jobs.py
src/runner/run.py
src/runner/cost.py
src/experiments/{e0_e2,e3,e5,e6,e7,e8}.py           # job builders
tests/test_schema.py
tests/test_validate.py
tests/test_valuation_tools.py
tests/test_llm_client.py
tests/test_agents.py
tests/test_cache.py
tests/test_runner.py
tests/test_job_builders.py
```

## 5. Design

### 5.1 Output schema (`src/parse/schema.py`)

Mirrors Appendix A with the D4/D5.1 additions:

```python
class Extracted(BaseModel):
    base_year: int
    unit: Literal["KRW_million"]
    revenue: float; operating_income: float; depreciation_amortization: float | None
    capex: float | None; change_in_working_capital: float | None
    cash_and_equivalents: float; total_borrowings: float; non_operating_assets: float | None
    shares_outstanding: float
    convertible_bonds_outstanding: float | None = None
    conversion_price: float | None = None

class Assumptions(BaseModel):
    revenue_growth: conlist(float, min_length=5, max_length=5)
    operating_margin: conlist(float, min_length=5, max_length=5)
    tax_rate: float; wacc: float; terminal_growth: float
    assumption_rationale: str
    @model_validator  # wacc > terminal_growth; rates given as decimals (0.08, not 8)

class Calculation(BaseModel):
    fcff: conlist(float, min_length=5, max_length=5)
    terminal_value: float; enterprise_value: float
    net_debt: float; non_operating_assets_added: float
    equity_value: float
    shares_used: float
    discounting_convention: Literal["end_of_year", "mid_year"]

class Dilution(BaseModel):
    dilution_applied: bool
    convertible_shares: float | None
    diluted_shares: float | None

class Result(BaseModel):
    value_per_share: float                     # KRW
    ev_ebitda_crosscheck_per_share: float | None

class Meta(BaseModel):
    data_anomaly_flag: bool; data_anomaly_note: str = ""; sources_used: str = ""

class ValuationOutput(BaseModel):
    extracted: Extracted; assumptions: Assumptions; calculation: Calculation
    dilution: Dilution; result: Result; meta: Meta
```
Rates are normalized: if a rate field is > 1 (e.g., `8.5`), the validator converts it to a decimal and records `normalized_percent=True`. This counts as valid output, but the event is logged.

Separate small schemas: `IdentificationOutput {guess_name: str | None, guess_ticker: str | None, confidence: float}` and `QuizOutput {q1..q6: str | float | None}` with "모른다" → `None`.

### 5.2 Prompts

- `valuation_system_v1.txt`: Appendix B rules 1–5 plus D5.1 (equity bridge) and "할인은 연말 기준(end_of_year)으로 하라". Appendix A schema embedded as a JSON example.
- `valuation_system_v1_instr.txt`: identical + rule 6.
- `valuation_user_v1.txt`: Appendix B user template; slots filled by `render_user_prompt` (P2).
- `registry.py`: `get_prompt(version) -> (text, sha256)`. The sha256 goes into every run record and the preregistration. A unit test fails if a registered file's hash changes after the `prereg-v1` tag.

### 5.3 LLM client (`src/agents/llm_client.py`)

```python
class RawResponse(BaseModel):
    text: str; model_reported: str; finish_reason: str
    tokens_in: int; tokens_out: int; latency_s: float
    created_at: datetime; request_id: str | None; refusal: bool

class LLMClient(Protocol):
    def complete(self, messages: list[dict], cfg: ModelConfig) -> RawResponse

class OpenAICompatibleClient: ...   # hosted open-weight models
class AnthropicClient: ...          # or whichever SDK the comparison model needs
def make_client(cfg: ModelConfig) -> LLMClient
```
- Concurrency: `asyncio` with a semaphore per provider (`max_concurrency` in `models.yaml`), plus a requests-per-minute limiter.
- Transient errors (429, 5xx, timeouts): exponential backoff, up to 6 attempts. Hard errors are raised.
- Refusal detection: empty content, a provider refusal flag, or a refusal phrase list (Korean + English) when no JSON is present.
- JSON mode / structured output is turned on if the provider supports it (from the P0 probe); recorded as part of the decoding config.

### 5.4 Agents

```python
class RunRequest(BaseModel):
    job_id: str
    firm_id: str; group: str; experiment: str
    condition: Literal["A", "B", "D", "C"]
    perturbation: PerturbMeta
    agent_structure: Literal["P", "T", "R", "SYN"]
    model_key: str; prompt_version: str; rep: int
    messages: list[dict]               # fully rendered
    package_hash: str

class RunRecord(BaseModel):
    request: RunRequest
    cache_key: str
    attempts: int
    valid: bool
    error: str | None
    output: ValuationOutput | None
    raw: list[RawResponse]
    code_version: str                  # git commit hash
    finished_at: datetime

class Agent(Protocol):
    def run(self, req: RunRequest) -> RunRecord
```

- **Plain (P)** — `plain.py`: send `messages`, validate with retries (§5.5), return the record.
- **Tool (T)** — `tool.py`:
  1. Call with `tool_system_v1.txt`, which asks for `extracted`, `assumptions`, FCFF inputs per year (`revenue`, `ebit`, `tax`, `d&a`, `capex`, `Δnwc`), and `dilution.dilution_applied` + `convertible_shares`.
  2. `valuation_tools.value_from_inputs(...)` computes FCFF, TV, EV, equity, per-share value, and the diluted value when `dilution_applied` (if-converted: equity + F, shares + convertible shares, then `min` with the undiluted value).
  3. Assemble a full `ValuationOutput` (calculation fields filled by the tool), `valid=True` if step 1 validated.
- **Synthetic** — `synthetic.py` (no API calls; same `Agent` protocol):
  - `OracleAgent(noise_sd=0.05)`: extracts true values from the package, applies fixed assumptions (growth 3%, margin = last-year margin, WACC 8%, g 2%), values via `valuation_tools`, multiplies the result by `exp(N(0, sd))`. Applies dilution correctly.
  - `AnchoredAgent(anchor: dict[firm_id, float])`: returns the anchor × noise.
  - `MixtureAgent(w)`: `exp(w·log V_oracle + (1−w)·log V_anchor)` × noise.
  - `NoDilutionAgent`: Oracle with `dilution_applied=False` and correctly extracted convertible shares.
  - `CalcErrorAgent`: Oracle that reports a per-share value 10% off its own calculation (tests ε and E9 "computation failure").

`valuation_tools.py` is the single canonical DCF implementation:
```python
def dcf_value(fcff: list[float], wacc: float, g: float, convention="end_of_year") -> tuple[float, float]  # (EV, TV)
def equity_bridge(ev, net_debt, non_op) -> float
def per_share(equity, shares) -> float
def if_converted(equity, shares, F, Pc) -> tuple[float, float]   # (v_conv, v_debt)
def value_from_inputs(inputs: ToolInputs) -> ValuationOutput
```

### 5.5 Validation (`src/parse/validate.py`)

```python
def extract_json(text: str) -> dict          # strips code fences; takes the outermost {...}; tolerates trailing text
def validate_output(text: str, schema=ValuationOutput) -> tuple[ValuationOutput | None, str | None]
def run_with_retries(client, messages, cfg, schema, max_retries=2) -> tuple[output, list[RawResponse], error]
    # on failure, append the assistant's reply plus a user message:
    # "출력이 스키마에 맞지 않습니다: {error}. 같은 평가 결과를 스키마에 맞는 JSON으로만 다시 출력하세요."
```
Missing-data rules (fixed now, copied into the preregistration):
- Invalid runs are excluded from all medians and regressions.
- A firm × condition × perturbation cell with < 70% valid runs is flagged `low_validity`; primary analyses keep it, and a robustness analysis drops it.
- `value_per_share <= 0` is valid output but excluded from log-based metrics; the count is reported.

### 5.6 Cache and logs

`cache.py` (SQLite, WAL mode):
```sql
CREATE TABLE calls (
  cache_key TEXT PRIMARY KEY,
  experiment TEXT, firm_id TEXT, model_key TEXT, prompt_version TEXT,
  record_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```
`cache_key = stable_hash({messages, model_id, decoding, rep, agent_structure, schema_version})`.
API: `get(key) -> RunRecord | None`, `put(record)`. Writes are transactional, so an interrupted run never leaves half-written rows.

`logger.py`: appends every `RunRecord` (including cache misses only — cache hits are not re-logged) to `results/runs/{experiment}/{YYYYMMDD}.jsonl`.

### 5.7 Jobs and runner

`src/runner/jobs.py`:
```python
class JobSpec(BaseModel):
    experiment: str; firm_ids: list[str]; conditions: list[str]
    perturbations: list[tuple[str, dict]]; reps: int | dict[str, int]
    agent_structure: str; model_key: str; prompt_version: str
def expand(spec: JobSpec, packages, conditions_store) -> Iterator[RunRequest]
```

`src/experiments/*.py` — one builder per module, each returning `JobSpec`s from config:

| Builder | Produces |
|---|---|
| `e0_e2.py` | Conditions × k grid × reps (k=1 cells are E0) |
| `e3.py` | Cash / shares / non-operating, using `SizeDecision`s from `sizing.py` and the 2/5/10% tiers |
| `e5.py` | Identification prompts for A/B/D at k ∈ {1, 1.5}, 3 reps |
| `e6.py` | Memory quiz per firm, 3 reps (no package) |
| `e7.py` | Conditions A and C for E7 candidates (reuses E2 k=1 runs when cached) |
| `e8.py` | CB V0–V4 for S firms |

`src/runner/run.py` CLI:
```
python -m src.runner.run --experiment E2 --groups L,M,S --conditions A,B,D,C \
    --model primary --agent P [--firms L001,L002] [--reps 10] [--limit 50] \
    [--dry-run] [--tag pilot]
```
Flow: build specs → expand to requests → split into cached / to-run → if `--dry-run`, print counts + cost estimate (`cost.py`, using mean token counts from the cache if available, else a configured default) and exit → otherwise run concurrently, cache, log → write/refresh `results/runs/{experiment}.parquet` (flattened run-level table, one row per record).

Run-level table columns:
`job_id, cache_key, experiment, tag, firm_id, group, condition, perturbation_type, perturbation_params (json), agent_structure, model_key, model_reported, prompt_version, prompt_sha, rep, valid, error, attempts, value_per_share, equity_value, shares_used, net_debt, enterprise_value, wacc, terminal_growth, dilution_applied, convertible_shares, anomaly_flag, tokens_in, tokens_out, latency_s, code_version, finished_at, output_json`.

## 6. Step-by-step tasks

1. **Schema** + tests (valid Appendix A example passes; missing fields fail; percent normalization; WACC ≤ g fails). Commit.
2. **valuation_tools** + tests (hand-computed DCF example for both conventions; if-converted worked example from §E8: E=100bn, N=10m, F=20bn, Pc=8,000 → 9,600). Commit.
3. **validate.py** + tests (code fences, trailing prose, nested JSON, retry flow with a fake client that fails then succeeds, final failure). Commit.
4. **Prompts + registry** + tests (files load; hashes recorded; template slots all filled for a fixture). Commit.
5. **LLM client** with a `FakeClient` for tests; real adapters smoke-tested manually with one call each (`scripts/smoke_llm.py`). Commit.
6. **Cache + logger** + tests (same request → same key; changing one message character → different key; transactional put; resume after a simulated crash). Commit.
7. **Plain agent** + tests with `FakeClient`. Commit.
8. **Tool agent** + tests (FakeClient returns tool inputs; record has tool-computed calculation; dilution path). Commit.
9. **Synthetic agents** + tests (Oracle reproduces `valuation_tools` exactly at zero noise; Anchored ignores the package). Commit.
10. **Jobs, builders, runner, cost** + tests (job counts per builder match the formulas; dry-run makes zero client calls; second run is 100% cache hits; parquet columns present). Commit.
11. **End-to-end smoke** with the real primary model: E2, condition C, 3 fixture firms, k ∈ {1, 2}, 2 reps (12 calls). Inspect the outputs by hand.

## 7. Tests

All tests use `FakeClient` or synthetic agents; no network. Coverage target ≥ 85% for `src/parse`, `src/agents`, `src/runner`.

## 8. Exit criteria & verification

- [ ] Smoke run produces 12 valid records with populated intermediate fields.
- [ ] Re-running the smoke command: 0 API calls, identical parquet output.
- [ ] `--dry-run` for the full main design prints a job count matching R§10 (±5%).
- [ ] Synthetic agents run through the same runner path as real agents.

## 9. Risks & fallbacks

| Risk | Fallback |
|---|---|
| Primary model often omits intermediate fields | Provider JSON/structured mode; simplify optional fields; move to tool agent (gate G2) |
| Provider silently updates the model behind an id | Log `model_reported` per call; the runner halts a batch if it changes mid-batch |
| Long CB prompts exceed the context window | Truncate non-CB filing boilerplate in the renderer (same rule for V0–V4) |
| Rate limits slow the main run | Concurrency tuning; spread across days; second provider for the same weights only if outputs are shown to be equivalent on a pilot subset (otherwise do not mix) |
