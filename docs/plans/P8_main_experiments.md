# P8 — Main Experiments

| Item | Value |
|---|---|
| Roadmap | R§10 |
| Weeks | 9–13 |
| Status | Tooling built (2026-10-06); main run waits for `prereg-v1` and budget confirmation |
| Version | v0.1 (2026-10-05) |
| Depends on | P7 (`prereg-v1` tag, final `config/experiments.yaml`, size decisions) |
| Unlocks | P10 (and P9 cost decision) |

> **Progress notes (2026-10-06)**
> - Built: `src/runner/frozen.py` and `scripts/check_frozen.py` (diff and untracked files under the frozen paths since the tag, plus `registry.FROZEN` hash check); `src/runner/monitor.py` and `scripts/monitor.py` (§5.3 thresholds, journal line, `results/qa/main_run_qa.md`: cell completeness, low-validity cells, non-positive share, extreme values); `scripts/size_main.py` (non-pilot sizes from the main E0 cell; pilot firms keep pilot sizes); `scripts/build_firm_level.py`; `scripts/run_main.sh` (frozen check → per batch dry run → run → monitor); `scripts/prereg_hashes.py` (hash block; `--pin` fills `registry.FROZEN`); `config/main_run.yaml` (T, v1.2, tag `main`, budget). Runner CLI gains `--sizes` and `--tiers` for E3. Tests: `tests/test_frozen_monitor.py`.
> - Not started: the main run itself (needs the P7 freeze, i.e. commit + `prereg-v1` tag, and a confirmed budget).

## 1. Objective

Execute the preregistered main design on all 150 firms with the primary model and primary agent structure. Keep spending, validity, and model-version stability under control, and produce the complete run-level and firm-level datasets.

## 2. Entry conditions

- `prereg-v1` tag exists; the working tree has no changes to `src/agents/prompts/`, `src/perturb/`, or `src/metrics/` since the tag (verified by `scripts/check_frozen.py`).
- Budget for P8 confirmed against the P7 estimate.

## 3. Decisions resolved in this phase

None planned. Any unplanned decision is a deviation and is logged (P7 §6.2 item 9).

## 4. Deliverables

```
scripts/check_frozen.py
scripts/monitor.py
scripts/run_main.sh               # documented sequence of runner commands
results/runs/{E0_E2,E3,E5,E6,E7,E8}.parquet
results/runs/*/YYYYMMDD.jsonl
results/firm_level.parquet
results/qa/main_run_qa.md         # generated per module
docs/run_journal.md               # dated notes: batches, incidents, spend
```

## 5. Design

### 5.1 Execution order and scope

| # | Module | Scope | Calls (n = 10 baseline; actual from the n rule) | Why this order |
|---|---|---|---|---|
| 1 | E6 memory quiz | 150 firms × 3 reps | ~450 short | Cheap; independent; early check of $M_i$ spread |
| 2 | E0 + E2 | 150 × 4 conditions × 5 k × n | ~30,000 | Core; provides baselines for E3 sizing |
| 3 | Sizing | `decide_size` for non-pilot firms using E0 σ | 0 | Needs E0 |
| 4 | E5 identification | 150 × {A, B, D} × k ∈ {1, 1.5} × 3 | ~2,700 short | Needs only packages; placed after E2 so a cost overrun in E2 is caught first |
| 5 | E3 single-item | 150 × {cash, shares, non-op} × n, + cash tiers 2/5/10% | ~4,500 + ~4,500 tiers | Needs sizing |
| 6 | E7 stale anchor | E7 candidates (~40) × {A, C} at k = 1 | ~0–400 (mostly cache hits from E2) | Reuses E2 cells |
| 7 | E8 CB dilution | 50 S × V0–V4 × n | ~2,500 | Independent; last so S-firm E2/E3 issues are known |
| — | E1, E9 | Offline from stored outputs | 0 | — |

