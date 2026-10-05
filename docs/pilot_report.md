# Pilot Report (P7) — KOSDAQ-independent part (agent T, prompt v1.1)

## Gates

| gate | metric | value | threshold | result | note |
|---|---|---|---|---|---|
| G1 Schema | valid / all runs | 0.999 | >= 95% | PASS | 1229/1230 runs |
| G2 Calculation | share of valid T runs with eps > 5% | 0.000 | < 30% | PASS | median eps 0.000% |
| G3 Signal | large caps mean(beta_A - beta_C) | -0.083 | 90% CI excludes 0 or |mean| >= 0.10 | PASS | 90% CI [-0.154, -0.017], 8 firms |
| G4 Measurability | firms with a feasible cash size at n <= 20 | 0.000 | >= 80% | FAIL | 0/10 firms |
| G5 Data | ITM small caps with CB truth; E8 validity | – | >= 30 firms; >= 90% valid | pending | pending: S selection waits for KRX KOSDAQ prices |

## Diagnostics

- nonpositive_baseline_firms: 2
- nonpositive_run_share: 0.215
- refusal_or_invalid_share: 0.001
- mean_latency_s: 4.430
- unit_slip_share: 0.000
- korean_rationale_share: 1.000

### Elasticities

| firm_id | condition | beta | se_hc3 | n_used | n_nonpositive_dropped |
|---|---|---|---|---|---|
| L001 | A | 0.105 | 0.202 | 46.000 | 4.000 |
| L001 | C | 0.264 | 0.205 | 62.000 | 8.000 |
| L006 | A | 0.690 | 0.352 | 44.000 | 6.000 |
| L006 | C | 0.968 | 0.169 | 67.000 | 3.000 |
| L011 | A | 0.954 | 0.029 | 50.000 | 0.000 |
| L011 | C | 0.992 | 0.051 | 70.000 | 0.000 |
| L016 | A | 1.126 | 0.055 | 50.000 | 0.000 |
| L016 | C | 1.037 | 0.066 | 70.000 | 0.000 |
| L021 | A | 0.972 | 0.039 | 50.000 | 0.000 |
| L021 | C | 1.006 | 0.037 | 70.000 | 0.000 |
| L026 | A | – | – | 0.000 | 49.000 |
| L026 | C | – | – | 2.000 | 68.000 |
| L031 | A | – | – | 0.000 | 50.000 |
| L031 | C | – | – | 0.000 | 70.000 |
| L036 | A | 1.193 | 0.108 | 50.000 | 0.000 |
| L036 | C | 1.154 | 0.094 | 70.000 | 0.000 |
| L041 | A | 0.556 | 0.137 | 50.000 | 0.000 |
| L041 | C | 0.758 | 0.172 | 70.000 | 0.000 |
| L046 | A | 0.853 | 0.070 | 50.000 | 0.000 |
| L046 | C | 0.938 | 0.093 | 70.000 | 0.000 |

### Baseline (E0 / k = 1)

