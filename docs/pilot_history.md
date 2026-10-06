## Pilot history

### Round 1 (2026-10-05): prompt v1 + structure P

Pilot L (1,230 calls): G1 PASS 99.8%; G2 FAIL (median ε 81%; the error is in the discounting step: EV gaps 20–115% while the bridge and division are correct); G4 FAIL 0/10; unit slips (amounts ÷ 1000, sometimes shares ÷ 1000) in 24% of E0 runs for the largest firms; G3 not interpretable.

### Round 2 (2026-10-06): prompt v1.1 + structure T

Fixes for the two round-1 problems:
- **Unit slips** → prompt v1.1 adds explicit unit rules (copy amounts in KRW million as printed; shares as printed; Korean rationale). Verified on the dev set with two scaled-up dev packages (X011, X012: revenue ≈ KRW 220–300 trillion), which reproduce the slips under v1 (33–47% of runs) and show 0–20% under v1.1·P and **0%** under v1.1·T.
- **Discounting errors** → structure T (Python computes FCFF, discounting, bridge, per-share value).

Pilot L re-run with T + v1.1 (1,230 calls): G1 99.9%, **G2 PASS** (ε = 0 by construction), unit slips **0%**, G3 mean β_A − β_C = −0.08 (90% CI [−0.15, −0.02], 8 firms with positive values). **G4 still fails (0/10).**

Why G4 still fails:
1. **D&A is missing from 131 of 150 packages** (DART structured cash-flow data give only the total "조정" line), so the model invents D&A in each run (Samsung Electronics: 0 to 55 trillion KRW against ~48 trillion capex), which swings FCFF. Re-computing the same T runs with D&A = capex and ΔNWC = 0 cuts the run-to-run CV from 190% → 39% (L001), 39% → 5% (L011), 45% → 8% (L041), 76% → 18% (L006).
2. **The §6.8 parameters are very strict for LLM noise.** With s* = 0.1 and the 10% cap, a firm passes only if CV ≤ 3.2% at n = 20 (4.5% at n = 40). Even after (1) most firms have CV 4–40%.
   | s* | cap | max CV, n = 20 | max CV, n = 40 |
   |---|---|---|---|
   | 0.10 | 10% | 3.2% | 4.5% |
   | 0.10 | 20% | 6.3% | 8.9% |
   | 0.20 | 10% | 6.3% | 8.9% |
   | 0.25 | 20% | 15.8% | 22.4% |
3. Two firms (L026, L031) have non-positive baseline values in every run (D7.5).

Decisions needed (design, before the preregistration): (a) a D&A convention in the tool prompt (D&A = capex, ΔNWC from history or 0) or adding D&A to the packages from the annual-report notes; (b) relaxing s* and/or the cap, or accepting E3 on fewer firms; (c) D7.5 for non-positive baselines.
