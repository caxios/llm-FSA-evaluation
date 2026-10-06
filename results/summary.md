# Results summary (P10)

_Generated 2026-10-06 18:22 (code 09269f4)_

## Hypotheses

| H | type | statistic | estimate | 95% CI | p | p (Holm) | n | verdict | ref |
|---|---|---|---|---|---|---|---|---|---|
| H1 | primary | DL weighted mean beta_C (L) | 0.993 | [0.951, 1.035] | 0.3759 | 1.0000 | 50 | not supported | T2 |
| H1b | exploratory | b_S (small - large slope), firm-clustered | 0.287 | [-0.001, 0.574] | 0.0254 | – | 146 | consistent (exploratory) | T3 |
| nonlinearity | exploratory | share of firms with p(quad) < 0.05 | 0.243 | [–, –] | – | – | 144 | — | T3 |
| H1c | exploratory | median eps_median L - S (structure P) | -0.148 | [–, –] | 0.8463 | – | 20 | not consistent (exploratory) | T4 |
| H2a | primary | median E_i (all) | 0.020 | [-0.114, 0.130] | 0.4276 | 1.0000 | 145 | inconclusive | T5 |
| H2a-L | exploratory | median E_i (L) | 0.014 | [-0.165, 0.290] | 0.2893 | – | 50 | not consistent (exploratory) | T5 |
| H2a-M | exploratory | median E_i (M) | 0.109 | [-0.173, 0.160] | 0.2796 | – | 50 | not consistent (exploratory) | T5 |
| H2a-S | exploratory | median E_i (S) | -0.127 | [-0.289, 0.217] | 0.6564 | – | 45 | not consistent (exploratory) | T5 |
| H2b | primary | gamma_1 (M_i), WLS, HC3 | 0.178 | [-0.788, 1.144] | 0.3592 | 1.0000 | 145 | inconclusive | T6 |
| H2c | exploratory | b2 (log P_old) in log V_C ~ log V_A + log P_old | 0.245 | [0.069, 0.420] | 0.0031 | – | 114 | consistent (exploratory) | T7 |
| H2d | exploratory | median beta_A - beta_B | 0.006 | [-0.077, 0.163] | 0.2470 | – | 145 | not consistent (exploratory) | T8 |
| H3 | primary | DL weighted mean R_dil (V0 vs V1), ITM small caps | 0.744 | [-0.138, 1.626] | 0.2849 | 1.0000 | 15 | inconclusive | T9 |
| H3c | exploratory | mean dose-response slope | -0.255 | [-2.158, 1.648] | 0.0906 | – | 17 | not consistent (exploratory) | T9 |
| specificity | exploratory | share of firm x placebo cells equivalent | 0.270 | [0.193, 0.364] | – | – | 100 | — | T9 |
| H3b | exploratory | mean reflection share - extraction share | 0.000 | [–, –] | – | – | 17 | — | T10 |
| H4-beta-P | exploratory | median paired |1-beta_C|: P - T | 0.060 | [–, –] | 0.1733 | – | 29 | not consistent (exploratory) | T11 |
| H4-Rdil-P | exploratory | median paired |1-R_dil|: P - T | -1.637 | [–, –] | – | – | 1 | — | T11 |
| H4-eps-P | exploratory | median epsilon (P; T = 0) | 0.761 | [–, –] | – | – | 30 | — | T11 |
| H4-beta-R | exploratory | median paired |1-beta_C|: R - T | 0.030 | [–, –] | 0.1326 | – | 29 | not consistent (exploratory) | T11 |
| H4-Rdil-R | exploratory | median paired |1-R_dil|: R - T | – | [–, –] | – | – | 0 | — | T11 |
| H4-eps-R | exploratory | median epsilon (R; T = 0) | 0.776 | [–, –] | – | – | 30 | — | T11 |

## Robustness