| firm_id | condition | v0 | sigma | n_valid | n_total | shares_agent |
|---|---|---|---|---|---|---|
| L001 | A | 47,960 | 84,562 | 10.000 | 10.000 | 5,827,808,935 |
| L001 | C | 45,485 | 90,852 | 30.000 | 30.000 | 5,827,808,935 |
| L006 | A | 627,106 | 351,291 | 10.000 | 10.000 | 51,563,401 |
| L006 | C | 455,606 | 366,733 | 30.000 | 30.000 | 51,563,401 |
| L011 | A | 421,090 | 37,877 | 10.000 | 10.000 | 162,167,581 |
| L011 | C | 463,857 | 182,278 | 30.000 | 30.000 | 162,167,581 |
| L016 | A | 198,691 | 56,817 | 10.000 | 10.000 | 149,579,777 |
| L016 | C | 251,177 | 25,434 | 30.000 | 30.000 | 149,579,777 |
| L021 | A | 32,518 | 3,138 | 10.000 | 10.000 | 95,312,200 |
| L021 | C | 24,943 | 2,200 | 30.000 | 30.000 | 95,312,200 |
| L026 | A | -2,862,239 | 389,348 | 9.000 | 10.000 | 70,592,343 |
| L026 | C | -2,323,777 | 363,106 | 30.000 | 30.000 | 70,592,343 |
| L031 | A | -228,444 | 30,334 | 10.000 | 10.000 | 88,946,220 |
| L031 | C | -217,814 | 39,594 | 30.000 | 30.000 | 88,946,220 |
| L036 | A | 109,460 | 60,275 | 10.000 | 10.000 | 111,355,765 |
| L036 | C | 148,035 | 27,786 | 30.000 | 30.000 | 111,355,765 |
| L041 | A | 150,521 | 30,841 | 10.000 | 10.000 | 175,922,788 |
| L041 | C | 76,440 | 33,936 | 30.000 | 30.000 | 175,922,788 |
| L046 | A | 96,766 | 91,097 | 10.000 | 10.000 | 77,377,800 |
| L046 | C | 97,857 | 15,358 | 30.000 | 30.000 | 77,377,800 |

### Sigma stability (sigma from first n reps / sigma from all)

| firm_id | n_valid | sigma_all | cv_all | rel_5 | rel_10 | rel_15 | rel_20 |
|---|---|---|---|---|---|---|---|
| L001 | 20 | 88,402 | 1.903 | 0.750 | 1.135 | 1.061 | 1.000 |
| L006 | 20 | 357,936 | 0.763 | 0.485 | 1.127 | 1.069 | 1.000 |
| L011 | 20 | 181,952 | 0.390 | 0.191 | 1.059 | 1.147 | 1.000 |
| L016 | 20 | 24,479 | 0.097 | 1.378 | 1.126 | 1.027 | 1.000 |
| L021 | 20 | 2,224 | 0.089 | 0.992 | 1.021 | 0.986 | 1.000 |
| L026 | 20 | 368,050 | 0.154 | 0.799 | 1.000 | 1.018 | 1.000 |
| L031 | 20 | 37,950 | 0.174 | 1.372 | 1.181 | 1.101 | 1.000 |
| L036 | 20 | 27,893 | 0.182 | 1.206 | 0.999 | 0.944 | 1.000 |
| L041 | 20 | 34,412 | 0.450 | 0.889 | 1.009 | 1.024 | 1.000 |
| L046 | 20 | 16,235 | 0.166 | 0.996 | 0.872 | 0.815 | 1.000 |

### Size decisions

| firm_id | perturbation | fraction | x_mn | n | status | reason |
|---|---|---|---|---|---|---|
| L001 | cash | – | – | 40 | excluded | precision bound 1,152,003,758 exceeds upper bound 27,070,289 (KRW mn) at n_max |
| L001 | non_operating | – | – | 40 | excluded | precision bound 1,152,003,758 exceeds upper bound 27,070,289 (KRW mn) at n_max |
| L006 | cash | – | – | 40 | excluded | precision bound 41,269,769 exceeds upper bound 2,418,687 (KRW mn) at n_max |
| L006 | non_operating | – | – | 40 | excluded | precision bound 41,269,769 exceeds upper bound 2,418,687 (KRW mn) at n_max |
| L011 | cash | – | – | 40 | excluded | precision bound 65,979,003 exceeds upper bound 3,458,218 (KRW mn) at n_max |
| L011 | non_operating | – | – | 40 | excluded | precision bound 65,979,003 exceeds upper bound 7,560,977 (KRW mn) at n_max |
| L016 | cash | – | – | 40 | excluded | precision bound 8,187,550 exceeds upper bound 3,763,098 (KRW mn) at n_max |
| L016 | non_operating | – | – | 40 | excluded | precision bound 8,187,550 exceeds upper bound 3,763,098 (KRW mn) at n_max |
| L021 | cash | – | – | 40 | excluded | precision bound 473,928 exceeds upper bound 237,132 (KRW mn) at n_max |
| L021 | non_operating | – | – | 40 | excluded | precision bound 473,928 exceeds upper bound 237,132 (KRW mn) at n_max |
| L026 | cash | – | – | 10 | excluded | non-positive equity value or share count |
| L026 | non_operating | – | – | 10 | excluded | non-positive equity value or share count |
| L031 | cash | – | – | 10 | excluded | non-positive equity value or share count |
| L031 | non_operating | – | – | 10 | excluded | non-positive equity value or share count |
| L036 | cash | – | – | 40 | excluded | precision bound 6,945,291 exceeds upper bound 1,704,538 (KRW mn) at n_max |
| L036 | non_operating | – | – | 40 | excluded | precision bound 6,945,291 exceeds upper bound 1,704,538 (KRW mn) at n_max |
| L041 | cash | – | – | 40 | excluded | precision bound 13,536,783 exceeds upper bound 1,171,466 (KRW mn) at n_max |
| L041 | non_operating | – | – | 40 | excluded | precision bound 13,536,783 exceeds upper bound 1,344,752 (KRW mn) at n_max |
| L046 | cash | – | – | 40 | excluded | precision bound 2,808,938 exceeds upper bound 757,197 (KRW mn) at n_max |
| L046 | non_operating | – | – | 40 | excluded | precision bound 2,808,938 exceeds upper bound 757,197 (KRW mn) at n_max |

