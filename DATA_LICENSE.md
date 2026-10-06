# Data license

| Material | License / terms |
|---|---|
| Code (`src/`, `scripts/`, `tests/`) | MIT (see `LICENSE`) |
| Paper text and figures (`paper/`) | CC BY 4.0 |
| Derived firm-level metrics (`results/firm_level*.parquet`, `results/tables/`) | CC BY 4.0 |
| Parsed model outputs (`results/runs/*.parquet` in the replication package) | CC BY 4.0, subject to the Google Gemini API terms of service that govern model outputs |
| Prompts (`src/agents/prompts/`) | CC BY 4.0 |
| Input packages (`data/processed/packages/`, in the replication package) | Derived from OpenDART public filings (source: Financial Supervisory Service, OpenDART); CC BY 4.0 for the processing |
| Raw OpenDART filings and KRX market data | **Not redistributed.** Re-fetch them with `scripts/fetch_all.py` under your own OpenDART and KRX Open API keys and their terms of use |
| Ground-truth price files (`anchor_prices`, `cb_truth`, prices in `quiz_truth`) | Not redistributed (derived from KRX prices); rebuilt by `scripts/build_packages.py`. The package includes `quiz_truth_no_prices.parquet` |
| Model-call cache (`results/cache/calls.sqlite`: full prompts and responses) | Not included (size); available from the author on request |
| Reviewed Q5 keywords (`data/ground_truth/q5_keywords.csv`) | CC BY 4.0 (derived from public annual reports) |

The CC BY 4.0 materials require attribution. Cite the paper (see `CITATION.cff`).
