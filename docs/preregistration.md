# Preregistration

> Status: **draft, ready to freeze** (2026-10-06). It is frozen by committing it, running `python scripts/prereg_hashes.py --pin`, committing again, and tagging `prereg-v1`. After the tag, every change is a deviation. Each deviation is recorded with a date and reason in `docs/decisions_log.md` and reported in the paper.

## 1. Research questions and hypotheses

RQ1–RQ3 and the hypotheses are taken from `llm_valuation_research_plan.md` §4.

### Primary hypotheses (confirmatory)

Holm correction is applied across these four, at α = 0.05.

| # | Hypothesis | Statistic | Direction / test |
|---|---|---|---|
| H1 | Large caps under the real name respond less than proportionally to scale | Large-cap β_C,i | Inverse-variance weighted mean of β_C < 1, one-sided z test. Robustness: unweighted mean, Wilcoxon signed-rank vs 1 |
| H2a | Revealing the name dampens the response further | E_i = β_D,i − β_C,i (all firms with both β) | Median > 0, one-sided Wilcoxon signed-rank |
| H2b | The firm-memory effect rises with memory strength | γ1 in E_i = γ0 + γ1 M_i + γ2 ln(cap) + industry FE + γ3 id_rate_D + ε | γ1 > 0, one-sided, HC3 standard errors. Robustness: weighted by 1/Var(E_i) |
| H3 | Small caps do not reflect CB dilution in full | R_dil,i (V0 vs V1), ITM firms by the agent's own value | Mean < 1, one-sided t test. Robustness: Wilcoxon |

### Exploratory hypotheses

These are reported with effect sizes and CIs, without multiplicity correction.

| # | Hypothesis |
|---|---|
| H1b | Large caps dampen more than small caps (mixed model b_S > 0) |
| H1c | ε is larger for large caps. Only structure P: ε = 0 by construction under T |
| H2c | Stale-anchor coefficient b2 > 0 (E7) |
| H2d | β_A − β_B > 0 (industry label alone dampens) |
| H3b | Reflection failures exceed extraction failures (E9) |
| H3c | CB dose-response slope < 1 |
| H4 | Structure T is closer to 1 than P on β, R and ε (P9 extension) |

## 2. Sample

- 150 firms:
  - **L**: KOSPI market-cap ranks 1–50.
  - **M**: 50 KOSPI firms from the mid band, split by newsworthiness within cap quintiles.
  - **S**: 50 KOSDAQ issuers with an in-the-money CB at the KRX `T_post` close, ranked by dilution potential, with firms above 100% excluded.
- `T_post` = 2026-04-01; fiscal year 2025.
- Firm list: `data/processed/sample.parquet` (hash in §11).
- Exclusion rules (`docs/sample_report.md`):
  - financial industries (KSIC 64–66);
  - halted on `T_post` (KRX daily volume 0);
  - failed reported-statement identities (D7);
  - fewer than 3 fiscal years;
  - capital impairment;
  - annual report not filed by `T_post` (D2.9).
- Administrative-issue status (D0.6) is not applied. This is a limitation.

## 3. Models and agent structures

- **Primary model:**
  - `gemini-2.5-flash-lite`, via the Gemini OpenAI-compatible endpoint.
  - Training cutoff 2025-01-01.
  - Decoding: temperature 0.3, max output 8,192 tokens, no thinking, JSON-object mode.
- **Primary agent structure: T (D6).**
  - The model returns the inputs (`ToolInputs`).
  - Python computes FCFF, end-of-year discounting, the Gordon terminal value, the equity bridge, per-share value and if-converted dilution.
  - Structure P is kept for H4 (P9).
- Settings: `config/models.yaml`, `config/main_run.yaml`.

## 4. Prompts

Version **v1.2** (hashes in §11):
- v1.1 adds unit rules.
- v1.2 adds "projected D&A = capex" (D7.6).

Prompts used by the main run:
- system: `tool_system_v1_2`;
- user: `valuation_user_v1`;
- E5: `identification_v1`;
- E6: `memory_quiz_v1`.

`valuation_system_v1_2` and `_instr` are registered for structure P and the instruction robustness check.

## 5. Experiments

Modules and order follow `docs/plans/P8_main_experiments.md` §5.1: E6 → E0/E2 → sizing → E5 → E3 (+ tiers) → E7 → E8. Commands are in `scripts/run_main.sh`.

| Module | Conditions | Perturbations | Reps |
|---|---|---|---|
| E0/E2 | A, B, D, C | k ∈ {0.5, 0.8, 1.0, 1.25, 2.0}; the CB block is removed under scale (D3.4) | 10 |
| E3 | C | shares m = 2; cash distribution and non-operating assets at the rule size; tiers 2/5/10% of book equity | n_i from the rule (§7); tiers 10 |
| E5 | A, B, D | k ∈ {1.0, 1.5} | 3 |
| E6 | — | quiz | 3 |
| E7 | A, C | E2 cells at k = 1 | — |
| E8 | C (CB block shown) | V0–V3; V4 placebos (redeemed CB, irrelevant) | 10 |

## 6. Measures

