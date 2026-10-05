# Data Coverage Report (P1)

- Generated: 2026-10-05 19:31
- Evaluation date `T_post`: 2026-04-01; fiscal year: FY2025
- Source tables: `data/processed/p1/*.parquet` (not committed)

## Universe

| Market | Listed | Financial (excluded) | CB issuers | In universe |
|---|---|---|---|---|
| KOSPI | 830 | 111 | 0 | 719 |
| KOSDAQ | 726 | 13 | 726 | 713 |

- Halted on `T_post` (KRX-covered firms only): 24 of 719

## Annual statements

- Statements found: 1431 / 1432 (99.9%)
- Consolidated (CFS): 1206; separate only (OFS): 225
- Three years in one report: 1428 / 1432 (99.7%)
- Filed by `T_post` (latest receipt date): 1258 / 1432 (87.8%)
  - Later receipt dates include corrected reports re-filed after `T_post`; P2 decides which filings count as available at `T_post`.

## Shares, dividends, investments

- Share totals: 1431 / 1432 (99.9%)
- Dividends: 1431 / 1432 (99.9%)
- Investments in other companies: 1431 / 1432 (99.9%)

## Convertible bonds (KOSDAQ CB issuers)

- Firms processed: 713
- Unredeemed-CB table found in the annual report: 509 / 713 (71.4%)
- Status: table 509, not_found 150, none_declared 53, no_report 1
- Firms with ≥ 1 outstanding CB series at FY end: 509
- CB issuance terms (series): 1822
- Conversion-price adjustments between FY end and `T_post`: 154
- Parse warnings: 29

## Prices

| Date | Source | Firms |
|---|---|---|
| cutoff | krx | 712 |
| cutoff | yfinance | 698 |
| t_post | krx | 719 |
| t_post | yfinance | 706 |
