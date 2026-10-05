# Pilot Report (P7) — KOSDAQ-independent part

## Gates

| gate | metric | value | threshold | result | note |
|---|---|---|---|---|---|
| G1 Schema | valid / all runs | 0.998 | >= 95% | PASS | 1227/1230 runs |
| G2 Calculation | share of valid P runs with eps > 5% | 0.952 | < 30% | FAIL | median eps 80.804% |
| G3 Signal | large caps mean(beta_A - beta_C) | -0.592 | 90% CI excludes 0 or |mean| >= 0.10 | PASS | 90% CI [-1.028, -0.126], 10 firms |
| G4 Measurability | firms with a feasible cash size at n <= 20 | 0.000 | >= 80% | FAIL | 0/10 firms |
| G5 Data | ITM small caps with CB truth; E8 validity | – | >= 30 firms; >= 90% valid | pending | pending: S selection waits for KRX KOSDAQ prices |

## Diagnostics

- nonpositive_baseline_firms: 2
- nonpositive_run_share: 0.171
- refusal_or_invalid_share: 0.002
- mean_latency_s: 3.539
- unit_slip_share: 0.142
- korean_rationale_share: 0.322

### Elasticities

| firm_id | condition | beta | se_hc3 | n_used | n_nonpositive_dropped |
|---|---|---|---|---|---|
| L001 | A | 1.034 | 0.846 | 50.000 | 0.000 |
| L001 | C | 0.884 | 0.446 | 70.000 | 0.000 |
| L006 | A | -1.944 | 0.784 | 49.000 | 1.000 |
| L006 | C | -0.773 | 1.012 | 65.000 | 5.000 |
| L011 | A | -0.550 | 0.848 | 50.000 | 0.000 |
| L011 | C | -1.802 | 0.964 | 70.000 | 0.000 |
| L016 | A | -0.959 | 0.904 | 49.000 | 1.000 |
| L016 | C | 0.314 | 0.613 | 70.000 | 0.000 |
| L021 | A | 0.476 | 0.451 | 49.000 | 0.000 |
| L021 | C | 0.407 | 0.457 | 70.000 | 0.000 |
| L026 | A | -2.621 | 0.600 | 43.000 | 7.000 |
| L026 | C | -1.302 | 0.839 | 52.000 | 18.000 |
| L031 | A | 1.662 | 0.995 | 10.000 | 39.000 |
| L031 | C | 1.703 | 0.560 | 22.000 | 48.000 |
| L036 | A | -1.518 | 2.393 | 12.000 | 38.000 |
| L036 | C | 0.019 | 1.462 | 22.000 | 48.000 |
| L041 | A | 0.042 | 0.600 | 50.000 | 0.000 |
| L041 | C | 0.863 | 0.545 | 69.000 | 0.000 |
| L046 | A | -0.182 | 0.709 | 50.000 | 0.000 |
| L046 | C | 1.050 | 0.168 | 70.000 | 0.000 |

### Baseline (E0 / k = 1)

