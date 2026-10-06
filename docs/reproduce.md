# Reproducing the results

There are three levels of reproduction. Each one needs less than the one before it.

| Level | What it reproduces | Needs | Time |
|---|---|---|---|
| 1. Analysis only | Every table, figure and test in the paper | This repository + the replication package (`replication_data.zip`) | about 5 minutes |
| 2. Re-parse and re-score | Firm-level metrics from the stored model outputs | Level 1 | about 5 minutes |
| 3. Full re-run | Data fetch, packages, model calls | OpenDART and KRX Open API keys, a Google Gemini API key, about USD 100 | days (API rate limits) |

## Setup

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"   # Windows
# uv pip install --python .venv/bin/python -e ".[dev]"         # macOS/Linux
.venv/Scripts/python -m pytest                                 # no network needed
```

## Level 1–2: analysis from the replication package

1. Unzip `replication_data.zip` at the repository root. It restores the following (see its `MANIFEST.sha256`):
   - `results/runs/*.parquet` and `results/firm_level*.parquet`;
   - `data/processed/sample.parquet`, `data/processed/packages/`, `data/processed/identifiers/` and `data/processed/fake_names.parquet`;
   - the size decisions, the reviewed Q5 keywords and `quiz_truth_no_prices.parquet`.
2. Run:
   ```bash
   .venv/Scripts/python scripts/run_analysis.py --reuse   # tests, tables, figures from the shipped firm tables
   .venv/Scripts/python scripts/build_paper_figures.py    # title-free figures for the paper
   cd paper && latexmk -pdf main.tex                      # the paper
   ```
3. Outputs go to `results/hypothesis_table.md`, `results/summary.md`, `results/tables/` and `results/figures/`.

Rebuilding the firm tables from the run tables (level 2: `run_analysis.py` without `--reuse`) also needs the KRX-derived truth files (quiz prices for M_i, anchor prices for H2c). They are not redistributed, so rebuild them at level 3. The shipped firm tables already contain every derived metric.

## Level 3: full re-run

| Step | Command | Phase |
|---|---|---|
| Raw data (DART, KRX, prices) | `python scripts/fetch_all.py --stage all` | P1 |
| Packages, sample, ground truth | `python scripts/build_packages.py --stage all` | P2 |
| Identifiers, fake names, redaction check | `python scripts/build_conditions.py` | P4 |
| Pilot | `python scripts/pilot.py e0` … `report` | P7 |
| Main run (frozen check first) | `bash scripts/run_main.sh` | P8 |
| Extensions | `python scripts/build_e10_filler.py`, then `bash scripts/run_ext.sh` | P9 |
| Analysis | `python scripts/run_analysis.py` | P10 |

Notes:
- Model calls are cached by a hash of the rendered prompt, the agent identity and the repetition (`results/cache/calls.sqlite`). Re-running a step costs nothing for calls that are already cached.
- Exact model outputs are not reproducible across provider-side model updates. The run tables record `model_reported` for each call.
- The preregistration is frozen at the git tag `prereg-v1`. The datasets are tagged `data-v1` (main run) and `data-v2` (extensions and post-results additions). Every deviation is logged in `docs/decisions_log.md`.
