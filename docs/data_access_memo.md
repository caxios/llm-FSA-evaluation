# Data Access Memo (P0 Step 0.5)

| Item | Value |
|---|---|
| Date | 2026-10-05 |
| Probes | `scripts/probes/probe_*.py` (run manually; outputs summarized here) |
| Fixtures | `tests/fixtures/{dart,krx,prices}/` |

Status legend: **available** / **workaround** / **unavailable** / **action needed**.

## Summary (research plan §8)

| Data | Source | Status | Notes |
|---|---|---|---|
| Consolidated statements, 3 years | OpenDART `fnlttSinglAcntAll.json` | **available** | One annual report returns `thstrm`/`frmtrm`/`bfefrmtrm` for all statements. FY2022–FY2025 available |
| Original filing documents | OpenDART `document.xml` | **available** | ZIP of DART XML files (UTF-8). Tables use `TE`/`TU` cell tags besides `TD`/`TH` |
| CB issuance terms | OpenDART `cvbdIsDecsn.json` | **available** | Face amount, conversion price, convertible shares, **refixing floor**, maturity, conversion period. Call/put terms only as text |
| CB outstanding balance | Annual report table "미상환 전환사채 발행현황" | **workaround** | No structured endpoint per CB series. The table is reliably found by headers and parses cleanly |
| Refixing history | OpenDART `list.json` exchange disclosures, `report_nm` "전환가액의조정" | **available** | Search per `corp_code` (no window limit). The latest annual-report table already reflects refixings up to its date |
| Listing universe, market cap (KOSPI) | KRX Open API `sto/stk_bydd_trd` | **available** | Any past date; includes `MKTCAP`, `LIST_SHRS`, close |
| Listing universe, market cap (KOSDAQ) | KRX Open API `sto/ksq_bydd_trd` | **action needed** | HTTP 401: service not approved for this key. Apply on openapi.krx.co.kr |
| Issue base info (KOSPI/KOSDAQ) | KRX Open API `sto/stk_isu_base_info`, `sto/ksq_isu_base_info` | **action needed** | HTTP 401: not approved. Optional (listing date, share class); apply together with the item above |
| pykrx | scraping data.krx.co.kr | **unavailable** | Requires KRX login (`KRX_ID`/`KRX_PW`); market-cap and sector calls fail; long OHLCV ranges return 0 rows. Do not use |
| Prices | KRX Open API close (primary); yfinance `Close` (fallback) | **available** | See price section |
| Industry classification | OpenDART `company.json` `induty_code` (KSIC) | **available** | 3-digit KSIC codes (e.g., `264`); division = first 2 digits. KRX `SECT_TP_NM` is empty for KOSPI |
| Shares (issued/treasury/outstanding by class) | OpenDART `stockTotqySttus.json` | **available** | Rows per class: 보통주 / 우선주 / 합계 |
| DPS | OpenDART `alotMatter.json` | **available** | Three years, by share class |
| Investee names (for redaction) | OpenDART `otrCprInvstmntSttus.json` | **available** | `inv_prm` = investee name (e.g., 134 rows for Samsung) |
| Admin-issue / trading-halt flags as of a past date | — | **workaround** | Not in the approved KRX services. Workaround: a firm traded on the evaluation date (present in `stk_bydd_trd` with volume > 0) is not halted; admin-issue status from exchange disclosures (`list.json`, `pblntf_ty=I`) in the year before `T_post` |

## OpenDART details

- Daily quota: not tested to exhaustion (published limit 20,000 calls/key/day). Observed latency 0.1–0.3 s per call; `list.json` without `corp_code` 0.6–7.5 s.
- `list.json`:
  - Without `corp_code`: window ≤ 3 months (status `100` otherwise). With `corp_code`: multi-year windows work.
  - `page_count` max 100 (larger values are silently capped).
  - `pblntf_ty=B` (major-event reports), `corp_cls=K` filters KOSDAQ. CB issuance titles: `주요사항보고서(전환사채권발행결정)`, plus prefixes `[기재정정]`, `[첨부정정]`. Related: `자기전환사채매도결정`, `자기전환사채만기전취득결정`, `전환사채매수선택권행사자지정`.
  - Exchange disclosures (`pblntf_ty=I`) are high volume (~8,300/month on KOSDAQ), so refixing searches are done per `corp_code`, not market-wide.