| firm_id | condition | v0 | sigma | n_valid | n_total | shares_agent |
|---|---|---|---|---|---|---|
| L001 | A | 45,181 | 67,369 | 10.000 | 10.000 | 5,827,808,935 |
| L001 | C | 192,786 | 66,450 | 30.000 | 30.000 | 5,919,638 |
| L006 | A | 970,414 | 646,269 | 10.000 | 10.000 | 51,448,788 |
| L006 | C | 1,262,438 | 695,541 | 30.000 | 30.000 | 51,448,788 |
| L011 | A | 633 | 187,250 | 10.000 | 10.000 | 162,168 |
| L011 | C | 718 | 209,720 | 30.000 | 30.000 | 162,167,581 |
| L016 | A | 452 | 132,396 | 10.000 | 10.000 | 149,579,777 |
| L016 | C | 469,765 | 204,131 | 30.000 | 30.000 | 149,579,777 |
| L021 | A | 42,222 | 7,654 | 10.000 | 10.000 | 94,853,002 |
| L021 | C | 33,082 | 8,934 | 30.000 | 30.000 | 94,853,002 |
| L026 | A | 670 | 454,857 | 10.000 | 10.000 | 70,592,341 |
| L026 | C | 1,314 | 539,157 | 30.000 | 30.000 | 70,592,341 |
| L031 | A | -38.870 | 88,904 | 10.000 | 10.000 | 88,946,185 |
| L031 | C | -19.185 | 40,688 | 30.000 | 30.000 | 88,946,185 |
| L036 | A | -119 | 82,148 | 10.000 | 10.000 | 111,355,765 |
| L036 | C | -19,859 | 62,341 | 30.000 | 30.000 | 111,355,765 |
| L041 | A | 129,554 | 130,591 | 10.000 | 10.000 | 170,444,487 |
| L041 | C | 135,244 | 71,890 | 30.000 | 30.000 | 170,444,487 |
| L046 | A | 187,752 | 440,004 | 10.000 | 10.000 | 77,350,186 |
| L046 | C | 221,510 | 300,238 | 30.000 | 30.000 | 77,350,186 |

### Sigma stability (sigma from first n reps / sigma from all)

| firm_id | n_valid | sigma_all | cv_all | rel_5 | rel_10 | rel_15 | rel_20 |
|---|---|---|---|---|---|---|---|
| L001 | 20 | 62,430 | 0.324 | 1.564 | 1.236 | 1.068 | 1.000 |
| L006 | 20 | 666,571 | 0.528 | 0.865 | 1.180 | 1.134 | 1.000 |
| L011 | 20 | 226,598 | 311 | 0.000 | 0.794 | 0.942 | 1.000 |
| L016 | 20 | 208,256 | 0.445 | 1.170 | 0.960 | 0.809 | 1.000 |
| L021 | 20 | 9,055 | 0.255 | 0.981 | 1.013 | 0.964 | 1.000 |
| L026 | 20 | 500,070 | 380 | 1.390 | 1.275 | 1.073 | 1.000 |
| L031 | 20 | 44,902 | 2,340 | 0.272 | 0.719 | 0.643 | 1.000 |
| L036 | 20 | 58,677 | 2.955 | 1.233 | 1.214 | 1.128 | 1.000 |
| L041 | 20 | 71,443 | 0.461 | 0.661 | 0.985 | 0.903 | 1.000 |
| L046 | 20 | 365,800 | 1.651 | 0.181 | 0.197 | 0.233 | 1.000 |

### Size decisions

| firm_id | perturbation | fraction | x_mn | n | status | reason |
|---|---|---|---|---|---|---|
| L001 | cash | – | – | 40 | excluded | precision bound 826,363 exceeds upper bound 116,984 (KRW mn) at n_max |
| L001 | non_operating | – | – | 40 | excluded | precision bound 826,363 exceeds upper bound 116,984 (KRW mn) at n_max |
| L006 | cash | – | – | 40 | excluded | precision bound 76,684,264 exceeds upper bound 7,265,680 (KRW mn) at n_max |
| L006 | non_operating | – | – | 40 | excluded | precision bound 76,684,264 exceeds upper bound 7,265,680 (KRW mn) at n_max |
| L011 | cash | – | – | 40 | excluded | precision bound 82,168,622 exceeds upper bound 10,430 (KRW mn) at n_max |
| L011 | non_operating | – | – | 40 | excluded | precision bound 82,168,622 exceeds upper bound 10,430 (KRW mn) at n_max |
| L016 | cash | – | – | 40 | excluded | precision bound 69,655,367 exceeds upper bound 5,984,019 (KRW mn) at n_max |
| L016 | non_operating | – | – | 40 | excluded | precision bound 69,655,367 exceeds upper bound 7,265,547 (KRW mn) at n_max |
| L021 | cash | – | – | 40 | excluded | precision bound 1,920,537 exceeds upper bound 276,235 (KRW mn) at n_max |
| L021 | non_operating | – | – | 40 | excluded | precision bound 1,920,537 exceeds upper bound 337,138 (KRW mn) at n_max |
| L026 | cash | – | – | 40 | excluded | precision bound 78,935,695 exceeds upper bound 5,808 (KRW mn) at n_max |
| L026 | non_operating | – | – | 40 | excluded | precision bound 78,935,695 exceeds upper bound 5,808 (KRW mn) at n_max |
| L031 | cash | – | – | 10 | excluded | non-positive equity value or share count |
| L031 | non_operating | – | – | 10 | excluded | non-positive equity value or share count |
| L036 | cash | – | – | 10 | excluded | non-positive equity value or share count |
| L036 | non_operating | – | – | 10 | excluded | non-positive equity value or share count |
| L041 | cash | – | – | 40 | excluded | precision bound 27,228,586 exceeds upper bound 1,171,466 (KRW mn) at n_max |
| L041 | non_operating | – | – | 40 | excluded | precision bound 27,228,586 exceeds upper bound 2,644,299 (KRW mn) at n_max |
| L046 | cash | – | – | 40 | excluded | precision bound 63,268,812 exceeds upper bound 1,558,981 (KRW mn) at n_max |
| L046 | non_operating | – | – | 40 | excluded | precision bound 63,268,812 exceeds upper bound 2,281,758 (KRW mn) at n_max |

