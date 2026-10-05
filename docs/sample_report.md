# Sample Report (P2)

- Generated: 2026-10-05 19:58
- `T_post`: 2026-04-01; universe firms: 1432

## Package builds

| status | firms |
|---|---|
| ok | 1321 |
| identity_failure | 86 |
| missing_required | 12 |
| non_krw | 9 |
| no_shares | 3 |
| no_statements | 1 |

## Exclusions (a firm can have several)

| market | universe | financial | halted | build | no_3y | impairment | not_filed | eligible |
|---|---|---|---|---|---|---|---|---|
| KOSPI | 719 | 0 | 24 | 47 | 1 | 17 | 1 | 643 |
| KOSDAQ | 713 | 0 | 0 | 64 | 3 | 45 | 2 | 606 |

- `financial`: KSIC 64–66 (already outside the universe, shown as 0 here). `halted`: zero volume on `T_post` (KOSPI only until KRX KOSDAQ data is available). Administrative-issue status is not yet applied (D0.6, pending).

## Sample

| group | firms | market cap median (tn KRW) | KSIC divisions |
|---|---|---|---|
| L | 50 | 22.91 | 23 |
| M | 50 | 0.48 | 25 |
| S | 50 |  | 22 |

## Mid group: newsworthiness contrast within market-cap quintiles

| cap_quintile | news_group | count | median |
|---|---|---|---|
| 0 | high | 5 | 82.0 |
| 0 | low | 5 | 46.0 |
| 1 | high | 5 | 92.0 |
| 1 | low | 5 | 31.0 |
| 2 | high | 5 | 59.0 |
| 2 | low | 5 | 27.0 |
| 3 | high | 5 | 55.0 |
| 3 | low | 5 | 24.0 |
| 4 | high | 5 | 59.0 |
| 4 | low | 5 | 21.0 |

## Small group (CB)

- Eligible KOSDAQ CB issuers: 606; with outstanding CB at `T_post`: 381; in the money at market price: 227
- Selected: 50; dilution (ITM convertible shares / common shares) median 36.6%, range 25.0%–81.0%
- Price source for the ITM test: {'yfinance': 706}
- **Provisional**: KOSDAQ prices come from yfinance until the KRX KOSDAQ service is approved; yfinance closes are adjusted for later capital changes. Re-run `small`, `select`, `packages`, `truth` after approval.