All measures are defined by code in `src/metrics/` at the tagged commit:
- β: `elasticity.firm_elasticity`, OLS of log V on log k with HC3; non-positive values are dropped.
- R: `response.firm_responses`, median-based with a bootstrap CI.
- ε: `self_consistency`.
- E_i decomposition: `decomposition`.
- M_i: `memory_quiz`.
- id rate: `identification`.
- R_dil, dose response, placebo shift: `dilution`.
- Failure stages: `failure_modes`.
- Firm table: `firm_table.build_firm_table`.

Bootstrap: 1,000 resamples of runs within a firm.

## 7. Perturbation sizes and n

- **Size rule (§6.8, D7.7):** x = min(max(lower bound, 5% of the agent's equity value), 20% cap).
  - lower bound = σ √(2/n) / s* × shares, with s* = 0.2.
  - When the bound exceeds the cap at n = 10, n rises in steps of 5 up to 40.
  - When it still exceeds the cap, the firm is excluded from that perturbation.
  - A cash distribution may not exceed the firm's cash.
  - `src/perturb/sizing.decide_size`; parameters in `config/experiments.yaml`.
- **Pilot firms:** their sizes are fixed by the pilot (`data/processed/size_decisions.parquet`, hash in §11).
- **Other firms:** the same rule, applied to the main-run E0 cell (`scripts/size_main.py`) before E3.
- **n:** 10 for E0/E2/E8, and n_i from the size rule for E3.
- **G4 fallback (D7.8):** the pilot showed that few firms satisfy the rule (3 of 20, all at n = 25–30).
  - E3 at the rule size runs only for firms the rule accepts. Excluded firms are listed with the reason.
  - The tier runs (2/5/10% of book equity, n = 10) cover every firm with positive book equity. They are the size-dependence robustness analysis, not a substitute for the rule size.
  - None of the primary hypotheses depends on E3.

## 8. Analysis plan

Research plan §7:
- H1 inverse-variance weighted mean of β_C.
- Mixed model log V = a_i + (b + b_S Small + b_M Mid) log k.
- Quadratic term check.
- H2a Wilcoxon.
- H2b HC3 regression with VIFs. If collinearity is severe, stratify by cap band.
- H3 mean R_dil.
- H3c dose-response slope.
- Placebo TOST within ±σ_i.
- H3b stage shares.
- Holm across H1, H2a, H2b, H3.

Robustness:
- drop identified firms (id_rate ≥ 0.5);
- size tiers;
- half-n resampling;
- excluding anomaly-flagged runs;
- excluding `low_validity` cells;
- comparison model (P9);
- instruction prompt;
- dropping complex CBs.

## 9. Missing data and exclusions

- **Validation:** schema validation allows up to 2 retries in the same conversation. A rep that still fails is stored invalid and not re-run.
- **Low-validity cells:** a cell with < 70% valid runs is flagged `low_validity`. It is kept in the primary analyses and dropped in a robustness check.
- **D7.5:** firms whose E0 median value (condition C, k = 1) is ≤ 0 are excluded from log-based measures (β, E_i, H2b) and from R. They are reported in a table.
  - Non-positive runs inside otherwise positive cells are dropped in log-based fits, and their count is reported.
- **E3 sizing:** firms excluded by the size rule are listed with the reason.
- **E8:** firms whose CB is out of the money under the agent's own value enter the analysis of observed deltas only, not R_dil.

## 10. Pilot results that set these parameters

See `docs/pilot_report.md`. Round 3 used structure T and prompt v1.2 on 10 L + 10 S firms: 3,420 calls, about $4.

| Gate | Result |
|---|---|
| G1 | PASS (100%) |
| G2 | PASS (ε = 0) |
| G3 | PASS: mean β_A − β_C = 0.18, which meets the \|mean\| ≥ 0.10 criterion; 90% CI [−0.13, 0.57] |
| G4 | FAIL (0/20 at n ≤ 20; 3/20 feasible at n ≤ 40); fallback D7.8 |
| G5 | PASS (50 ITM firms; E8 valid 390/390) |

Other pilot findings:
- Noise: CV is 7–38% for most large caps. Most small caps exceed 100%, because loss-making firms get margins of −5%, 0% or +5%, which flips the sign of the value.
- Non-positive baselines: 4 of 20 firms (D7.5).
- Unit slips: 1.5% of runs.
- D&A = capex compliance: 68% of E0 runs.
- Anomaly-flag rate: 0.54–0.87, including 0.56 on unperturbed inputs. Flags are therefore uninformative as a manipulation signal, and the robustness check that excludes flagged runs is reported with this caveat.
- Main-run cost estimate: about $40 (budget $60, `config/main_run.yaml`).
- The research plan's power assumptions are optimistic for small caps. H3 is tested as registered; its precision is reported as is.

## 11. Hashes

Generated by `python scripts/prereg_hashes.py` at the freeze commit (filled at freeze).

## 12. Deviations policy

After the tag:
- Any change to `src/agents/prompts/`, `src/perturb/` or `src/metrics/` is detected by `scripts/check_frozen.py`, which `run_main.sh` runs first.
- Each such change requires a dated `decisions_log.md` entry stating whether completed runs remain valid.
- A prompt change invalidates the affected module's runs under the old version.
- Parser fixes are re-parsed from the stored raw responses.