| check | statistic | estimate | 95% CI | p | n | note |
|---|---|---|---|---|---|---|
| H1-unweighted | mean beta_C (L), t test | 0.948 | [0.765, 1.130] | 0.2838 | 50 |  |
| H1-wilcoxon | median beta_C (L), Wilcoxon | 0.981 | [–, –] | 0.5608 | 50 |  |
| H2b-OLS | gamma_1 (M_i), OLS, HC3 | -0.276 | [-2.551, 1.999] | 0.5940 | 145 | R2 0.082; industry dummies 11 |
| H3-unweighted | mean R_dil, t test | -3.459 | [-7.901, 0.983] | 0.0246 | 15 |  |
| H3-wilcoxon | median R_dil, Wilcoxon | -1.014 | [–, –] | 0.0603 | 15 |  |
| R1-id_rate_D-H2a | median E_i (all) | 0.014 | [-0.119, 0.126] | 0.4674 | 144 | excluding 1 firms with id_rate_D >= 0.5; mean 0.0039 |
| R1-id_rate_D-H2b | gamma_1 (M_i), WLS, HC3 | 0.180 | [-0.782, 1.142] | 0.3570 | 144 | excluding 1 firms with id_rate_D >= 0.5; R2 0.105; industry dummies 11; VIF(M_i) 1.17, VIF(ln_cap) 1.18 |
| R1-id_rate_A-H2a | median E_i (all) | 0.020 | [-0.117, 0.130] | 0.4511 | 143 | excluding 2 firms with id_rate_A >= 0.5; mean 0.0065 |
| R1-id_rate_A-H2b | gamma_1 (M_i), WLS, HC3 | 0.176 | [-0.802, 1.153] | 0.3622 | 143 | excluding 2 firms with id_rate_A >= 0.5; R2 0.109; industry dummies 11; VIF(M_i) 1.17, VIF(ln_cap) 1.18 |
| R2 | Spearman rho(tier, R) | -0.046 | [–, –] | 0.6376 | 108 | median R by tier: cash 2% 1.10; cash 5% 1.24; cash 10% 1.03; non_operating 2% 0.14; non_operating 5% 1.17; non_operating 10% 0.50 |
| R3 | mean beta_C (L) with half the reps (100 draws) | 0.855 | [0.597, 1.043] | – | 100 |  |
| R4-H1 | DL weighted mean beta_C (L) | 0.996 | [0.956, 1.036] | 0.4165 | 48 | anomaly-flagged runs excluded (44.6% of runs); tau2 = 0.0068 |
| R4-H2a | median E_i (all) | 0.029 | [-0.242, 0.148] | 0.2938 | 102 | anomaly-flagged runs excluded (44.6% of runs); mean -0.0472 |
| R4-H3 | DL weighted mean R_dil (V0 vs V1), ITM small caps | 1.170 | [0.692, 1.648] | 0.7568 | 8 | anomaly-flagged runs excluded (44.6% of runs); tau2 = 0.1853 |
| R5-beta_C-comparison | median beta_C (comparison, 30 firms) | 0.979 | [–, –] | 0.0288 | 30 |  |
| R5-E-comparison | median E_i (comparison, 30 firms) | 0.033 | [–, –] | 0.1396 | 27 |  |
| R5-beta_C-primary | median beta_C (primary, 30 firms) | 1.005 | [–, –] | 0.6272 | 30 |  |
| R5-E-primary | median E_i (primary, 30 firms) | 0.072 | [–, –] | 0.3204 | 30 |  |
| R6 | median paired beta_C: with rule 6 - without (P) | -0.276 | [–, –] | 0.0357 | 26 | mean -0.8177 |
| R7 | H3 without complex CBs | – | [–, –] | – | 0 | not run: cb_complex is unknown for every firm (no structured field for call options or net settlement, D2.8) |
| R8-H1 | DL weighted mean beta_C (L) | 0.993 | [0.951, 1.035] | 0.3759 | 50 | cells below 70% validity excluded; tau2 = 0.0090 |
| R8-H2a | median E_i (all) | 0.020 | [-0.113, 0.131] | 0.4229 | 145 | cells below 70% validity excluded; mean 0.0087 |
| R8-H3 | DL weighted mean R_dil (V0 vs V1), ITM small caps | 0.715 | [-0.150, 1.581] | 0.2595 | 15 | cells below 70% validity excluded; tau2 = 0.8803 |
| R9-H1 | mean median-based beta_C (L), t test | 1.009 | [0.910, 1.108] | 0.5737 | 50 |  |

