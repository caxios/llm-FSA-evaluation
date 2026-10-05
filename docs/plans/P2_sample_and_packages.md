# P2 — Sample Selection & Input Packages

| Item | Value |
|---|---|
| Roadmap | R§4 |
| Weeks | 4–5 |
| Status | Ready (account IDs depend on P0/P1 findings) |
| Version | v0.1 (2026-10-05) |
| Depends on | P1 raw data |
| Unlocks | P3, P4 (schema only, after Step 2.1), P7 |

## 1. Objective

Turn raw DART/KRX data into (a) the 150-firm sample, (b) one standardized, accounting-consistent **input package** per firm, (c) a deterministic renderer that produces the prompt text, and (d) ground-truth tables for CB, memory quiz, and stale-anchor experiments.

**Step 2.1 (package schema) is the critical path.** Freeze it first so P3 and P4 can start on fixtures in parallel.

## 2. Entry conditions

- P1 exit criteria met; `data/processed/universe_{t_post}.parquet` exists.

## 3. Decisions resolved in this phase

| ID | Decision | Recommendation |
|---|---|---|
| D7 | Firms whose reported statements fail identities | Add an explicit "other (reconciling)" line if the gap is < 0.5% of total assets; otherwise exclude and record |
| D8 | "Newsworthiness" proxy for mid-cap selection | **Resolved 2026-10-05.** Count of DART filings in the 12 months before `t_post` (cheap, reproducible). An optional news count is robustness only |
| D2.1 | Line-item granularity in packages | Keep **all reported lines** (so the statements look like real filings), tagged with canonical IDs where mapped |
| D2.2 | Notes summary source | **Resolved 2026-10-05.** Derive from BS lines (borrowings breakdown, non-operating assets), not from parsed note text. Document as a limitation |
| D2.3 | Share class handling | Store common and preferred counts separately; render both. Metrics use the share count the agent reports (P6), so no single convention is imposed |
| D2.4 | Internal unit and rounding | Internal: float, KRW million, unrounded. Rendered: integer KRW million |
| D2.5 | M-group rank band | **Resolved 2026-10-05.** KOSPI market-cap ranks 101–400 after exclusions |

## 4. Deliverables

```
src/data/package_schema.py
src/data/account_map.py
config/account_map.yaml          # IFRS/DART account_id -> canonical; name synonyms
config/industry_labels.yaml      # KSIC division -> generic Korean label (used in P4)
src/data/sample.py
src/data/package_builder.py
src/data/render.py
src/data/ground_truth.py
src/perturb/consistency.py       # check_identities() is owned here (shared with P3)
scripts/build_packages.py
tests/test_package_schema.py
tests/test_account_map.py
tests/test_package_builder.py
tests/test_render.py
tests/fixtures/packages/*.json   # 5 hand-checked packages for P3/P4/P6 development
data/processed/sample.parquet
data/processed/packages/{firm_id}.json
data/ground_truth/{cb_truth,quiz_truth,anchor_prices}.parquet
docs/sample_report.md            # generated
```

## 5. Design

### 5.1 Package schema (`src/data/package_schema.py`)

