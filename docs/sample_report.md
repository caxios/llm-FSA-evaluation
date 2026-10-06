# Sample Report (P2)

- Generated: 2026-10-06 09:31
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
| KOSDAQ | 713 | 0 | 45 | 64 | 3 | 45 | 2 | 579 |

- `financial`: KSIC 64–66 (already outside the universe, shown as 0 here). `halted`: zero volume on `T_post` (KRX daily data). Administrative-issue status is not yet applied (D0.6, pending).

## Sample

| group | firms | market cap median (tn KRW) | KSIC divisions |
|---|---|---|---|
| L | 50 | 22.91 | 23 |
| M | 50 | 0.48 | 25 |
| S | 50 | 0.09 | 19 |

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

- Eligible KOSDAQ CB issuers: 579; with outstanding CB at `T_post`: 368; in the money at market price: 173
- Selected: 50; dilution (ITM convertible shares / common shares) median 28.8%, range 16.4%–81.0%
- Price source for the ITM test: {'krx': 712}
