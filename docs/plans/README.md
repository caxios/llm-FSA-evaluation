# Phase Implementation Plans

Detailed, buildable plans for each phase of the roadmap in [`implementation_plan.md`](../../implementation_plan.md). The roadmap says *what* each phase delivers; these documents say *how*: files, interfaces, commit-sized steps, tests, and verification.

## Index

| Phase | Plan | Weeks | Status | Revise after |
|---|---|---|---|---|
| P0 | [Project setup & pre-flight checks](P0_setup_and_preflight.md) | 1–2 | Ready | — |
| P1 | [Data acquisition](P1_data_acquisition.md) | 3–4 | Ready (depends on P0 probe results) | P0 |
| P2 | [Sample selection & input packages](P2_sample_and_packages.md) | 4–5 | Ready (depends on P0 probe results) | P0, P1 |
| P3 | [Perturbation engine](P3_perturbation_engine.md) | 4–5 | Ready (fixture-based) | P2.1 schema freeze |
| P4 | [Information conditions](P4_information_conditions.md) | 5 | Ready (fixture-based) | P2.1 schema freeze |
| P5 | [Agent, runner & parsing infrastructure](P5_agents_runner_parsing.md) | 3–6 | Ready | P0 model choice |
| P6 | [Metrics library & synthetic validation](P6_metrics_and_validation.md) | 5–6 | Ready (fixture-based) | — |
| P7 | [Pilot & go/no-go](P7_pilot_and_gates.md) | 6–8 | Draft | P1–P6 |
| P8 | [Main experiments](P8_main_experiments.md) | 9–13 | Provisional | P7 pilot report |
| P9 | [Extension experiments](P9_extensions.md) | 12–15 | Provisional | P7 pilot report |
| P10 | [Analysis](P10_analysis.md) | 16–19 | Provisional | P7 preregistration |
| P11 | [Release & write-up](P11_release_and_writeup.md) | 20–24 | Provisional | P10 |

**Status meanings**
- **Ready**: can be executed as written.
- **Draft**: structure is fixed; parameters will be filled in from earlier phases.
- **Provisional**: written against assumptions listed at the end of the document; revise before starting the phase.

## Shared conventions

- **Section references**: `§x.y` points to `llm_valuation_research_plan.md`; `R§x` points to the roadmap `implementation_plan.md`.
- **Decision IDs**: roadmap decisions are `D1`–`D8`. Phase-local decisions are `Dn.k` (e.g., `D3.2` = second decision in P3). All resolved decisions are recorded in `docs/decisions_log.md`.
- **Commit-sized steps**: each step in a plan ends in a state where `ruff check` and `pytest` pass, and can be committed on its own.
- **Package layout**: code lives under `src/` and is imported as `src.<module>` (e.g., `python -m src.runner.run`).
- **No network in tests**: tests use recorded fixtures in `tests/fixtures/`. Live-API checks live in `scripts/probes/` and are run manually.

## Plan template

Every phase plan follows the same structure:

1. Objective
2. Entry conditions
3. Decisions resolved in this phase
4. Deliverables
5. Design (interfaces, data shapes)
6. Step-by-step tasks
7. Tests
8. Exit criteria & verification
9. Risks & fallbacks
10. Assumptions to revalidate (for Draft/Provisional plans)

## Updating these plans

At the end of each phase:
1. Mark the phase checklist in the roadmap (R§17).
2. Update the next phase's plan with whatever the finished phase revealed: changed field names, data gaps, parameters chosen.
3. Bump the plan's version line and add a one-line change note at the top.
