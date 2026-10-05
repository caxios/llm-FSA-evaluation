# Synthetic Validation (P6) — 150 sample firms

- Firms: 150; positive oracle value: 141; reps 10; noise sd 0.05
- CB firms in the money for the oracle: 21
- Firms with a non-positive oracle value (excluded from log metrics and anchored/mixture agents): L004, L031, M001, M035, M050, S019, S033, S040, S050
- Overall: **PASS**

| agent | metric | expected | recovered | n | pass |
|---|---|---|---|---|---|
| oracle | mean beta (A) | 1 | 0.9980 | 141 | ✓ |
| oracle | mean beta (B) | 1 | 1.0009 | 141 | ✓ |
| oracle | mean beta (D) | 1 | 0.9986 | 141 | ✓ |
| oracle | mean beta (C) | 1 | 1.0004 | 141 | ✓ |
| oracle | mean R (cash) | 1 | 1.0201 | 33 | ✓ |
| oracle | mean R (non_operating) | 1 | 1.0153 | 52 | ✓ |
| oracle | mean R (shares) | 1 | 0.9949 | 150 | ✓ |
| oracle | mean eps | 0 | 0.0000 | 35310 | ✓ |
| oracle | mean R_dil (V0) | 1 | 1.0123 | 19 | ✓ |
| oracle | mean R_dil (V2) | 1 | 1.0059 | 19 | ✓ |
| oracle | mean R_dil (V3) | 1 | 1.0427 | 21 | ✓ |
| oracle | E9 success share | >= 95% | 1.0000 | 630 | ✓ |
| anchored | mean beta (C) | 0 | -0.0002 | 141 | ✓ |
| anchored | mean R (all types) | 0 | -0.0167 | 154 | ✓ |
| mixture(0.6) | mean beta (C) | 0.6 | 0.5996 | 141 | ✓ |
| condition mixture | mean industry_eff | 0.0 | 0.0045 | 141 | ✓ |
| condition mixture | mean name_eff | 0.2 | 0.1984 | 141 | ✓ |
| condition mixture | mean memory_eff | 0.3 | 0.2986 | 141 | ✓ |
| no_dilution | mean R_dil (V0, V2, V3) | 0 | 0.0420 | 59 | ✓ |
| no_dilution | E9 reflection share | >= 95% | 1.0000 | 630 | ✓ |
| calc_error | mean eps | 10% | 0.1000 | 4460 | ✓ |
| calc_error | E9 computation share | >= 95% | 1.0000 | 630 | ✓ |

Bootstrap CI coverage (200 simulated oracle firms, n = 10, 95% CI for R): **96.5%** (within 93–97%)

Runtime: 804 s