## Decomposition (T5)

| group | component | mean | ci_lo | ci_hi | share_of_total | n |
|---|---|---|---|---|---|---|
| all | industry_eff | 0.043 | -0.079 | 0.164 | 3.080 | 145 |
| all | name_eff | -0.037 | -0.148 | 0.074 | -2.656 | 145 |
| all | memory_eff | 0.008 | -0.105 | 0.127 | 0.576 | 145 |
| all | total_atten | 0.014 | -0.136 | 0.171 | 1.000 | 145 |
| L | industry_eff | 0.050 | -0.109 | 0.192 | 0.302 | 50 |
| L | name_eff | 0.053 | -0.055 | 0.175 | 0.321 | 50 |
| L | memory_eff | 0.062 | -0.120 | 0.291 | 0.377 | 50 |
| L | total_atten | 0.165 | -0.068 | 0.466 | 1.000 | 50 |
| M | industry_eff | -0.021 | -0.095 | 0.050 | 0.440 | 50 |
| M | name_eff | -0.020 | -0.132 | 0.098 | 0.417 | 50 |
| M | memory_eff | -0.007 | -0.178 | 0.143 | 0.143 | 50 |
| M | total_atten | -0.047 | -0.250 | 0.108 | 1.000 | 50 |
| S | industry_eff | 0.106 | -0.243 | 0.435 | -1.229 | 45 |
| S | name_eff | -0.156 | -0.461 | 0.152 | 1.813 | 45 |
| S | memory_eff | -0.036 | -0.283 | 0.214 | 0.416 | 45 |
| S | total_atten | -0.086 | -0.427 | 0.251 | 1.000 | 45 |

## E9 stages, ITM small caps (T10)

| stage | mean_share | ci_lo | ci_hi | n_firms |
|---|---|---|---|---|
| extraction_failure | 0.000 | 0.000 | 0.184 | 17 |
| reflection_failure | 0.000 | 0.000 | 0.184 | 17 |
| computation_failure | 0.000 | 0.000 | 0.184 | 17 |
| success | 1.000 | 0.816 | 1.000 | 17 |

## Structures (T11)

| structure | n_firms | extraction_failure | reflection_failure | computation_failure | success | median_beta_C |
|---|---|---|---|---|---|---|
| T | 20 | 0.000 | 0.000 | 0.000 | 1.000 | 1.005 |
| P | 10 | 0.000 | 0.000 | 0.983 | 0.017 | 0.889 |
| R | 0 | – | – | – | – | 0.776 |

## R by tier (R2)

| perturbation | tier | median | mean | count |
|---|---|---|---|---|
| cash | 0.020 | 1.098 | 4.476 | 8 |
| cash | 0.050 | 1.242 | 2.428 | 8 |
| cash | 0.100 | 1.031 | 1.381 | 8 |
| non_operating | 0.020 | 0.136 | -1.912 | 28 |
| non_operating | 0.050 | 1.171 | -5.071 | 28 |
| non_operating | 0.100 | 0.498 | -0.473 | 28 |

## Firm counts

| group | firms | beta_C_median |
|---|---|---|
| L | 50 | 0.981 |
| M | 50 | 0.970 |
| S | 50 | 1.179 |

## Runs by variant

| tag | agent_structure | model_key | prompt_version | runs | valid |
|---|---|---|---|---|---|
| ext | P | primary | v1.2 | 2690 | 0.998 |
| ext | P | primary | v1.2_instr | 1500 | 0.998 |
| ext | R | primary | v1.2 | 1500 | 0.999 |
| ext | T | comparison | v1.2 | 3000 | 1.000 |
| main | T | primary | v1.2 | 42160 | 0.997 |
| pilot | P | primary | v1 | 1230 | 0.998 |
| pilot | T | primary | v1.1 | 1230 | 0.999 |
| pilot | T | primary | v1.2 | 850 | 1.000 |
| smoke | P | primary | v1 | 8 | 0.875 |