Note: E7 as specified (§6.7) uses `t_post` packages in conditions A and C at k = 1, which are exactly E2 cells. It therefore costs nothing extra unless E7 needs more reps for precision. The optional `T_pre` replication (D7.4) runs here as module 8 only if the remaining budget allows (fetch `t_pre` data, build packages, E2 condition A/C on ~20 firms).

Tier runs for E3 (2/5/10%) are part of the preregistered robustness analysis. If budget is tight, run tiers on a random 50% of firms (seeded), as allowed by the preregistration.

### 5.2 Batching

- A batch = one module × one group (e.g., "E2-L"). Each batch is one runner invocation logged in `run_journal.md`.
- Before each batch: `--dry-run` → record job count and estimated cost in the journal.
- After each batch: `scripts/monitor.py --batch <id>` → QA summary; refresh `firm_level.parquet`.

### 5.3 Monitoring (`scripts/monitor.py`)

Reports per batch and cumulative:

| Metric | Stop threshold |
|---|---|
| Valid-run rate | < 90% in a batch → pause, inspect |
| Refusal rate | > 2% → pause |
| Anomaly-flag rate | > 2× the pilot rate for the same module → inspect |
| `model_reported` values | more than one distinct value within the run → halt |
| Spend vs budget | > 80% of P8 budget before module 7 → apply levers |
| Median latency | informational |

### 5.4 Incident protocol

1. Pause the runner (Ctrl-C is safe; the cache is transactional).
2. Record the incident in `run_journal.md` (time, batch, symptom).
3. Diagnose with the JSONL raw responses.
4. If the fix touches frozen code or prompts: log a deviation in `decisions_log.md`. Decide whether completed runs remain valid. A prompt change invalidates all runs under the old version for the affected module (they stay in the cache, but analysis uses one version only).
5. Resume.

Model version change mid-run: completed runs stay valid for the old version. Either finish on the old version (if still served) or re-run the affected module completely on the new version. Never mix versions within a module.

### 5.5 QA after each module (`results/qa/main_run_qa.md`)

- Cell completeness: every firm × condition × perturbation has its planned reps; missing cells listed.
- Validity per cell; `low_validity` cells listed.
- Distribution checks: share of non-positive values; extreme values (> 10× the cell median) listed for manual review. These are not removed; they are reviewed to catch parsing bugs (e.g., unit errors such as KRW vs KRW million).
- Spot check: 10 random raw responses per module read by a person.

## 6. Step-by-step tasks

| Week | Work |
|---|---|
| 9 | `check_frozen.py`, `monitor.py`, `run_main.sh`; E6; E2 for group L |
| 10 | E2 for M and S; sizing for non-pilot firms; QA for E2 |
| 11 | E5; E3 (main sizes) |
| 12 | E3 tiers; E7; E8 |
| 13 | Buffer: re-runs for incidents, low-validity cells (only if allowed by the preregistration), final QA, freeze `firm_level.parquet` (tag `data-v1`) |

## 7. Tests

- `check_frozen.py` test: detects a modified prompt file against the tag.
- `monitor.py` test: thresholds trigger on a synthetic run table.

## 8. Exit criteria & verification

- [ ] All modules complete; overall valid-run rate ≥ 95%; every incomplete cell listed with a reason.
- [ ] Single model version per module confirmed.
- [ ] `results/firm_level.parquet` rebuilt from run tables by one command and tagged `data-v1`.
- [ ] Spend recorded; remaining budget computed for P9.

## 9. Risks & fallbacks

| Risk | Fallback |
|---|---|
| Spend overrun in E2 | Preregistered levers in order: per-firm n (min 5), A/B k grid to 3 points, tier runs on 50% of firms |
| Provider outage or deprecation | Wait/resume; if the model is withdrawn, finish on a second provider serving the same weights only after an equivalence check on 5 firms (E0 distributions); otherwise document the partial completion |
| Parsing bug found mid-run | Fix the parser (not frozen as a measure); re-parse from stored raw responses, no new calls |

## 10. Assumptions to revalidate (after P7)

- Call counts above (replace with the P7 dry-run numbers).
- E7 needs no reps beyond E2.
- Whether the `T_pre` replication is kept (D7.4).
