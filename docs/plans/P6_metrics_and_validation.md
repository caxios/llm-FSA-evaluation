# P6 — Metrics Library & Synthetic Validation

| Item | Value |
|---|---|
| Roadmap | R§8 |
| Weeks | 5–6 |
| Status | Implemented 2026-10-05 (synthetic validation passed on 150 firms) |
| Version | v0.1 (2026-10-05) |
| Depends on | P3 (perturbation metadata), P5 (run-level table, synthetic agents, `valuation_tools`) |
| Unlocks | P7 (hard gate: no paid pilot call before this phase passes) |

> **Implementation notes (2026-10-05)** — see `docs/decisions_log.md` (P6 decisions):
> - Code: `src/metrics/{cells,bootstrap,baseline,elasticity,response,self_consistency,decomposition,memory_quiz,identification,dilution,failure_modes,firm_table,synthetic_validation}.py`; script `scripts/synthetic_validation.py`; report `docs/synthetic_validation.md` (under `docs/` because `results/qa/` is not tracked). The run table gained a `schema_name` column; `NullCache` in `src/runner/cache.py` runs synthetic agents without storing records. New synthetic agent: `ConditionMixtureAgent`.
> - 150-firm run (n = 10, noise 5%, 804 s): every pass band met; bootstrap CI coverage 96.5%. Oracle β 0.998–1.001 by condition, R 0.99–1.02, ε 0, R_dil 1.01–1.04, E9 success 100%; anchored β ≈ 0; mixture β 0.600; decomposition 0.005 / 0.198 / 0.299; NoDilution R_dil 0.04 and 100% reflection; CalcError ε 10.0% and 100% computation.
> - Findings for the pilot: (1) 9 firms have a non-positive oracle value (heavy losses or net debt); a baseline-value ≤ 0 exclusion rule may be needed. (2) With 5% noise the §6.8 size rule keeps only 33 firms for cash and 52 for non-operating assets (the precision bound exceeds the 10% cap or the cash balance for the rest); real-model noise is larger (P5 smoke run), so E3 coverage must be checked in the pilot. (3) Only 21 of 50 CB firms are in the money from the oracle's own valuation; the theoretical dilution is 0 for the rest.

## 1. Objective

Implement every metric of §5 as a function of the run-level table. Then show, with synthetic agents whose true behavior is known, that the full pipeline (perturb → run → parse → metric) recovers that behavior.

## 2. Entry conditions

- Run-level parquet format fixed (P5 §5.7).
- `PerturbMeta` fields fixed (P3 §5.1).
- Synthetic agents implemented (P5 Step 9).

## 3. Decisions resolved in this phase

| ID | Decision | Recommendation |
|---|---|---|
| D6.1 | Share count used for theoretical per-share changes | The agent's own `shares_used`, median over the baseline cell. This measures fidelity to the agent's own valuation and avoids imposing a share-class convention |
| D6.2 | Baseline cell for each single-item perturbation | Same firm, condition C, k = 1, unperturbed (the E0 cell) |
| D6.3 | Baseline for CB experiments | V1 (CB terms removed). Changes V0/V2/V3 vs V1 measure how much the CB information moves the value (§7.4: "R_dil (V0 vs V1)") |
| D6.4 | Bootstrap unit | Resample runs within each cell (firm × condition × perturbation), 1,000 replicates, fixed seed |
| D6.5 | Elasticity estimator | Per firm × condition OLS of log V on log k using all valid runs, HC3 SE. A median-based version (log of cell medians) is reported as robustness |

## 4. Deliverables

```
src/metrics/__init__.py
src/metrics/cells.py              # cell aggregation helpers
src/metrics/baseline.py
src/metrics/elasticity.py
src/metrics/response.py
src/metrics/self_consistency.py
src/metrics/decomposition.py
src/metrics/memory_quiz.py
src/metrics/identification.py
src/metrics/dilution.py
src/metrics/failure_modes.py
src/metrics/bootstrap.py
src/metrics/firm_table.py
scripts/synthetic_validation.py
tests/test_metrics_*.py
tests/test_metrics_synthetic.py
results/qa/synthetic_validation.md   # generated
```

## 5. Design

### 5.1 Input contract

All metric functions take a filtered `pd.DataFrame` from the run-level table (P5 §5.7) and return DataFrames. They never read files themselves; `firm_table.py` does the I/O. Only `valid == True` rows are used unless stated otherwise. Monetary units: `value_per_share` in KRW; `x_mn` and equity in KRW million (×1e6 to convert).

### 5.2 Metric specifications

**Baseline (E0)** — `baseline.py`
```python
def baseline(runs) -> pd.DataFrame
# per firm × condition × agent × model:
# v0 = median(value_per_share), sigma = std(value_per_share, ddof=1), mad,
# n_valid, n_total, compliance = n_valid/n_total,
# shares_agent = median(shares_used), equity_agent = median(equity_value)
```

