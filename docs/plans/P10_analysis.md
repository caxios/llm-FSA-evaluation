# P10 — Analysis

| Item | Value |
|---|---|
| Roadmap | R§12 |
| Weeks | 16–19 (code written in weeks 12–15 on pilot data) |
| Status | Done (2026-10-06): `scripts/run_analysis.py` on `data-v2`; report `docs/results_report.md` |
| Version | v0.1 (2026-10-05) |
| Depends on | P8 (`data-v1`), P9 (`data-v2`), P7 preregistration |
| Unlocks | P11 |

## 1. Objective

Produce every preregistered test, robustness check, table, and figure with scripts only, from the frozen firm-level and run-level datasets, so the whole results section can be regenerated with one command.

## 2. Entry conditions

- `data-v1` (and `data-v2` if extensions ran) tagged.
- Analysis code already developed and tested on pilot data and synthetic data (see Step 1). Writing analysis code before seeing main results keeps the analysis honest.

## 3. Decisions resolved in this phase

None planned; everything comes from the preregistration. Exploratory additions are allowed but are labeled exploratory in outputs (`exploratory=True` in the table metadata).

## 4. Deliverables

```
src/analysis/common.py           # loading, weighting, Holm, table writers
src/analysis/rq1.py
src/analysis/rq2.py
src/analysis/rq3.py
src/analysis/h4.py
src/analysis/robustness.py
src/analysis/figures.py
src/analysis/summary.py
scripts/run_analysis.py          # one command: everything
tests/test_analysis_*.py
results/tables/*.csv, *.tex
results/figures/*.pdf, *.png
results/summary.md
results/hypothesis_table.md
```

## 5. Design

### 5.1 Data inputs

- `results/firm_level.parquet` (one row per firm × model × agent × prompt version).
- Run-level tables for pooled models (`rq1` mixed model, dose-response).
- `sample.parquet` and ground truth for covariates.
- The analysis records the dataset tag and code commit in every output file header.

### 5.2 Hypothesis tests

| H | Script | Data | Test | Output |
|---|---|---|---|---|
| H1 (primary) | `rq1.py` | Large caps, β_C | One-sided test of inverse-variance-weighted mean < 1 (weights 1/se²; z-test with a random-effects variance estimate, DerSimonian–Laird). Robustness: unweighted t-test, Wilcoxon signed-rank vs 1 | T2 |
| H1b | `rq1.py` | All runs, condition C | Pooled model: log V = firm FE + (b + b_S·Small + b_M·Mid)·log k, SEs clustered by firm; test b_S > 0. Alternative: `MixedLM` with random slopes | T3 |
| — nonlinearity | `rq1.py` | Per firm | Share of firms with a significant quadratic term; mean β_quad | T3 note |
| H1c | `rq1.py` | ε by group | Median ε by group; Mann–Whitney L vs S | T4 |
| H2a (primary) | `rq2.py` | E_i, all firms (and by group) | One-sided Wilcoxon signed-rank E_i > 0 | T5 |
| — decomposition | `rq2.py` | Four components | Means, bootstrap CIs, share of total attenuation | T5 |
| H2b (primary) | `rq2.py` | E_i vs M_i | WLS: E_i ~ M_i + ln(mcap) + industry FE + id_rate_D, weights 1/se(E_i)², HC3; one-sided γ1 > 0. Report OLS too, VIFs, and stratified-by-mcap-tercile estimates if VIF(M_i) > 5 | T6 |
| H2c | `rq2.py` | E7 firms | OLS: log V_C = a + b1 log V_A + b2 log P_old + e, HC3; b2 > 0 | T7 |
| H2d | `rq2.py` | β_A − β_B | Wilcoxon vs 0; by-industry means compared with the direction reported by Lee et al. (2025) | T8 |
| H3 (primary) | `rq3.py` | S firms, R_dil (V0 vs V1) | One-sided test that the inverse-variance-weighted mean < 1; Wilcoxon robustness; ITM-by-agent firms only | T9 |
| H3b | `rq3.py` | E9 classes | Proportions with Wilson CIs; extraction vs reflection comparison (paired by firm, McNemar-type test on firm-level majority class) | T10 |
| H3c | `rq3.py` | Dose-response slopes | One-sided test that the mean slope < 1; intercept distribution | T9 |
| — specificity | `rq3.py` | V4 | TOST per firm with margin ±σ_i; share of firms equivalent; pooled TOST | T9 |
| H4 | `h4.py` | P vs T vs R, 30 firms | Paired comparisons of \|1 − β_C\|, \|1 − R_dil\|, ε (Wilcoxon signed-rank by firm); E9 class proportions by structure | T11 |