```python
Kind = Literal["monetary", "count", "ratio", "per_share"]
Year = int

class LineItem(BaseModel):
    line_id: str                   # stable within package, e.g. "bs_012"
    label: str                     # Korean label as reported (may be redacted in P4)
    canonical: str | None          # e.g. "cash", "total_assets"; None if unmapped
    kind: Kind = "monetary"
    values: dict[Year, float | None]
    order: int                     # display order (from DART `ord`)
    indent: int = 0                # display depth

class Statement(BaseModel):
    code: Literal["BS", "IS", "CF"]
    lines: list[LineItem]
    def get(self, canonical: str) -> LineItem
    def value(self, canonical: str, year: Year) -> float

class ShareInfo(BaseModel):
    common_issued: float
    common_treasury: float
    preferred_issued: float = 0
    preferred_treasury: float = 0
    @property
    def common_outstanding(self) -> float

class PerShare(BaseModel):
    eps: dict[Year, float | None]          # basic EPS, KRW
    dps_common: dict[Year, float | None]   # KRW

class CBInstrument(BaseModel):
    series: str
    face_outstanding: float                # KRW million
    conversion_price: float                # KRW per share
    refix_floor: float | None
    maturity: date | None
    complex_terms: bool                    # call option / net settlement etc.

class CBBlock(BaseModel):
    instruments: list[CBInstrument]
    filing_text: str                       # rendered CB disclosure text (Korean)
    outstanding_table_text: str

class PackageMeta(BaseModel):
    firm_id: str                           # "L001".."L050", "M001".., "S001"..
    corp_code: str
    ticker: str
    real_name: str
    ksic: str
    industry_label: str
    group: Literal["L", "M", "S"]
    market: Literal["KOSPI", "KOSDAQ"]
    eval_date: date
    source_rcept_no: str
    fs_div: Literal["CFS", "OFS"]

class InputPackage(BaseModel):
    schema_version: str = "1.0"
    meta: PackageMeta
    unit: Literal["KRW_million"] = "KRW_million"
    years: list[Year]                      # ascending, length 3
    bs: Statement
    is_: Statement = Field(alias="is")
    cf: Statement
    per_share: PerShare
    shares: ShareInfo
    notes: NotesSummary
    cb: CBBlock | None = None
    def package_hash(self) -> str          # stable_hash of model_dump(mode="json")
```

`NotesSummary` contains `borrowings: list[(label, amount)]` and `non_operating_assets: list[(label, amount)]` for the latest year, each item pointing at the `line_id` it was derived from (so perturbations stay consistent).

### 5.2 Canonical IDs required in every package

| Statement | Required canonical IDs |
|---|---|
| BS | `cash`, `current_assets`, `non_current_assets`, `total_assets`, `current_liabilities`, `non_current_liabilities`, `total_liabilities`, `retained_earnings`, `other_equity` (or `oci_reserve`), `equity_owners`, `non_controlling_interest`, `total_equity`, `total_liabilities_and_equity` (if reported), plus every borrowing line (`short_term_borrowings`, `current_portion_ltd`, `bonds`, `convertible_bonds`, `long_term_borrowings`, `lease_liabilities`) and non-operating asset lines (`fvpl_financial_assets`, `fvoci_financial_assets`, `investments_in_associates`, `investment_property`) where present |
| IS | `revenue`, `operating_income`, `pretax_income`, `income_tax`, `net_income`, `net_income_owners`, `eps_basic` (kind `per_share`), `interest_income`, `interest_expense` if present |
| CF | `cfo`, `depreciation_amortization` (if reported, else derived from notes-free proxy and flagged), `capex_ppe`, `capex_intangibles`, `cfi`, `dividends_paid`, `cff`, `net_change_in_cash`, `beginning_cash`, `ending_cash`, `fx_effect_on_cash` |

`config/account_map.yaml` lists, for each canonical ID, the DART `account_id` values (e.g., `ifrs-full_CashAndCashEquivalents`, `ifrs-full_Assets`, `ifrs-full_Revenue`, `dart_OperatingIncomeLoss`, `ifrs-full_ProfitLossAttributableToOwnersOfParent`, `ifrs-full_IncreaseDecreaseInCashAndCashEquivalents`, ...) and a list of Korean label synonyms for rows with `-표준계정코드 미사용-`. The final list comes from the P0/P1 fixtures.

### 5.3 Ancestry map (shared with P3)

`config/ancestry.yaml` defines which subtotal lines must move when a leaf changes, e.g.:

```yaml
cash: [current_assets, total_assets]
fvoci_financial_assets: [non_current_assets, total_assets]
retained_earnings: [equity_owners, total_equity, total_liabilities_and_equity]
other_equity: [equity_owners, total_equity, total_liabilities_and_equity]
convertible_bonds: [non_current_liabilities, total_liabilities, total_liabilities_and_equity]
dividends_paid: [cff, net_change_in_cash, ending_cash]
```
Where the leaf is current vs non-current varies by firm (e.g., convertible bonds), the builder records the actual parent per package in `LineItem` metadata, and the map is resolved per package.

