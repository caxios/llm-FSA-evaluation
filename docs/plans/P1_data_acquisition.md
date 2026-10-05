# P1 — Data Acquisition

| Item | Value |
|---|---|
| Roadmap | R§3 |
| Weeks | 3–4 |
| Status | Ready (endpoint details depend on P0 probe results) |
| Version | v0.1 (2026-10-05) |
| Depends on | P0 (keys, data-access memo, fixtures, `t_post`/`t_pre`) |
| Unlocks | P2 |

## 1. Objective

Build idempotent, rate-limited clients for OpenDART, KRX, and prices. Use them to fetch the raw data for the full candidate universe into `data/raw/`, reproducibly via one script.

## 2. Entry conditions

- `docs/data_access_memo.md` complete; D0.3–D0.6 resolved.
- Fixtures in `tests/fixtures/{dart,krx,prices}/`.
- `config/sample.yaml` has final `t_post`, `t_pre`.

## 3. Decisions resolved in this phase

| ID | Decision | Recommendation |
|---|---|---|
| D1.1 | Three-year statements from one annual report vs one report per year | One report (the latest annual report before the evaluation date), using `thstrm`/`frmtrm`/`bfefrmtrm`. This keeps restated prior years consistent with the current year. Fall back to the prior-year report only for a missing `bfefrmtrm` column |
| D1.2 | How far back to search CB filings | 6 years before `t_post` (covers typical 3–5 year CB maturities) |
| D1.3 | Candidate universe size for financial-statement fetching | All non-financial KOSPI firms + KOSDAQ firms with at least one CB issuance filing in the D1.2 window |

## 4. Deliverables

```
src/data/dart_client.py
src/data/krx_client.py
src/data/price_client.py
src/data/rate_limit.py
src/data/cb_collect.py
src/data/cb_parser.py
scripts/fetch_all.py
tests/test_dart_client.py
tests/test_krx_client.py
tests/test_price_client.py
tests/test_cb_parser.py
data/raw/...                      # not committed
data/processed/universe_{date}.parquet
docs/data_coverage_report.md      # generated
```

## 5. Design

### 5.1 Raw storage layout

```
data/raw/
├── dart/
│   ├── corpCode/corpCode_{fetch_date}.xml
│   ├── company/{corp_code}.json
│   ├── fs/{corp_code}/{bsns_year}_{reprt_code}_{fs_div}.json
│   ├── filings/{bgn_de}_{end_de}_{pblntf_ty}_p{page}.json
│   ├── cb_decision/{corp_code}_{bgn_de}_{end_de}.json
│   ├── shares/{corp_code}/{bsns_year}_{reprt_code}.json
│   ├── dividends/{corp_code}/{bsns_year}_{reprt_code}.json
│   ├── investments/{corp_code}/{bsns_year}_{reprt_code}.json
│   └── documents/{rcept_no}/         # extracted archive contents
├── krx/
│   ├── listing/{market}_{YYYYMMDD}.parquet
│   ├── sector/{market}_{YYYYMMDD}.parquet
│   └── flags/{YYYYMMDD}.parquet
└── prices/{ticker}.parquet
```

Every file has a sidecar `.meta.json` written by `src.utils.io.write_raw`.

### 5.2 Rate limiting (`src/data/rate_limit.py`)

```python
class RateLimiter:
    def __init__(self, per_second: float, daily_quota: int | None, state_path: Path): ...
    def acquire(self) -> None        # blocks; raises QuotaExhausted when the daily count is reached
```
The daily counter is persisted in `state_path` (keyed by local date), so restarting a script does not reset it. OpenDART: ~5 requests/second, daily quota from the P0 memo (expected 20,000/key).

### 5.3 `DartClient`

```python
class DartClient:
    def __init__(self, api_key: str, raw_root: Path, limiter: RateLimiter, refresh: bool = False): ...

    def corp_codes(self) -> pd.DataFrame
        # corp_code, corp_name, corp_eng_name, stock_code, modify_date
    def company(self, corp_code: str) -> dict
        # corp_name, corp_name_eng, stock_name, ceo_nm, corp_cls, induty_code, adres, hm_url, est_dt
    def financial_statements(self, corp_code: str, bsns_year: int,
                             reprt_code: str = "11011", fs_div: str = "CFS") -> pd.DataFrame
        # rcept_no, sj_div, account_id, account_nm, account_detail, ord,
        # thstrm_amount, frmtrm_amount, bfefrmtrm_amount, currency
    def search_filings(self, bgn_de: date, end_de: date, corp_code: str | None = None,
                       pblntf_ty: str | None = None, pblntf_detail_ty: str | None = None) -> pd.DataFrame
        # splits into allowed windows, follows pagination
    def cb_issuance_decisions(self, corp_code: str, bgn_de: date, end_de: date) -> pd.DataFrame
    def share_totals(self, corp_code: str, bsns_year: int, reprt_code: str = "11011") -> pd.DataFrame
    def dividends(self, corp_code: str, bsns_year: int, reprt_code: str = "11011") -> pd.DataFrame
    def investments(self, corp_code: str, bsns_year: int, reprt_code: str = "11011") -> pd.DataFrame
    def document(self, rcept_no: str) -> Path      # returns the extracted directory
```

