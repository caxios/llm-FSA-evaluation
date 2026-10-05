# Data Coverage Report (P1)

- Generated: 2026-10-05 17:15
- Evaluation date `T_post`: 2026-04-01; fiscal year: FY2025
- Source tables: `data/processed/p1/*.parquet` (not committed)

## Universe

| Market | Listed | Financial (excluded) | CB issuers | In universe |
|---|---|---|---|---|
| KOSPI | 5 | 1 | 0 | 4 |
| KOSDAQ | 5 | 0 | 5 | 5 |

- Halted on `T_post` (KRX-covered firms only): 0 of 4

## Annual statements

- Statements found: 5 / 5 (100.0%)
- Consolidated (CFS): 5; separate only (OFS): 0
- Three years in one report: 5 / 5 (100.0%)
- Filed by `T_post` (latest receipt date): 5 / 5 (100.0%)
  - Later receipt dates include corrected reports re-filed after `T_post`; P2 decides which filings count as available at `T_post`.

## Shares, dividends, investments

- Share totals: 5 / 5 (100.0%)
- Dividends: 5 / 5 (100.0%)
- Investments in other companies: 5 / 5 (100.0%)

## Convertible bonds (KOSDAQ CB issuers)

- Firms processed: 5
- Unredeemed-CB table found in the annual report: 2 / 5 (40.0%)
- Firms with ≥ 1 outstanding CB series at FY end: 2
- CB issuance terms (series): 5
- Conversion-price adjustments between FY end and `T_post`: 1
- Parse warnings: 0

## Prices

| Date | Source | Firms |
|---|---|---|
| cutoff | yfinance | 5 |
| t_post | yfinance | 5 |

## Notes

- KRX KOSDAQ daily service not approved; KOSDAQ market data (market cap, halt flag) unavailable