### 5.4 Identity checks (`src/perturb/consistency.py`)

```python
@dataclass
class IdentityViolation:
    check: str; year: int; lhs: float; rhs: float; gap: float

def check_identities(pkg: InputPackage, rel_tol: float = 1e-6, abs_tol: float = 1.0) -> list[IdentityViolation]
```
Checks per year:
1. `total_assets == total_liabilities + total_equity`
2. `total_equity == equity_owners + non_controlling_interest`
3. `current_assets + non_current_assets == total_assets` (and the liability analogue)
4. `ending_cash == beginning_cash + net_change_in_cash + fx_effect_on_cash`, and `ending_cash == bs.cash` (same year)
5. `beginning_cash[y] == ending_cash[y-1]`
6. `eps_basic ≈ net_income_owners / weighted common shares` — reported data only matches approximately, so this check uses a loose tolerance (2%) and is applied to *changes* introduced by perturbations rather than to the raw package (see P3)

Tolerances are absolute in KRW million (`abs_tol=1.0` covers rounding of the source data, which is in KRW).

### 5.5 Renderer (`src/data/render.py`)

```python
def render_financials(pkg) -> str        # three statements, all lines, integer KRW million, indented
def render_share_info(pkg) -> str
def render_notes(pkg) -> str
def render_additional_filings(pkg, include_cb: bool) -> str
def render_company_block(pkg, condition: Literal["A","B","D","C"], fake_name: str | None) -> str
def render_user_prompt(pkg, condition, fake_name=None, include_cb=False, template_version="v1") -> str
```
Rendering is deterministic (same package → identical string), uses fixed column order (Y-2, Y-1, Y), thousands separators, and negative numbers as `-1,234`. The company block keeps the same structure in every condition (see P4 §5.3).

### 5.6 Sample selection (`src/data/sample.py`)

```python
def apply_exclusions(universe: pd.DataFrame, cfg: SampleConfig) -> pd.DataFrame
    # adds boolean columns: excl_financial (KSIC 64–66), excl_admin, excl_halt,
    # excl_impairment (prior-year total_equity < paid-in capital or <0), excl_no_3y
def select_large(df, n=50) -> pd.DataFrame        # top-n KOSPI by market cap (common tickers only)
def select_mid(df, n=50, band=(101, 400), seed) -> pd.DataFrame
def select_small(df, cb_truth, n=50, seed) -> pd.DataFrame
```
- **Mid**: split the band into 5 market-cap quintiles; within each quintile, sort by newsworthiness (D8) and pick 5 from the top and 5 from the bottom tercile at random (seeded). This guarantees cap-matched high/low-newsworthiness contrasts.
- **Small**: KOSDAQ, non-excluded, at least one outstanding CB with `conversion_price < price_on(t_post)`. Rank by (plain CB first, then larger dilution potential `convertible_shares / common_outstanding`), take 50; tag `cb_complex`.
- Output columns: `firm_id, group, corp_code, ticker, name, market_cap, newsworthiness, ksic, selection_reason, cb_complex`.

### 5.7 Ground truth (`src/data/ground_truth.py`)

| Table | Columns | Source |
|---|---|---|
| `cb_truth` | firm_id, series, face_outstanding (KRW mn), conversion_price, convertible_shares, as_of, source_rcept_no | P1 CB table + refixings |
| `quiz_truth` | firm_id, eval_date, market_cap, revenue_prev, op_income_prev, price, main_business, market | KRX + packages; `main_business` from DART company info + manual short label |
| `anchor_prices` | firm_id, p_old (at model cutoff), p_new (at `t_post`), log_diff, e7_candidate | PriceClient |

`e7_candidate = |log(p_new / p_old)| >= 0.30`. E7 uses `t_post` packages for these firms; `p_old` enters only as a regressor (see D7.4 in P7 on the role of `T_pre`).

## 6. Step-by-step tasks