**Multiple comparisons**: Holm correction across the four primary p-values (H1, H2a, H2b, H3), implemented in `common.holm()`. Exploratory results are reported with effect sizes and 95% CIs, without correction, and labeled.

### 5.3 Robustness (`robustness.py`) — one row per §7.5 item

| Check | Implementation | Output |
|---|---|---|
| Exclude identified firms | Drop firms with id_rate_D ≥ 0.5 (and separately id_rate_A ≥ 0.5); re-run H2a/H2b | R1 |
| Perturbation size | R by tier (2/5/10%); test of trend across tiers | R2 |
| Half reps | Recompute firm metrics with a random half of reps (100 draws); distribution of primary statistics | R3 |
| Anomaly-flag runs | Exclude runs with `anomaly_flag`; re-run primary tests | R4 |
| Comparison model | Primary tests on the 30-firm subset, both models side by side | R5 |
| Instruction | Paired β_C with vs without rule 6 | R6 |
| Complex CBs | H3 with and without `cb_complex` firms | R7 |
| Low-validity cells | Exclude `low_validity` cells | R8 |
| Median-based β | Repeat H1/H2a with the median-based elasticity | R9 |

### 5.4 Figures (`figures.py`)

| Figure | Content |
|---|---|
| F1 | Design diagram (static, from the paper source) |
| F2 | Distribution of β_C by group (L/M/S), with the β = 1 reference line |
| F3 | Decomposition: stacked bars of industry / name / memory components by group |
| F4 | E_i vs M_i scatter with the WLS fit, points colored by group |
| F5 | E8 dose-response: actual vs theoretical change, pooled with per-firm slopes |
| F6 | E9 failure-stage proportions by agent structure |
| F7 | R by perturbation tier |

Charts follow one consistent style (shared matplotlib style file); colorblind-safe palette.

### 5.5 Hypothesis summary (`summary.py`)

`results/hypothesis_table.md`: one row per hypothesis in §4.2 with: type (primary/exploratory), estimate, CI, p (raw and Holm-adjusted for primary), verdict (supported / not supported / inconclusive), table/figure reference, script reference.

Verdict rule (preregistered): primary hypotheses are "supported" if the Holm-adjusted p < 0.05 in the predicted direction; "not supported" if the CI excludes effects of practical size (e.g., for H1: the 95% CI lower bound of mean β_C > 0.9); otherwise "inconclusive".

## 6. Step-by-step tasks

1. **Weeks 12–15 (during P8/P9)**: implement all scripts against (a) synthetic firm tables from P6 (where the true answers are known) and (b) pilot data. Tests check that each synthetic scenario produces the expected verdict.
2. **Week 16**: run `scripts/run_analysis.py` on `data-v1`; review every table for sanity (sign conventions, units, Ns).
3. **Week 17**: robustness; extension analyses (after `data-v2`).
4. **Week 18**: figures, summary, hypothesis table. A second person re-runs the analysis from a clean clone and checks that outputs match byte for byte (or within floating tolerance).
5. **Week 19**: buffer; exploratory analyses (labeled); write the results narrative notes for P11.

## 7. Tests

| Test | Covers |
|---|---|
| `test_analysis_holm.py` | Holm against a known example |
| `test_analysis_rq*.py` | Each test function on synthetic data with known effect → expected verdict; null data → not significant at the expected rate (simulation, 500 draws, false-positive rate ≈ 5%) |
| `test_analysis_outputs.py` | All tables/figures produced; headers contain dataset tag and commit |

## 8. Exit criteria & verification

- [ ] `python scripts/run_analysis.py` regenerates all outputs from tagged data in one run.
- [ ] Every hypothesis has a row in `hypothesis_table.md`.
- [ ] Independent re-run from a clean clone matches.
- [ ] Deviations from the preregistration listed in `results/summary.md`.

## 9. Risks & fallbacks

| Risk | Fallback |
|---|---|
| Random-effects meta-analysis unstable with heterogeneous se | Report the fixed-effect and unweighted versions alongside; prereg lists all three |
| Strong M_i–mcap collinearity | Stratified estimates; E7 (time-based identification) carries more weight in the discussion |
| Few firms ITM by the agent's own valuation (H3 N small) | Report N prominently; pooled run-level model as a complement |

## 10. Assumptions to revalidate

- Test choices match the frozen preregistration text exactly (update this plan if the prereg changed anything).
