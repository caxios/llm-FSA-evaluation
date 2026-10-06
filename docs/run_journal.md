# Run Journal (P8)

Dated notes: batches, incidents, spend.

- 2026-10-06 11:05 monitor E6: 450 runs, valid 100.0%, cumulative spend $0.03
- 2026-10-06 12:17 monitor E6: 450 runs, valid 100.0%, cumulative spend $0.03
- 2026-10-06 13:11 monitor E6: 450 runs, valid 100.0%, cumulative spend $0.03
- 2026-10-06 13:52 monitor E2-L: 10000 runs, valid 99.6%, cumulative spend $11.27
- 2026-10-06 15:04 monitor E6: 450 runs, valid 100.0%, cumulative spend $11.27
- 2026-10-06 15:15 monitor E2-L: 10000 runs, valid 99.6%, cumulative spend $11.27
- 2026-10-06 15:27 monitor E2-M: 10000 runs, valid 99.8%, cumulative spend $21.11
- 2026-10-06 16:21 monitor E2-S: 10000 runs, valid 99.7%, cumulative spend $30.71
- 2026-10-06 16:32 monitor E5: 2700 runs, valid 100.0%, cumulative spend $31.99
- 2026-10-06 16:47 monitor E3: 2190 runs, valid 99.7%, cumulative spend $34.26
- 2026-10-06 18:05 monitor E3: 4260 runs, valid 99.4%, cumulative spend $36.53
- 2026-10-06 18:05 monitor E7: 1780 runs, valid 99.8%, cumulative spend $38.36
- 2026-10-06 18:19 monitor E8: 2970 runs, valid 99.7%, cumulative spend $41.37

## Summary (2026-10-06 18:20) — P8 complete

| Module | Runs | Valid |
|---|---|---|
| E6 quiz | 450 | 100.0% |
| E2 (L, M, S) | 30,000 | 99.7% (5 low-validity cells) |
| E5 identification | 2,700 | 100.0% |
| E3 rule sizes | 2,190 | 99.7% |
| E3 rule sizes + tiers | 4,260 | 99.4% |
| E7 (E2 cells) | 1,780 | 99.8% |
| E8 CB dilution | 2,970 | 99.7% |

- One model version throughout: `gemini-2.5-flash-lite`.
- Spend: the monitor's cumulative figure of $41.37 double-counts E7, whose calls are E2 cache hits. Measured spend is about $39, against a budget of $60.
- Incidents, all resumed from the cache without repeating calls:
  - DNS failure at 12:40, which aborted the batch; the runner was fixed to skip failed calls and re-run them;
  - Claude Code ended the background shell under memory pressure at 13:5x; the runner process survived;
  - broken chunked read during a network outage around 15:00, after which every requests error was made transient;
  - laptop sleep and power-off around 17:00–18:00; 49 calls were re-run by the batch retry loop.
- Sizing (`size_decisions_main.parquet`): the cash rule size was accepted for 8 of 150 firms, and the non-operating size for 28 (D7.8 fallback). Tiers ran for every firm with positive book equity.
- QA: `results/qa/main_run_qa.md` lists 736 extreme values in E2, most of them sign flips around near-zero medians. Following §5.5 they are reviewed, not removed.
- Pilot E2 rows in `results/runs/E2.parquet` were overwritten by identical main-run job ids, because the job id carries no tag. The pilot results remain in the cache and the JSONL logs, and `docs/pilot_report.md` was written beforehand.
- 2026-10-06 19:44 monitor E3: 11500 runs, valid 99.6%, cumulative spend $48.82

- 2026-10-06 19:45: E3 tiers for the remaining firms (builder fix, D7.8 as preregistered): 6,790 calls; E3 total valid 11,450/11,500; monitor cumulative spend $48.82 (double-counted E7; measured main-run spend about $46).
