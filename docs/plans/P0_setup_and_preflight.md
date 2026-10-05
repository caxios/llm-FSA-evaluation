# P0 — Project Setup & Pre-flight Checks

| Item | Value |
|---|---|
| Roadmap | R§2 |
| Weeks | 1–2 |
| Status | Ready |
| Version | v0.1 (2026-10-05) |
| Depends on | — |
| Unlocks | P1, P5 |

## 1. Objective

Stand up the repository and settle every external fact the pipeline depends on before any pipeline code is written: which data fields exist, which model is primary, what its training cutoff is, and which evaluation dates follow from that.

## 2. Entry conditions

- OpenDART API key issued (https://opendart.fss.or.kr).
- KRX Open API key requested (approval can take days, so request on day 1).
- At least one hosted inference account for open-weight models, and one commercial API account for the comparison model.

## 3. Decisions resolved in this phase

| ID | Decision | Input needed |
|---|---|---|
| D1 | `T_post` (FY2024 vs FY2025 annual reports) and `T_pre` | Verified training cutoff of the primary model. Rule fixed 2026-10-05: ≥ 3 months after the cutoff, prefer FY2025 (April 2026) |
| D5 | Prompt language | **Resolved 2026-10-05: Korean** |
| D0.1 | Primary open-weight model and hosting provider | Price, pinnable version, context length |
| D0.2 | Comparison model | Reasoning vs non-reasoning, price |
| D0.3 | Price source (KRX vs yfinance) and adjustment convention | Probe results |
| D0.4 | Listing/market-cap source (KRX Open API vs pykrx) | Probe results; pykrx breakage risk |
| D0.5 | Industry classification source (DART `induty_code` KSIC vs KRX sector) | Probe results |
| D0.6 | Source for administrative-issue / trading-halt flags | Probe results |

## 4. Deliverables

```
pyproject.toml
ruff.toml (or [tool.ruff] in pyproject)
.env.example
.gitignore
README.md                        # stub: purpose, setup, layout
config/models.yaml
config/sample.yaml
config/experiments.yaml
config/budget.yaml
src/__init__.py
src/config.py
src/utils/{__init__,io,hashing,logging}.py
scripts/probes/probe_dart_fs.py
scripts/probes/probe_dart_filings.py
scripts/probes/probe_dart_cb.py
scripts/probes/probe_dart_document.py
scripts/probes/probe_dart_shares.py
scripts/probes/probe_krx.py
scripts/probes/probe_prices.py
scripts/probes/probe_model.py
tests/test_config.py
tests/test_utils.py
tests/fixtures/...               # sample responses saved by probes
docs/decisions_log.md
docs/preregistration.md          # skeleton only
docs/data_access_memo.md
docs/literature_check.md
```

## 5. Design

### 5.1 Directory layout

Created at the repository root (`llm-FSA-evaluation/`), following §9.2 with these additions: `src/utils/`, `src/experiments/` (job builders, filled in P5), `scripts/`, `docs/plans/`.

### 5.2 Configuration schema (`src/config.py`)

```python
class ModelConfig(BaseModel):
    key: str                    # "primary", "comparison"
    provider: Literal["openai_compatible", "anthropic", "openai", "google"]
    model_id: str
    base_url: str | None
    training_cutoff: date
    cutoff_source: HttpUrl
    reasoning: bool
    temperature: float = 0.3
    max_output_tokens: int = 4096
    price_in_per_mtok: float    # USD per 1M input tokens
    price_out_per_mtok: float
    context_window: int

class SampleConfig(BaseModel):
    t_post: date
    t_pre: date
    groups: dict[Literal["L", "M", "S"], GroupSpec]
    exclusions: ExclusionSpec   # KSIC prefixes, admin-issue, halt, impairment, min_years=3
    seed: int = 20261019

class ExperimentsConfig(BaseModel):
    k_grid: list[float] = [0.5, 0.8, 1.0, 1.25, 2.0]
    n_default: int = 10
    n_min: int = 5
    n_max: int = 40
    target_se: float = 0.1      # s*
    tiers: list[float] = [0.02, 0.05, 0.10]
    share_multiplier: float = 2.0
    bootstrap_reps: int = 1000

class BudgetConfig(BaseModel):
    total_usd: float
    reserved_extensions_usd: float

def load_config(root: Path = Path("config")) -> Config: ...
```

All other modules read configuration only through `load_config()`.

### 5.3 Shared utilities

- `src/utils/hashing.py`: `canonical_json(obj) -> str` (sorted keys, no whitespace, floats via `repr`), `stable_hash(obj) -> str` (sha256 hex of `canonical_json`). Used for package hashes and cache keys.
- `src/utils/io.py`: `write_raw(path, payload, meta)` writes the payload plus a sidecar `<name>.meta.json` (`url`, `params` with secrets removed, `fetched_at` UTC ISO, `status`). `read_raw(path)`. `atomic_write(path, bytes)` (write to temp file, then rename).
- `src/utils/logging.py`: standard `logging` setup; one log file per script run under `logs/`.

### 5.4 Decisions log format (`docs/decisions_log.md`)

```markdown
## D1 — T_post selection
- Date: 2026-10-xx
- Phase: P0
- Options considered: ...
- Decision: ...
- Reason: ...
- Affects: config/sample.yaml, P2, P8
```

## 6. Step-by-step tasks

### Step 0.1 — Scaffold (day 1)
1. Create the directory tree with `__init__.py` files under `src/`.
2. `pyproject.toml`: project metadata, Python `>=3.11`, dependencies from R§2 P0.1, optional `[dev]` extras (`pytest`, `ruff`, `hypothesis`).
3. `.gitignore`: `.env`, `data/raw/`, `data/processed/`, `results/runs/`, `*.sqlite`, `logs/`, `__pycache__/`, `.venv/`.
4. `.env.example` with `DART_API_KEY=`, `KRX_API_KEY=`, `PRIMARY_API_KEY=`, `COMPARISON_API_KEY=`.
5. `README.md` stub.
6. Verify: `pip install -e .[dev]`, `ruff check .`, `pytest` (0 tests) all succeed.
7. Commit: "Scaffold project layout".

### Step 0.2 — Config loader (day 1–2)
1. Implement `src/config.py` (§5.2).
2. Write YAML files with placeholder values; mark unknowns with `TODO` comments.
3. `tests/test_config.py`: valid files load; missing fields raise; `temperature` outside [0, 2] raises; `t_pre < t_post` enforced.
4. Commit.

### Step 0.3 — Utilities (day 2)
1. Implement `hashing.py`, `io.py`, `logging.py`.
2. `tests/test_utils.py`: `stable_hash` is order-independent for dicts and stable across runs (golden value); `write_raw` produces the sidecar and redacts `crtfc_key`; `atomic_write` leaves no partial file if interrupted (simulate with an exception).
3. Commit.

### Step 0.4 — Docs templates (day 2)
`decisions_log.md`, `preregistration.md` (headings: hypotheses, sample, measures, perturbation sizes, n, analysis, exclusions, missing data, deviations), `data_access_memo.md`, `literature_check.md`. Commit.

### Step 0.5 — Data probes (days 3–6)

Each probe is a standalone script that (a) calls the live API for 2–3 known firms, (b) prints a short summary, and (c) saves trimmed sample responses to `tests/fixtures/<source>/` for P1 parser tests. Use firms that cover the edge cases: a large KOSPI firm with preferred shares (e.g., Samsung Electronics), a mid-cap, and a KOSDAQ firm with an outstanding CB.

| Probe | Endpoint(s) to verify | Questions to answer in the memo |
|---|---|---|
| `probe_dart_fs.py` | `fnlttSinglAcntAll.json` (`reprt_code=11011`, `fs_div=CFS`/`OFS`) | Does one annual call return three years (`thstrm`, `frmtrm`, `bfefrmtrm`) for BS, IS/CIS, and CF? How consistently is `account_id` populated with IFRS taxonomy IDs vs `-표준계정코드 미사용-`? Is EPS present as a line? Are amounts in KRW? Coverage for FY2022–FY2025? |
| `probe_dart_filings.py` | `list.json` | Max date window without `corp_code` (expected 3 months); page size limit; how to filter major-event reports (`pblntf_ty=B`) and exchange disclosures (`pblntf_ty=I`); exact `report_nm` strings for CB issuance and conversion-price adjustment |
| `probe_dart_cb.py` | `cvbdIsDecsn.json` (CB issuance decision) | Exact fields: face amount, conversion price, refixing floor, conversion period, maturity, call/put terms. Is the outstanding balance available from any structured endpoint? (Check the periodic-report key-info APIs for unredeemed bond balances; expected: none specific to CBs.) |
| `probe_dart_document.py` | `document.xml` | Archive format; encoding; can the "unredeemed convertible bond" table be located by header keywords? Record the table headers seen |
| `probe_dart_shares.py` | `stockTotqySttus.json`, `alotMatter.json`, `company.json`, `otrCprInvstmntSttus.json` | Issued/treasury/outstanding by share class; DPS; `induty_code` (KSIC); names of invested companies (used for redaction in P4) |
| `probe_krx.py` | KRX Open API and `pykrx` (`get_market_ticker_list`, `get_market_cap`, sector functions) | Historical listing and market cap as of arbitrary past dates? Does pykrx still work without login? Is there a source for administrative-issue and halt flags as of a past date? |
| `probe_prices.py` | KRX daily prices, `yfinance` `.KS`/`.KQ` | Adjusted vs unadjusted availability, history depth, agreement between sources on 3 tickers (difference table) |

Also record OpenDART's daily call quota and observed latency.

Commit after each probe script, together with its fixtures.

### Step 0.6 — Model probes (days 5–8)
1. Shortlist 2–3 open-weight candidates with an officially documented training cutoff (e.g., Llama 4 Scout, documented cutoff Aug 2024). For each, record the cutoff source URL, hosting providers, price, context window, and whether a version/date-pinned model id exists.
2. `probe_model.py`: send one realistic valuation prompt (hand-built from the Samsung fixture, Appendix B system prompt, Appendix A schema) 5 times to each candidate, in Korean (D5). Record: JSON parse success, schema validity (temporary pydantic model), tokens in/out, latency, and whether intermediate values are populated.
3. Pick the primary model (D0.1) and comparison model (D0.2); fill `config/models.yaml`.
4. Resolve D1: `T_post` must be after the cutoff with a margin of at least 3 months; prefer the later of the FY2024/FY2025 annual-report dates if FY2025 data coverage is complete. `T_pre` = first trading day after the annual-report deadline (end of March) in a year before the cutoff (e.g., 2023-04-03).
5. D5 is already resolved (Korean). If no candidate reaches acceptable JSON compliance in Korean, raise it as a decision before choosing the model.

### Step 0.7 — Literature check (parallel, days 1–10)
Complete the §16 checklist items. For each paper, record in `docs/literature_check.md`: citation, what it does, overlap with this study (none / partial / major), and the differentiation note. A "major" overlap triggers a design review before P1 starts.

### Step 0.8 — Close-out (day 10)
1. Write each resolved decision (D0.x, D1, D5) into `decisions_log.md`.
2. Update `config/*.yaml` and remove all `TODO`s that P0 was supposed to resolve.
3. Update the P1 and P2 plans with probe findings (field names, workarounds).
4. Tick P0 in the roadmap checklist.

## 7. Tests

| Test file | Covers |
|---|---|
| `tests/test_config.py` | Loading, validation errors, cross-field checks |
| `tests/test_utils.py` | Hash stability, raw writes with sidecar, secret redaction, atomic writes |

Probes are not tests; they are run manually and are not part of `pytest`.

## 8. Exit criteria & verification

- [ ] `pip install -e .[dev] && ruff check . && pytest` succeeds on a clean checkout.
- [ ] `docs/data_access_memo.md` has an entry for every data item in §8, each marked **available**, **workaround** (with the workaround described), or **unavailable** (with the impact on the design).
- [ ] `config/models.yaml` has a verified cutoff URL for the primary model; `config/sample.yaml` has final `t_post` and `t_pre`.
- [ ] Fixtures exist for every endpoint that P1 will parse.
- [ ] Literature check has no unresolved "major" overlap.

## 9. Risks & fallbacks

| Risk | Fallback |
|---|---|
| pykrx no longer works without a KRX login | Use the KRX Open API; if its approval is delayed, use yfinance for prices and DART `stockTotqySttus` × price for market cap |
| No structured outstanding-CB balance | Parse the periodic report table (P1.4); budget extra time in P1 |
| No open-weight model with a clearly documented cutoff | Use the model with the best-documented cutoff and add an empirical cutoff check: quiz the model on dated events/prices around the claimed cutoff and record the results |
| KRX key approval delay | Start P1 with DART-only stages; KRX stages last |
| Probe model JSON compliance is poor | Test the provider's JSON mode / structured-output option; record it as a decoding setting |
