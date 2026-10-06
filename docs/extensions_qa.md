# Extensions QA (P9)

- Generated: 2026-10-06 18:40
- Every extension ran; validity >= 99.7% everywhere (exit criterion >= 90%).

| experiment | structure | model | prompt | runs | valid | anomaly-flag rate |
|---|---|---|---|---|---|---|
| E10 | T | primary | v1.2 | 800 | 99.8% | 83.2% |
| E2 | P | primary | v1.2 | 1500 | 99.7% | 55.3% |
| E2 | P | primary | v1.2_instr | 1500 | 99.8% | 53.9% |
| E2 | R | primary | v1.2 | 1500 | 99.9% | 57.5% |
| E2 | T | comparison | v1.2 | 3000 | 100.0% | 6.6% |
| E8 | P | primary | v1.2 | 1190 | 99.9% | 83.4% |
| E8 | R | primary | v1.2 | 1190 | 99.8% | 84.5% |

Structure T on the same firms comes from the main run (tag main). The comparison model flags anomalies far less often (6.6%) than the primary model (54-85%).
