# P7 — Pilot & Go/No-Go

| Item | Value |
|---|---|
| Roadmap | R§9 |
| Weeks | 6–8 |
| Status | In progress: round 2 (T + v1.1) passes G1–G3; G4 fails — design decision pending |
| Version | v0.1 (2026-10-05) |
| Depends on | P1–P6 exit criteria, especially the P6 synthetic-validation gate |
| Unlocks | P8, P9, P10 |

> **Progress notes (2026-10-05)** — `docs/pilot_report.md` (generated + interpretation):
> - Built: `config/pilot.yaml`, `scripts/build_dev_set.py` (dev set X001–X005: KOSPI ranks 51–52 and 101, two deep out-of-the-money KOSDAQ CB issuers that cannot enter the S group), `scripts/pilot.py` (stages dev, e0, e2, e6, size, e3, report), `src/analysis/pilot_report.py` (+ test). `SampleStore(dev=True)` serves the dev set.
> - Dev set (prompt v1): 100% compliance, no unit slips → v1 kept at Step 1.
> - Round 2 (2026-10-06, T + prompt v1.1, 1,230 calls): G1 PASS, G2 PASS, unit slips 0%, G3 −0.08; G4 FAIL 0/10 (model-invented D&A; §6.8 parameters need CV ≤ 3.2%). See `docs/pilot_report.md` "Round 2".
> - Round 1 pilot L (1,230 calls): G1 PASS 99.8%; G2 FAIL (median ε 81%, error in discounting); G4 FAIL 0/10; unit slips in 24% of E0 runs for the largest firms; G3 not interpretable. E3 not run (no feasible size). Pilot S / E8 / G5 / preregistration wait for KRX KOSDAQ.

## 1. Objective

Run a reduced version of the core experiments on 20 firms to (a) evaluate gates G1–G5, (b) measure noise, tokens, and cost, (c) set `n`, perturbation sizes, and the primary agent structure, and (d) freeze everything in a preregistration before the main run.

## 2. Entry conditions

- P6 synthetic validation passed on all 150 packages.
- Real-model smoke run (P5 Step 11) inspected.
- Budget for the pilot approved (estimate from `--dry-run`, expected ~3,500 calls).

## 3. Decisions resolved in this phase

| ID | Decision | How |
|---|---|---|
| D6 | Primary agent structure (P or T) | Gate G2 |
| D7.1 | `n` policy | From the σ stability analysis (§6 Step 4) |
| D7.2 | Perturbation sizes for E3 | `sizing.decide_size` with pilot σ |
| D7.3 | k grid for conditions A and B | Keep 5 points unless the budget requires {0.5, 1.0, 2.0} |
| D7.4 | Role of `T_pre` (see P1 Step 11) | **Resolved 2026-10-05**: optional exploratory replication of E2 (conditions A and C, ~20 firms). The pilot only decides whether the budget allows it |
| D3.3 | V3 conversion-price ratio | **Resolved 2026-10-05** (floor-consistent price). The pilot checks the V3 anomaly-flag rate and how many firms are excluded because Pc is already at the floor |
| D7.5 | Exclusion rule for non-positive baseline values | Exclude firms whose E0 median value ≤ 0 from log-based analyses (decide based on pilot frequency) |

## 4. Deliverables

```
config/pilot.yaml                    # pilot firm list and module scope
src/analysis/pilot_report.py
docs/pilot_report.md                 # generated + written interpretation
docs/preregistration.md              # frozen
config/experiments.yaml              # final n, sizes, k grid
data/processed/size_decisions.parquet
git tag: prereg-v1
```

## 5. Design

### 5.1 Pilot firm selection

| Set | Firms | Selection |
|---|---|---|
| Dev set | 5 firms **outside** the 150-firm sample (2 large, 1 mid, 2 small with CB) | For prompt iteration only. Prompts may be edited while looking at dev-set outputs, never pilot or main outputs |
| Pilot L | 10 of the 50 large caps | Every 5th by market-cap rank (ranks 1, 6, 11, …), so the full range is covered |
| Pilot S | 10 of the 50 small caps | 7 plain CB, 3 complex CB; spread in dilution potential |

Pilot firms stay in the main sample. Their pilot runs are **not** reused in the main analysis unless the prompt version and settings are identical (the cache handles this automatically: identical requests are cache hits).

### 5.2 Pilot scope and call budget

| Module | Cells | Reps | Calls |
|---|---|---|---|
| E0 (C, k=1) | 20 firms | 20 (for σ stability) | 400 |
| E2 (C, A × k ∈ {0.5, 0.8, 1.25, 2.0}; k=1 for A) | 20 × (4 + 5) | 10 | 1,800 |
| E3 cash (rule size + 2/5/10% tiers) | 20 × 4 | 10 | 800 |
| E8 V0, V1, V2, V3 | 10 × 4 | 10 | 400 |
| E6 quiz | 20 | 3 | 60 |
| **Total** | | | **~3,460** |

V3 is added to the research plan's pilot scope (§12.1 lists V0–V2) because the D3.3 choice needs evidence.