### Step 2.1 — Package schema & fixtures (days 1–2) ⟵ critical path
1. Implement `package_schema.py`, `consistency.py`, `config/ancestry.yaml`.
2. Hand-build 5 fixture packages in `tests/fixtures/packages/` from P0/P1 fixture data: one large cap with preferred shares, one mid cap, one small cap with a plain CB, one small cap with a complex CB, one firm with unmapped custom accounts. Verify each against the DART viewer by hand.
3. Tests: round-trip JSON; `package_hash` stable; `check_identities` passes on fixtures and catches a deliberately broken copy.
4. Commit and **announce the schema freeze** (P3/P4 start).

### Step 2.2 — Account mapping (days 2–4)
1. Draft `config/account_map.yaml` from the account IDs seen across the full P1 download (`scripts/account_inventory.py` lists every `account_id`/`account_nm` with frequencies).
2. Implement `account_map.py`: map by `account_id`, then by label synonym, else `canonical=None`.
3. Report unmapped required IDs per firm.
4. Tests on fixtures. Commit.

### Step 2.3 — Package builder (days 4–6)
1. `build_package(corp_code, eval_date) -> InputPackage`: load raw FS, map accounts, convert KRW→KRW million, assemble statements with `order`/`indent`, attach shares, EPS, DPS, notes summary, CB block (S group only).
2. Apply D7: run `check_identities`; add a reconciling line or mark excluded.
3. Tests. Commit.

### Step 2.4 — Renderer (day 6)
Implement `render.py`; golden-file tests (rendered text for each fixture stored under `tests/fixtures/rendered/`). Commit.

### Step 2.5 — Sample selection (days 6–8)
1. Build packages for the whole universe (needed to evaluate `excl_no_3y` and `excl_impairment`).
2. Run selection; write `sample.parquet`.
3. Generate `docs/sample_report.md`: counts per exclusion, group descriptives (market cap, KSIC divisions), mid-group newsworthiness contrast per quintile, small-group CB characteristics.
4. Commit code (not data).

### Step 2.6 — Ground truth (days 8–9)
Implement `ground_truth.py`; generate the three tables; spot-check 10 CB rows by hand against the DART viewer. Commit.

### Step 2.7 — Close-out (day 10)
`scripts/build_packages.py` reproduces Steps 2.3–2.6 end to end. Record D7, D8, D2.x. Update P3/P4/P5 plans if field names changed.

## 7. Tests

| Test file | Key cases |
|---|---|
| `test_package_schema.py` | Round trip, hash stability, accessor errors for missing canonical IDs |
| `test_account_map.py` | ID mapping, label-synonym fallback, unmapped reporting |
| `test_package_builder.py` | Units converted; years ascending; identities pass on fixtures; reconciling-line rule |
| `test_render.py` | Golden files; determinism; negative numbers; company-block structure identical across conditions |
| `test_consistency.py` | Each identity detects a targeted violation |

## 8. Exit criteria & verification

- [ ] 150 packages in `data/processed/packages/`, all with zero identity violations.
- [ ] Every package has all required canonical IDs (or a documented, tested exception).
- [ ] `sample_report.md` shows 50/50/50 and the mid-group newsworthiness contrast.
- [ ] `cb_truth` covers ≥ 30 in-the-money small caps (gate G5 pre-check) and 10 rows were hand-verified.
- [ ] Rendered prompt for each fixture reviewed by a human for readability.

## 9. Risks & fallbacks

| Risk | Fallback |
|---|---|
| Fewer than 50 ITM small caps | Widen the CB filing window; relax "plain CB" preference; accept a smaller S group (≥ 30) and adjust power expectations |
| Many custom (unmapped) accounts break required IDs | Extend synonyms; for subtotals, compute from leaves and add as derived lines flagged `derived=True` |
| D&A not reported as a CF line | Use the IS/CF supplementary line if present; else flag and let the agent work without it (it is an input, not a required metric field) |
| Mid-cap newsworthiness proxy is weakly related to memory | Not fatal: H2b uses measured $M_i$, not the proxy. The proxy only diversifies the sample |

## 10. Assumptions to revalidate

- Canonical ID list and account IDs (P1 inventory).
- Ancestry relationships per firm (current vs non-current placement of CBs).
- M-group rank band 101–400 gives enough spread in $M_i$ (check after the pilot quiz).
