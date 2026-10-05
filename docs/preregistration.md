# Preregistration

> Skeleton. Filled in and frozen at the end of the pilot (P7), then tagged `prereg-v1`. After the tag, every change is a deviation recorded in `docs/decisions_log.md`.

## 1. Research questions and hypotheses
- Primary (confirmatory, Holm-corrected): H1, H2a, H2b, H3
- Exploratory: H1b, H1c, H2c, H2d, H3b, H3c, H4

## 2. Sample
- Firm list hash (`data/processed/sample.parquet`):
- Exclusion rules:

## 3. Models and agent structures
- Model ids, training cutoffs, decoding settings:
- Primary agent structure:

## 4. Prompts
| Version | File | sha256 |
|---|---|---|

## 5. Measures
- Definitions (code commit):

## 6. Perturbation sizes
- Rule: min(max(precision lower bound, 5% of equity value), 10% cap)
- Size decisions hash (`data/processed/size_decisions.parquet`):

## 7. Number of repetitions (n)
- Rule:

## 8. Analysis plan
- Tests, weighting, Holm correction, α = 0.05:
- Robustness checks:

## 9. Exclusions and missing data

## 10. Deviations policy