- `fnlttSinglAcntAll.json`:
  - Row keys: `rcept_no, reprt_code, bsns_year, corp_code, sj_div, sj_nm, account_id, account_nm, account_detail, thstrm_nm, thstrm_amount, frmtrm_nm, frmtrm_amount, bfefrmtrm_nm, bfefrmtrm_amount, ord, currency`. Amounts in KRW.
  - `sj_div` values: `BS`, `IS`, `CIS`, `CF`, `SCE`. **Some firms report only `CIS`** (single statement of comprehensive income, e.g., Hansol Chemical); the builder must take IS lines from `CIS` when `IS` is absent.
  - `account_id = "-표준계정코드 미사용-"` is common in CF (~20–25% of CF rows) and rare in BS/IS. Label-synonym mapping is needed mainly for CF.
  - Key IDs present: `ifrs-full_CashAndCashEquivalents`, `ifrs-full_Assets`, `ifrs-full_Revenue`, `dart_OperatingIncomeLoss`, `ifrs-full_ProfitLossAttributableToOwnersOfParent` (CFS only; absent in OFS), `ifrs-full_IncreaseDecreaseInCashAndCashEquivalents`, `ifrs-full_BasicEarningsLossPerShare` (in IS or CIS).
  - Convertible bonds can appear with a DART ID (`dart_CurrentPortionOfConvertibleBonds`) or as an unmapped label `전환사채`.
  - Some rows have empty amounts in one of the three columns (e.g., Hansol Chemical BS) — expected for lines that exist only in some years.
- `cvbdIsDecsn.json` fields used: `bd_tm` (series), `bd_knd`, `bd_fta` (face, KRW), `cv_prc`, `cvisstk_cnt`, `cvisstk_tisstk_vs` (% of shares), `cvrqpd_bgd`/`cvrqpd_edd`, `act_mktprcfl_cvprc_lwtrsprc` (**refixing floor price**), `bd_mtd` (maturity), `bdis_mthn` (public/private), `rcept_no`, `bddd` (board date). Dates are Korean strings (`2029년 12월 24일`).
- Unredeemed-balance endpoints (`cprndNrdmpBlce`, `srtpdPsndbtNrdmpBlce`, `entrprsBilScritsNrdmpBlce`, `newCaplScritsNrdmpBlce`, `cndlCaplScritsNrdmpBlce`) give maturity-bucket totals for bond types, **not per-CB balances**. Not used for $F$.
- `document.xml`: ZIP with the main report XML (~2 MB) plus attachments (audit reports). Parse with BeautifulSoup. The CB table header row: `종류＼구분 | 회차 | 발행일 | 만기일 | 권면(전자등록)총액 | 전환대상주식의 종류 | 전환청구가능기간 | 전환조건(전환비율, 전환가액) | 미상환사채(권면총액, 전환가능주식수) | 비고`, unit caption `(단위 : 원, 주)`, last row `합 계`. Example (빛과전자 FY2025): 4 series, outstanding 15.48bn KRW, 20.28m convertible shares.

## Prices (D0.3)

| Ticker | Date | yfinance Close | yfinance Adj Close | KRX close |
|---|---|---|---|---|
| 005930 | 2023-04-03 | 63,100 | 59,378 | 63,100 |
| 005930 | 2024-08-30 | 74,300 | 71,608 | 74,300 |
| 005930 | 2026-04-01 | 189,650 | 189,441 | 189,600 |
| 014680 | 2023-04-03 | 231,500 | 223,341 | 231,500 |
| 014680 | 2026-04-01 | 286,000 | 286,000 | 284,000 |
| 069540 | 2023-04-03 | 2,775 | 2,775 | n/a (KOSDAQ not approved) |

- KRX close is the official, unadjusted point-in-time price. yfinance `Close` matches it for past dates but differed on 2026-04-01 for two tickers; yfinance `Adj Close` is dividend-adjusted and must not be used as "the price on that date".
- **Recommendation (D0.3)**: KRX Open API close for all point-in-time prices (quiz truth, ITM test, $P^{old}$, $P^{new}$). For the E7 log price change, adjust for share-count changes (splits, bonus issues) using `LIST_SHRS` changes and DART capital-change filings; yfinance `Close` only as a fallback.

## Decisions proposed from the probes

| ID | Proposal |
|---|---|
| D0.3 | Prices: KRX Open API close (unadjusted); split adjustment for E7 from `LIST_SHRS`/filings; yfinance fallback |
| D0.4 | Listing and market cap: KRX Open API (`stk_bydd_trd`, `ksq_bydd_trd`). Requires KOSDAQ service approval |
| D0.5 | Industry: DART `induty_code` (KSIC); exclusions by 2-digit division 64–66 |
| D0.6 | Halt: absence/zero volume in KRX daily data on the evaluation date. Admin issue: exchange disclosures in the prior 12 months |

## Implications for P1/P2 plans

1. P1 `krx_client`: KRX Open API only; drop pykrx. Endpoint `https://data-dbg.krx.co.kr/svc/apis/sto/{stk|ksq}_bydd_trd?basDd=YYYYMMDD`, header `AUTH_KEY`.
2. P1 `cb_parser`: handle `TE`/`TU` cells and the two-level header; unit caption `(단위 : 원, 주)`.
3. P1 `find_cb_issuers`: 3-month windows with `pblntf_ty=B`, `corp_cls=K`; match `전환사채권발행결정` including correction prefixes; deduplicate corrections by keeping the latest filing per original.
4. P2 builder: take IS lines from `CIS` when `IS` is absent; most label-synonym work is in CF.
5. P2: `T_post` = 2026-04-01 is feasible from the data side (FY2025 annual reports available).
