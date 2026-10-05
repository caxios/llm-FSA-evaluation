# P11 — Release & Write-up

| Item | Value |
|---|---|
| Roadmap | R§13 |
| Weeks | 20–24 |
| Status | Provisional |
| Version | v0.1 (2026-10-05) |
| Depends on | P10 outputs |
| Unlocks | — |

## 1. Objective

Write the paper, prepare a public, reproducible release of code and derived data, and submit to the first target venue.

## 2. Entry conditions

- `results/hypothesis_table.md`, all tables and figures final (P10 exit).
- Venue deadlines checked (FinNLP-type workshop, ICAIF, KCI journal); the submission target is set by week 20.

## 3. Decisions resolved in this phase

| ID | Decision | Recommendation |
|---|---|---|
| D11.1 | First venue | Financial NLP workshop if results are mixed or mainly methodological; ICAIF if primary hypotheses are clearly supported with robust results |
| D11.2 | Code license | MIT |
| D11.3 | Data license for released derived data | CC BY 4.0 for firm-level metrics and model outputs, subject to the model provider's terms (check the open-weight license and the comparison model's terms on publishing outputs) |
| D11.4 | Release of raw model responses | Release JSONL responses for the primary (open-weight) model; for the commercial model, release only if its terms permit |
| D11.5 | Archive | Zenodo DOI for the tagged release |

## 4. Deliverables

```
paper/                            # LaTeX source (venue template)
paper/figures -> results/figures (copied at build time)
README.md                         # full reproduction guide
LICENSE
DATA_LICENSE.md
CITATION.cff
release/
  firm_level.parquet
  run_level_primary.parquet       # parsed outputs, no raw DART data
  responses_primary.jsonl.gz      # if D11.4 allows
  prompts/                        # all prompt versions + hashes
  preregistration.md
  decisions_log.md
docs/reproduce.md
```

## 5. Design

### 5.1 Paper outline

1. Introduction: the identification problem with outcome accuracy; the metamorphic-test idea; contributions (§3.6).
2. Related work: knowledge conflicts; financial LLM bias (Lee et al. 2025); AI research evaluation (Haque et al. 2026); look-ahead leakage.
3. Method: metamorphic relations; metrics (β, R, ε, E_i, M_i, R_dil); information conditions; decomposition identity.
4. Data and design: DART, sample, models and cutoffs, agent structures, preregistration.
5. Results: RQ1, RQ2, RQ3, H4.
6. Robustness.
7. Discussion: implications for practice (tool-delegated computation, forced dilution extraction); limitations (no business descriptions in prompts, simplified notes, fixed DCF method, single primary model, forgone-interest simplification, finite-k scale test).
8. Conclusion.
Appendices: schema, prompts, quiz, perturbation details, full robustness tables, deviations from preregistration.

### 5.2 Reproduction tiers (`docs/reproduce.md`)

| Tier | What the user runs | Needs |
|---|---|---|
| 1. Results from released data | `python scripts/run_analysis.py --from-release` | No API keys |
| 2. Rebuild inputs | `fetch_all.py` + `build_packages.py` | DART/KRX keys |
| 3. Re-run model calls | Runner with the released cache or fresh calls | Model API keys; budget |

The release cache (SQLite) for the primary model lets tier 3 re-create the run tables without new calls.

### 5.3 Release checks

- No API keys or `.env` in history (`git log -p | grep` for key patterns; use a secret scanner).
- No raw DART/KRX files in the release (only scripts).
- Personal data: CEO names appear only in raw data and in identifier dictionaries; exclude `data/processed/identifiers/` from the release.
- `pip install` from a clean environment + tier 1 reproduction passes in CI-like conditions (fresh virtualenv on a second machine).

## 6. Step-by-step tasks

| Week | Work |
|---|---|
| 20 | Outline, figures/tables placed, method and data sections drafted (largely from the research plan and phase docs) |
| 21 | Results and robustness sections; limitations |
| 22 | Introduction, related work, abstract; internal review request (advisor/professors, per §16) |
| 23 | Revisions; release packaging; reproduction test on a second machine; Zenodo draft |
| 24 | Final proofreading; submission; publish the release (code public at submission or at acceptance, per venue anonymity rules) |

Note on double-blind venues: keep the repository private, or provide an anonymized mirror (e.g., an anonymous GitHub service) until the review ends.

## 7. Tests

- Tier 1 reproduction runs as an automated test on the release bundle.

## 8. Exit criteria & verification

- [ ] Paper submitted.
- [ ] Release bundle reproduces all tables (tier 1) on a clean machine.
- [ ] Licenses and terms checks recorded in `decisions_log.md`.

## 9. Risks & fallbacks

| Risk | Fallback |
|---|---|
| Venue deadline misaligned with the schedule | Pick the next venue; use the time for additional robustness or the §15 follow-up design |
| Model terms forbid releasing outputs | Release metrics and prompts only; provide scripts to regenerate outputs |

## 10. Assumptions to revalidate

- Venue choice and deadlines (week 20).
- Provider terms on publishing model outputs.
