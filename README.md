# LLM Valuation Filing-Fidelity Study

Do LLM valuation agents compute from filings or recall from memory? Metamorphic tests on Korean listed firms.

- Research plan (Korean): [`llm_valuation_research_plan.md`](llm_valuation_research_plan.md)
- Implementation roadmap: [`implementation_plan.md`](implementation_plan.md)
- Phase plans: [`docs/plans/`](docs/plans/README.md)
- Decisions: [`docs/decisions_log.md`](docs/decisions_log.md)

## Setup

Requires Python ≥ 3.11 (developed on 3.12).

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"   # Windows
# uv pip install --python .venv/bin/python -e ".[dev]"         # macOS/Linux
cp .env.example .env   # then fill in the keys
```

Checks:

```bash
.venv/Scripts/ruff check .
.venv/Scripts/python -m pytest
```

## Layout

```
config/        YAML configuration (models, sample, experiments, budget)
src/           Library code (imported as src.<module>)
  data/        DART/KRX/price clients, input packages
  perturb/     Accounting-consistent perturbations
  conditions/  Redaction and fake names (conditions A/B/D/C)
  agents/      LLM clients, agent structures, prompts
  parse/       Output schema and validation
  runner/      Cache, logging, experiment runner
  metrics/     β, R, ε, E_i, M_i, dilution, failure stages
  analysis/    RQ1–RQ3 analyses
  utils/       Hashing, raw I/O, logging
scripts/       Command-line entry points; probes/ for live API checks
tests/         pytest suite (no network); fixtures/ holds recorded responses
data/          raw/ and processed/ are not committed
docs/          Plans, decisions, memos
```

Raw DART/KRX data is never committed or redistributed; it is reproducible from the scripts.
