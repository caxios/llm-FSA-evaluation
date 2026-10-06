# Synthetic Validation (P6) — 150 sample firms

- Firms: 150; positive oracle value: 136; reps 10; noise sd 0.05
- CB firms in the money for the oracle: 19
- Firms with a non-positive oracle value (excluded from log metrics and anchored/mixture agents): L004, L031, M001, M035, M050, S012, S018, S024, S031, S032, S035, S047, S048, S049
- Overall: **PASS**

| agent | metric | expected | recovered | n | pass |
|---|---|---|---|---|---|
| oracle | mean beta (A) | 1 | 0.9982 | 136 | ✓ |
| oracle | mean beta (B) | 1 | 1.0009 | 136 | ✓ |
| oracle | mean beta (D) | 1 | 1.0002 | 136 | ✓ |
| oracle | mean beta (C) | 1 | 1.0011 | 136 | ✓ |
| oracle | mean R (cash) | 1 | 0.9596 | 113 | ✓ |
| oracle | mean R (non_operating) | 1 | 1.0176 | 136 | ✓ |
| oracle | mean R (shares) | 1 | 0.9967 | 150 | ✓ |
| oracle | mean eps | 0 | 0.0000 | 36960 | ✓ |
| oracle | mean R_dil (V0) | 1 | 1.0847 | 16 | ✓ |
| oracle | mean R_dil (V2) | 1 | 1.0309 | 16 | ✓ |
| oracle | mean R_dil (V3) | 1 | 1.0908 | 18 | ✓ |
| oracle | E9 success share | >= 95% | 1.0000 | 560 | ✓ |
| anchored | mean beta (C) | 0 | 0.0000 | 136 | ✓ |
| anchored | mean R (all types) | 0 | 0.0005 | 362 | ✓ |
| mixture(0.6) | mean beta (C) | 0.6 | 0.5963 | 136 | ✓ |
| condition mixture | mean industry_eff | 0.0 | -0.0003 | 136 | ✓ |
| condition mixture | mean name_eff | 0.2 | 0.2027 | 136 | ✓ |
| condition mixture | mean memory_eff | 0.3 | 0.2988 | 136 | ✓ |
| no_dilution | mean R_dil (V0, V2, V3) | 0 | -0.0363 | 50 | ✓ |
| no_dilution | E9 reflection share | >= 95% | 1.0000 | 560 | ✓ |
| calc_error | mean eps | 10% | 0.1000 | 4470 | ✓ |
| calc_error | E9 computation share | >= 95% | 1.0000 | 560 | ✓ |

Bootstrap CI coverage (200 simulated oracle firms, n = 10, 95% CI for R): **96.5%** (within 93–97%)

Runtime: 652 s