Behavior shared by all methods:
- **Cache first**: if the raw file exists and `refresh=False`, parse and return it without a network call.
- **Status handling**: `000` → store and return. `013` (no data) → store an empty marker and return an empty frame, so it is not re-fetched. `020` (quota) → raise `QuotaExhausted`. `010/011/012/901` (key/permission) → raise `DartAuthError`. Any other code → `DartError` after retries.
- **Retries**: `tenacity`, exponential backoff, 5 attempts, on network errors and HTTP 5xx only.
- **Numbers**: amount strings are parsed to `float` (strip commas; empty or `-` → `NaN`). Values stay in KRW at this layer.

### 5.4 `KrxClient` and `PriceClient`

```python
class KrxClient:
    def listing(self, on: date, market: Literal["KOSPI", "KOSDAQ"]) -> pd.DataFrame
        # ticker, name, market, close, market_cap, shares_listed
    def sector(self, on: date, market: str) -> pd.DataFrame          # ticker, sector_code, sector_name
    def flags(self, on: date) -> pd.DataFrame                         # ticker, admin_issue, halted

class PriceClient:
    def history(self, ticker: str, start: date, end: date) -> pd.DataFrame
        # date, close, adj_close, volume
    def price_on(self, ticker: str, on: date, adjusted: bool = True) -> float
        # last trading-day close on or before `on`; raises if no trade within 10 days before
```
The backend for each method (KRX Open API, pykrx, yfinance) follows D0.3/D0.4/D0.6. Backends sit behind these interfaces so they can be swapped without changing callers.

### 5.5 CB collection (`src/data/cb_collect.py`, `src/data/cb_parser.py`)

```python
def find_cb_issuers(dart, bgn: date, end: date) -> pd.DataFrame
    # search_filings over major-event reports, filter report_nm containing the CB issuance
    # title from the P0 memo; returns corp_code, rcept_no, rcept_dt, report_nm
def collect_cb_terms(dart, corp_codes, bgn, end) -> pd.DataFrame
    # cb_issuance_decisions per issuer: rcept_no, series (회차), face_amount, conversion_price,
    # refix_floor, conv_start, conv_end, maturity, call_option, put_option, raw fields
def collect_refixings(dart, corp_codes, bgn, end) -> pd.DataFrame
    # exchange disclosures whose report_nm matches the conversion-price adjustment title
    # (P0 memo); parse the new conversion price and effective date from the document
def latest_periodic_report(dart, corp_code, before: date) -> str   # rcept_no
def parse_unredeemed_cb_table(doc_dir: Path) -> pd.DataFrame
    # locate the table by header keywords ("미상환", "전환사채"); normalize columns:
    # series, issue_date, maturity, face_total, conv_price, face_outstanding, convertible_shares
```

`cb_parser` must handle: amounts in won or with unit captions ("단위: 원/천원/백만원"), merged header cells, "-" for empty, and multiple tables in one document (pick the one whose header matches; log ambiguity).

### 5.6 Orchestration (`scripts/fetch_all.py`)

```
python scripts/fetch_all.py --date t_post --stage all
python scripts/fetch_all.py --date t_post --stage listing,company,fs
python scripts/fetch_all.py --date t_pre  --stage fs --firms data/processed/e7_candidates.csv
```

| Stage | What it does | Approx. calls |
|---|---|---|
| `corpcodes` | Download `corpCode.xml` | 1 |
| `listing` | KRX listing, sector, flags for KOSPI and KOSDAQ on the evaluation date | few |
| `company` | `company()` for all listed firms (KSIC code for financial exclusion and labels) | ~2,600 |
| `cb_issuers` | `find_cb_issuers` over the D1.2 window | ~100–300 |
| `universe` | Build `universe_{date}.parquet`: KOSPI non-financial + KOSDAQ CB issuers, with exclusion flags | 0 |
| `fs` | Annual CFS statements for the universe (OFS fallback is recorded, not used, unless P2 decides otherwise) | ~1,200 |
| `shares` | Share totals, dividends, investments for the universe | ~3,600 |
| `cb` | CB terms, refixings, latest periodic report + table parsing for KOSDAQ issuers | ~1,000 |
| `prices` | Daily prices for the universe over [`t_pre − 2y`, `t_post + 1m`] | per ticker |
| `report` | Write `docs/data_coverage_report.md` | 0 |