### Anomaly-flag rate by perturbation

| perturbation_type | anomaly_rate |
|---|---|
| none | 0.459 |
| scale | 0.443 |

### Main-run cost re-estimate

| schema | main_calls | mean_tokens_in | mean_tokens_out | usd |
|---|---|---|---|---|
| valuation | 36780 | 6,788 | 1,181 | 42.343 |
| quiz | 450 | 364 | 86.633 | 0.032 |

## Round 2 (2026-10-06): prompt v1.1 + structure T

Fixes for the two round-1 problems:
- **Unit slips** → prompt v1.1 adds explicit unit rules (copy amounts in KRW million as printed; shares as printed; Korean rationale). Verified on the dev set with two scaled-up dev packages (X011, X012: revenue ≈ KRW 220–300 trillion), which reproduce the slips under v1 (33–47% of runs) and show 0–20% under v1.1·P and **0%** under v1.1·T.
- **Discounting errors** → structure T (Python computes FCFF, discounting, bridge, per-share value).

Pilot L re-run with T + v1.1 (1,230 calls): G1 99.9%, **G2 PASS** (ε = 0 by construction), unit slips **0%**, G3 mean β_A − β_C = −0.08 (90% CI [−0.15, −0.02], 8 firms with positive values). **G4 still fails (0/10).**

Why G4 still fails:
1. **D&A is missing from 131 of 150 packages** (DART structured cash-flow data give only the total "조정" line), so the model invents D&A in each run (Samsung Electronics: 0 to 55 trillion KRW against ~48 trillion capex), which swings FCFF. Re-computing the same T runs with D&A = capex and ΔNWC = 0 cuts the run-to-run CV from 190% → 39% (L001), 39% → 5% (L011), 45% → 8% (L041), 76% → 18% (L006).
2. **The §6.8 parameters are very strict for LLM noise.** With s* = 0.1 and the 10% cap, a firm passes only if CV ≤ 3.2% at n = 20 (4.5% at n = 40). Even after (1) most firms have CV 4–40%.
   | s* | cap | max CV, n = 20 | max CV, n = 40 |
   |---|---|---|---|
   | 0.10 | 10% | 3.2% | 4.5% |
   | 0.10 | 20% | 6.3% | 8.9% |
   | 0.20 | 10% | 6.3% | 8.9% |
   | 0.25 | 20% | 15.8% | 22.4% |
3. Two firms (L026, L031) have non-positive baseline values in every run (D7.5).

Decisions needed (design, before the preregistration): (a) a D&A convention in the tool prompt (D&A = capex, ΔNWC from history or 0) or adding D&A to the packages from the annual-report notes; (b) relaxing s* and/or the cap, or accepting E3 on fewer firms; (c) D7.5 for non-positive baselines.