### Anomaly-flag rate by perturbation

| perturbation_type | anomaly_rate |
|---|---|
| none | 0.360 |
| scale | 0.413 |

### Main-run cost re-estimate

| schema | main_calls | mean_tokens_in | mean_tokens_out | usd |
|---|---|---|---|---|
| valuation | 36780 | 6,627 | 922 | 37.944 |
| quiz | 450 | 364 | 87.133 | 0.032 |

## Interpretation (2026-10-05, KOSDAQ-independent part only)

Scope run: dev set (5 firms outside the sample) with prompt v1, then pilot L (10 large caps: E0 × 20 reps, E2 conditions C and A × 5 k × 10 reps, E6 × 3 reps; 1,230 calls, ≈ $1.5). Pilot S, E8, G5 and the preregistration wait for the KRX KOSDAQ approval. E3 was not run: no pilot firm received a feasible size.

1. **G1 passes** (99.8% valid after retries).
2. **G2 fails** (95% of runs have ε > 5%; median ε 81%). Stage gaps locate the error in discounting: the reported EV departs from the EV implied by the agent's own FCFF, WACC and g by 20–115% (median per firm); the bridge (EV → equity) and the division (equity → per share) are consistent. The plan's response is structure T (D6), where Python does the discounting.
3. **Unit slips** in 24% of E0 runs (14% of all valuation runs): for the largest firms the model restates amounts in KRW billion (÷1,000) and sometimes the share count too (Samsung Electronics, Samsung C&T). Mixed units move the per-share value by ~1,000×, which inflates σ. The dev set did not reveal this: its firms (KOSPI rank ≥ 51) have smaller numbers.
4. **G4 fails** (0/10): σ is huge relative to the 10% cap (CV 25–53% for firms without slips, up to 300× with slips); two firms (L031, L036) have non-positive baseline values. Without fixing (3), E3 cannot be sized.
5. **G3** formally passes (mean β_A − β_C = −0.59, 90% CI [−1.03, −0.13]) but is not interpretable: the sign is opposite to the hypothesis and the betas are dominated by unit slips and noise.

Per the plan (§9 "several gates fail at once"), no further spending until a design decision. Options:
- (a) Prompt v1.1 with explicit unit rules (copy table values in KRW million without conversion; shares exactly as in [주식 정보]); iterate on the dev set **including scaled-up dev packages** that reproduce large-firm magnitudes; then re-run pilot L. Logged as a post-step-1 prompt change (plan §9).
- (b) Structure T as the primary agent (fixes G2 by construction; unit slips still need (a)).
- (c) Model change (e.g., the comparison model, which showed tighter runs in P0) — the primary model's cutoff requirement (D1) must still hold.
Recommended: (a) + (b), re-run pilot L with T; keep P as the H4 comparison.