Order: E0 first (σ needed for E3 sizing), then E2, E6, E8, then E3 after sizing.

## 6. Step-by-step tasks

1. **Prompt iteration on the dev set** (days 1–3). Run E0/E2 (C) and E8 V0 on dev firms; fix schema compliance problems and prompt ambiguities. Every change bumps the prompt version (`v1` → `v1.1` …). Stop iterating once compliance ≥ 95% on the dev set. Log changes.
2. **E0** on pilot firms with n = 20 (`--tag pilot`).
3. **E2, E6, E8** (`--tag pilot`).
4. **σ stability analysis** (`pilot_report.py`): for each firm, compare σ estimated from the first 5, 10, 15, 20 reps; compute the relative change. Choose the per-firm `n` rule by inverting the §6.8 lower bound: `n_i = clamp(ceil(2 × (σ_i / (s* × |ΔV*_i|))²), n_min, n_max)`, with a default of 10 when σ is stable at 10.
5. **Sizing**: run `decide_size` for all pilot firms; then run **E3** at the decided sizes + tiers.
6. **Compute metrics** with P6 functions; generate `docs/pilot_report.md`.
7. **Gate evaluation** (table below). Write the interpretation section by hand.
8. **Cost re-estimate**: measured mean tokens per module × main-design job counts; compare with `config/budget.yaml`; apply R§15 levers if over.
9. **Freeze**: write the preregistration (§6.2), update `config/experiments.yaml`, commit, tag `prereg-v1`.

### 6.1 Gate definitions (operational, used in Step 7)

| Gate | Metric | Pass | If failed |
|---|---|---|---|
| G1 Schema | Valid runs / all runs (after retries), all pilot modules | ≥ 95% | Simplify schema; enable structured output; consider model swap (requires re-running P7 for the new model) |
| G2 Calculation | Share of valid structure-P runs with ε > 5% | < 30% | Switch the primary structure to T (D6); re-run E0/E2 for 5 pilot firms with T to confirm compliance |
| G3 Signal | Large caps: mean(β_A − β_C), with 90% bootstrap CI over firms | CI excludes 0, **or** \|mean\| ≥ 0.10 | Re-weight the paper toward RQ3 and H4; RQ1/RQ2 still run but are reported as possibly null |
| G4 Measurability | Share of pilot firms with `status ∈ {ok, increased_n}` and `n ≤ 20` for the cash perturbation | ≥ 80% | Raise `n_max`; drop noisy firms from E3 (documented); consider larger floor (e.g., 7%) |
| G5 Data | Count of ITM small caps with verified CB ground truth (from P2) and pilot E8 runs that are valid | ≥ 30 firms in sample; E8 validity ≥ 90% | Extend the CB window; include BWs; shrink S group |

Additional pilot diagnostics (not gates, but reported): anomaly-flag rate by perturbation type, refusal rate, share of non-positive values, latency, tokens per call by module, R by tier (size dependence), quiz $M_i$ spread between L and S.

### 6.2 Preregistration contents (`docs/preregistration.md`, used in Step 9)

1. Research questions and hypotheses: primary (H1, H2a, H2b, H3) vs exploratory, copied from §4.2 with exact test statistics and directions.
2. Sample: final firm list (hash of `sample.parquet`), exclusion rules.
3. Models: ids, cutoffs, decoding settings, agent structure.
4. Prompts: versions and sha256 hashes.
5. Experiments: modules, conditions, k grid, perturbation sizes per firm (hash of `size_decisions.parquet`), `n` rule.
6. Measures: definitions referencing `src/metrics` functions and the code commit.
7. Analysis: tests, weighting, Holm correction across the four primary hypotheses, α = 0.05, robustness list.
8. Missing data and exclusions: P5 §5.5 rules, D7.5.
9. Deviations policy: any change after the tag is logged with date and reason in `decisions_log.md` and reported in the paper.

## 7. Tests

No new library code beyond `pilot_report.py`; add a test that the report builds from a synthetic run table.

## 8. Exit criteria & verification

- [ ] All five gates evaluated, with numbers, in `docs/pilot_report.md`.
- [ ] All decisions in §3 recorded.
- [ ] Main-run cost estimate within budget (or levers applied and documented).
- [ ] `prereg-v1` tag exists; prompt hash test pins the registered templates.
- [ ] Update the P8–P10 plans with the final parameters, changing their status from Provisional to Ready.

## 9. Risks & fallbacks

| Risk | Fallback |
|---|---|
| Several gates fail at once | Hold a design review before any main-run spending; options include model change, structure T, or narrowing the paper to RQ3 + H4 |
| Pilot shows strong anomaly flagging of perturbed inputs | Inspect the flagged notes; fix the specific inconsistency in P3; re-pilot the affected module only |
| Dev-set prompt tuning leaks into pilot (temptation to keep editing) | Prompt edits after step 1 require a decisions-log entry and a full pilot re-run of affected modules |

## 10. Assumptions to revalidate

- ~3,500 pilot calls fit the pilot budget at measured token counts.
- σ at n = 10 is stable enough for most firms.