**Elasticity (E2)** — `elasticity.py`
```python
def firm_elasticity(runs) -> pd.DataFrame
# per firm × condition: beta, se_hc3, alpha, n_used, n_nonpositive_dropped,
# beta_quad (coef on (log k)^2 from the quadratic fit), p_quad, beta_median_based
```

**Response ratio (E3)** — `response.py`
```python
def theoretical_delta(meta: PerturbMeta, v0: float, shares_agent: float) -> float
#   cash:          -x_mn*1e6 / shares_agent
#   non_operating: +x_mn*1e6 / shares_agent
#   shares:         v0/m - v0
#   scale:          v0*(k-1)
def response_ratio(base_runs, pert_runs, delta_star, n_boot=1000, seed=0) -> dict
#   point = (median(pert) - median(base)) / delta_star ; ci_lo, ci_hi (percentile bootstrap)
def min_perturbation(sigma, n, target_se=0.1) -> float
```
`delta_star` uses `v0` and `shares_agent` from the baseline cell (D6.1, D6.2).

**Self-consistency (E1)** — `self_consistency.py`
```python
def recompute(output: ValuationOutput) -> Recomputed
#   ev_re      = dcf_value(fcff, wacc, g, reported convention)
#   equity_re  = ev_re - net_debt + non_operating_assets_added
#   vps_re     = equity_re / shares_used   (diluted shares if dilution_applied)
#   also stage-wise: ev_gap, equity_gap (given reported EV), vps_gap (given reported equity)
def epsilon(output) -> dict
#   eps = |vps_reported - vps_re| / |vps_re| ; eps_alt (other convention); stage gaps
```
Stage gaps show *where* the reported number departs from the agent's own chain (discounting, bridge, or division). FCFF itself is not recomputed from growth/margin assumptions, because the schema does not carry all FCFF components (documented limitation).

**Decomposition (E4)** — `decomposition.py`
```python
def decompose(betas: pd.DataFrame) -> pd.DataFrame
# per firm: total = bA - bC, industry = bA - bB, name = bB - bD, memory = bD - bC (= E_i)
# shares of total; bootstrap SEs via bootstrap.py (re-estimating all four betas per replicate)
```

**Memory strength (E6)** — `memory_quiz.py`
```python
def score_quiz(responses: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame
# per firm × rep × item: score in {0,1}
#   numeric items (Q1–Q4): 1 if |ans/true - 1| <= 0.20 ; Q3 also requires sign(ans)==sign(true); None -> 0
#   Q5: fuzzy/keyword match to main_business keywords (list maintained in quiz_truth); ambiguous
#       answers are written to a review file and scored by a person
#   Q6: exact market match
def memory_strength(scores) -> pd.DataFrame     # M_i = mean over items of mean over reps; p_mem = median Q4 answer
```
Unit handling: the quiz schema asks for numbers in KRW with an explicit unit field (`억원`, `조원`, `원`); the scorer converts before comparing.

**Identification (E5)** — `identification.py`
```python
def identification_rate(responses, identifiers) -> pd.DataFrame
# a guess counts as correct if guess_ticker == ticker, or the normalized guess_name matches
# any name variant (identifier dictionary, P4); per firm × condition: rate over (k × reps)
```