Stages are resumable thanks to the raw cache. With a 20,000/day quota the whole run fits in one or two days.

## 6. Step-by-step tasks

1. **Rate limiter** + tests (simulated clock; quota persistence across instances). Commit.
2. **DartClient core**: request helper, status handling, raw cache, `corp_codes`, `company`. Tests against fixtures, including `013` and `020` responses (craft fixture JSON for these). Commit.
3. **Financial statements**: `financial_statements` + amount parsing. Tests: three-year columns parsed; `-표준계정코드 미사용-` rows kept; NaN handling. Commit.
4. **Filing search**: window splitting (≤ 3 months without `corp_code`), pagination. Tests with multi-page fixtures. Commit.
5. **Share totals, dividends, investments, document download**. Tests. Commit.
6. **KrxClient + PriceClient** with the backends chosen in P0. Tests: `price_on` returns the previous trading day on weekends/holidays; raises on long gaps. Commit.
7. **CB collection + parser**. Build parser tests from at least 3 real periodic-report fixtures with different table layouts. Commit.
8. **fetch_all.py** with stages and `--limit` for smoke runs. Smoke test: `--limit 5` on every stage. Commit.
9. **Full fetch at `t_post`**, then generate the coverage report. Investigate failures; fix and re-run (cache keeps it cheap).
10. **Coverage report** (`docs/data_coverage_report.md`): firms per stage, failures by reason, KOSDAQ CB issuers with a parsed outstanding table, number with a refixing history.
11. **`t_pre` data is not fetched in P1.** As specified in §6.7, E7 values `t_post` filings and uses the cutoff-date price $P^{old}$ only as a regressor, so it needs prices, not `t_pre` statements. §6.3 nevertheless lists `T_pre` as "for E7". This inconsistency was resolved as **D7.4** (2026-10-05): `T_pre` is used only for an optional pre-cutoff replication of E2. If the budget allows it, `fetch_all.py --date t_pre --stage fs,shares` is run in P8 for the selected firms only.

## 7. Tests

| Test file | Key cases |
|---|---|
| `test_dart_client.py` | Cache hit avoids network (mock session asserts zero calls); status code mapping; amount parsing; window splitting; pagination |
| `test_krx_client.py` | Listing schema; market filter; flag join |
| `test_price_client.py` | `price_on` holiday handling; adjusted vs raw |
| `test_cb_parser.py` | ≥ 3 layout variants; unit captions; merged headers; empty markers; table disambiguation |

The HTTP layer is mocked with `responses` or a fake session object that serves fixture files.

## 8. Exit criteria & verification

- [ ] `pytest` passes; no test touches the network.
- [ ] `python scripts/fetch_all.py --date t_post --stage all` completes, and a second run makes zero network calls (check the limiter counter).
- [ ] Coverage report shows ≥ 95% of universe firms with a three-year CFS annual statement.
- [ ] Coverage report shows the number of KOSDAQ firms with a parsed outstanding-CB table and current conversion price. Pre-check for gate G5: at least ~60 candidates before the in-the-money filter (the ITM filter in P2 typically removes many).

## 9. Risks & fallbacks

| Risk | Fallback |
|---|---|
| Daily quota hit mid-stage | Stages are resumable; continue the next day. A second API key may be used only if permitted by OpenDART terms |
| `bfefrmtrm` missing for some statements | Fetch the prior-year annual report for that firm and take its `frmtrm`; flag `three_year_source="mixed"` |
| CB table layouts too varied for the parser | Parse the top layouts automatically; for the rest, a manual entry CSV (`data/ground_truth/cb_manual.csv`) with the source `rcept_no` |
| Refixing disclosures hard to parse | Use the conversion price from the latest periodic report's outstanding table as the current price (it already reflects refixings up to that date), and check refixings only after that report date |
| KRX flags unavailable for past dates | Derive admin-issue status from DART/exchange disclosures within the window; record the method |

## 10. Assumptions to revalidate

- Endpoint names and fields as listed (confirm against the P0 memo).
- One annual report provides three years for all three statements.
- OpenDART daily quota ≈ 20,000 calls.