**Dilution (E8)** — `dilution.py`
```python
def theoretical_diluted_value(E, N, F, Pc) -> tuple[float, float, float]   # (v_star, v_debt, delta)
def cb_theory_for_variant(variant, base_cell, cb_truth, perturb_meta) -> float
#   E = equity_agent from the V1 cell (KRW), N = shares_agent from the V1 cell,
#   F, Pc from cb_truth (modified per variant meta: V2 -> 2F, V3 -> Pc_new); V4 -> 0
def r_dil(v1_runs, vj_runs, delta_star) -> dict                             # via response_ratio
def dose_response(runs_by_variant, theory_by_variant) -> dict
#   per firm: regress (v_run - median(V1 runs)) on theory_j across runs of V0, V2, V3 (and V1 at 0);
#   returns slope, se_hc3, intercept
def placebo_shift(v1_or_v0_runs, v4_runs) -> dict                          # difference + TOST inputs
```
If $E/N \le P_c$ for a firm (out of the money from the agent's own valuation), the theoretical change is 0. That firm is excluded from $R_{dil}$ (division by ~0) and reported separately with its actual change.

**Failure stages (E9)** — `failure_modes.py`
```python
def classify(output: ValuationOutput, truth_convertible_shares: float, basic_shares: float) -> str
# 1. extraction_failure: convertible_shares is None or |cs/truth - 1| > 0.05
# 2. reflection_failure: shares_used within 0.5% of basic shares (dilution not used in the per-share value)
# 3. computation_failure: |vps - recompute(output).vps_re| / vps_re > 0.02
# 4. success
```
Applied to V0, V2, V3 runs (where dilution is theoretically relevant), with the correct truth for each variant.

**Firm table** — `firm_table.py`
`build_firm_table(run_tables, ground_truth, sample) -> pd.DataFrame` (one row per firm × model × agent structure; written to `results/firm_level.parquet`):

| Column group | Columns |
|---|---|
| Identity | firm_id, group, ksic, market_cap, newsworthiness, cb_complex |
| Baseline | v0_C, sigma_C, compliance_C, shares_agent, equity_agent |
| Elasticity | beta_{A,B,D,C}, se_{A,B,D,C}, beta_quad_C |
| Decomposition | industry_eff, name_eff, memory_eff (E_i), total_atten, bootstrap SEs |
| Response | R_cash, R_shares, R_nonop (+ CIs), R by tier (2/5/10%) |
| Self-consistency | eps_mean, eps_median, share_eps_gt_5pct |
| Memory / ID | M_i, p_mem, id_rate_{A,B,D} |
| E7 | p_old, p_new, v_A_e7, v_C_e7 |
| CB | R_dil_V0, R_dil_V2, R_dil_V3, dose_slope, dose_intercept, placebo_shift, failure-stage shares |
| QA | anomaly_rate, low_validity flags, n_nonpositive |

### 5.3 Synthetic validation (`scripts/synthetic_validation.py`)

Runs the full runner path (job builders → synthetic agents → cache → run table → metrics) on the 5 fixture packages (fast, part of `pytest`) and on all 150 real packages (script, after P2), with n = 10:

| Agent | Expected | Pass band |
|---|---|---|
| Oracle (noise 5%) | β ≈ 1 in all conditions; R ≈ 1 for all single-item types; ε ≈ 0; R_dil ≈ 1; E9 = success | mean β ∈ [0.95, 1.05]; mean R ∈ [0.9, 1.1]; ε < 1%; ≥ 95% success |
| Anchored | β ≈ 0; R ≈ 0 | \|mean β\| < 0.05; \|mean R\| < 0.1 |
| Mixture(w = 0.6) | β ≈ 0.6 | mean β ∈ [0.55, 0.65] |
| Condition-dependent mixture (w = 1, 1, 0.8, 0.5 for A, B, D, C) | Decomposition recovers industry ≈ 0, name ≈ 0.2, memory ≈ 0.3 | each within ±0.05 |
| NoDilution | R_dil ≈ 0; E9 = reflection failure | \|R_dil\| < 0.1; ≥ 95% reflection |
| CalcError | ε ≈ 10%; E9 = computation failure | ε ∈ [9%, 11%]; ≥ 95% computation |

The bootstrap CI coverage is also checked: across 200 simulated Oracle firms, the 95% CI for R should contain 1 in 93–97% of firms.

Report: `results/qa/synthetic_validation.md` (table of expected vs recovered values, pass/fail).

## 6. Step-by-step tasks

1. `cells.py` (group-by helpers, valid filtering) + `baseline.py`. Tests on a hand-made DataFrame. Commit.
2. `elasticity.py`. Tests: exact recovery on noiseless data (β = 0.7 → 0.7); non-positive dropping; quadratic detection on a curved pattern. Commit.
3. `response.py` + `bootstrap.py`. Tests: theoretical deltas for each type; point estimate on hand data; bootstrap determinism with seed. Commit.
4. `self_consistency.py`. Tests: consistent output → ε = 0; perturbed final value → known ε; stage gaps locate an injected bridge error. Commit.
5. `decomposition.py`. Tests: identity `total = industry + name + memory`. Commit.
6. `memory_quiz.py`, `identification.py`. Tests: unit conversion, sign rule, "모른다" handling, name normalization. Commit.
7. `dilution.py`, `failure_modes.py`. Tests: §E8 worked example (Δ = −400); out-of-the-money → 0 and excluded; each failure class triggered by a crafted output. Commit.
8. `firm_table.py`. Test: builds from a synthetic run table with all columns present. Commit.
9. `tests/test_metrics_synthetic.py` (fixtures, small n) and `scripts/synthetic_validation.py` (full). Run; fix until all pass bands are met. Commit the report.

## 7. Tests

Unit tests per module plus the synthetic end-to-end test. Coverage target ≥ 90% for `src/metrics/`.

## 8. Exit criteria & verification

- [x] Every row of the §5.3 table passes on fixtures (pytest, noise 2%) and on the 150 real packages (script, noise 5%).
- [x] CI coverage check within 93–97% (96.5%).
- [x] Report written (`docs/synthetic_validation.md`; not yet committed).
- [x] D6.1–D6.5 recorded.

## 9. Risks & fallbacks

| Risk | Fallback |
|---|---|
| Oracle fails on some real packages (e.g., negative FCFF → negative value) | Expected for some firms; record them. These firms will also be problematic for real agents, so flag them for the pilot (possible exclusion rule: baseline value ≤ 0) |
| Bootstrap too slow for 150 firms × many cells | Vectorize medians with numpy; parallelize over firms with `joblib` |
| Q5 scoring too subjective | Keyword lists fixed before scoring; a second person scores a 20% sample; report agreement |
