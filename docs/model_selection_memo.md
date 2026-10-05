# Model Selection Memo (P0 Step 0.6)

| Item | Value |
|---|---|
| Date | 2026-10-05 |
| Status | **Primary: Gemini 2.5 Flash-Lite** (user decision: use an older model). D1 conflict resolved |

## Update 2026-10-05 (2): Gemini 2.5 Flash-Lite as primary

- The user asked for an earlier-released model so that the cutoff precedes `T_post`.
- `gemini-2.5-flash` returns 404 "no longer available to new users". Models callable on the key and older than Gemini 3.7: `gemini-2.5-flash-lite` (GA, released 2025-06-17, **cutoff January 2025**), `gemini-3-flash-preview` (preview, Gemini 3 family), `gemma-4-31b-it` (cutoff not documented in sources found).
- Chosen: **`gemini-2.5-flash-lite`** — oldest GA model available, documented cutoff 14 months before `T_post = 2026-04-01`. `T_post`/`T_pre` (D1) stay as they are.
- Probe (same prompt, temperature 0.3, 5 runs): **JSON 5/5, schema 5/5**, intermediates populated; median latency 4.0 s; ~5,100 input / ~900 output tokens, **no thinking tokens**.
- **Noise warning**: value per share ranged 41,327–259,500 KRW (median 120,237) over 5 runs — much wider than Gemini 3.7 Flash (97,613–124,433). The pilot must check gate G4 (measurability) carefully; more repetitions may be needed.
- Cost: ≈ $0.0009 per valuation call → **≈ $35 for the main design**.
- Availability risk: Gemini 2.5 Flash is already closed to new users; Flash-Lite may follow. Mitigation: record the model id per call (P5), run the main experiments without long gaps, and keep `gemini-3-flash-preview` as the fallback (verify its cutoff first).
- Gemini 3.7 Flash remains a candidate for the comparison model (P9).
| Probe | `scripts/probes/probe_model.py` (`--dry-run` verified; prompt built from the Samsung FY2025 fixture) |

## Update 2026-10-05: Gemini 3.7 Flash as working primary

- User decision: use `gemini-3.7-flash` (Google Gemini API, key `GOOGLE_API_KEY`; API version `3.7-flash-08-2026`). Registered as `primary` in `config/models.yaml`.
- Probe (`probe_model.py`, Samsung FY2025 prompt, temperature 0.3, 5 runs): **JSON 5/5, schema 5/5**, all intermediates populated; value per share median 113,894 KRW (range 97,613–124,433); median latency 10.5 s. Tokens per call: ~5,100 input, ~830 visible output, plus ~1,300–2,700 thinking tokens (billed as output).
- Training cutoff (model card): **March 2026**, uneven across domains (some limited to January 2025).
- Cost: at $0.75 / $3.75 per 1M tokens, ≈ $0.015 per valuation call → **≈ $550 for the main design** (vs ≈ $50 estimated for Llama 4 Scout).

### Conflict with the research design (D1)
- The research plan assumes a primary model whose cutoff precedes `T_post` by ≥ 3 months. With a March 2026 cutoff, `T_post = 2026-04-01` is one month after the cutoff, and FY2025 annual reports (filed by end of March 2026) may be in the training data.
- Unaffected: the metamorphic tests (E2, E3, E8) and the information-condition decomposition (E4), because they measure responses to controlled input changes, not out-of-sample accuracy.
- Affected: E7 (stale anchor) loses most of its power, since prices at the cutoff and at `T_post` are one month apart; the time-based identification argument in §6.3 no longer holds. The uneven cutoff also makes "post-cutoff" hard to define.
- Options: see `docs/decisions_log.md` (D1 conflict).

## Primary model candidates (open weights, officially documented cutoff)

| Candidate | Documented training cutoff | Source | Hosted price (USD / 1M tokens, in/out) | Notes |
|---|---|---|---|---|
| Llama 4 Scout 17B-16E Instruct | August 2024 (pretraining data) | Meta model card (also mirrored by NVIDIA NIM, Google Vertex docs) | DeepInfra ~0.10/0.30; Together ~0.20/0.60; Fireworks ~0.21/0.63 (July 2026 snapshots; verify) | Used as the example in research plan §6.3; MoE, long context |
| Gemma 3 27B IT | August 2024 | Google Gemma 3 model card (ai.google.dev/gemma/docs/core/model_card_3) | to be checked | Dense; strong multilingual (140+ languages) |

Models with 2025–2026 cutoffs (e.g., recent Qwen releases with year-level "2026" cutoffs) are not suitable as the primary model: their cutoffs are too close to or after a `T_post` of April 2026, and year-level cutoffs are too imprecise for the time-based identification.

Recommendation: **Llama 4 Scout** as primary (research-plan continuity, cheap, widely hosted), **Gemma 3 27B** as the fallback if Scout's Korean JSON compliance is poor. Final choice after `probe_model.py` (≥ 95% schema compliance over 5 runs, populated intermediates).

## Evaluation dates (D1)

Both candidates have an August 2024 cutoff, so the dates do not depend on which of the two is chosen:

| Date | Value | Check |
|---|---|---|
| `T_post` | **2026-04-01** (first trading day after FY2025 annual reports) | 19 months after the cutoff (rule: ≥ 3 months); FY2025 statements available (data memo); KRX daily data available for this date |
| `T_pre` (optional replication, D7.4) | **2023-04-03** | Before the cutoff; KRX data available |

Note: firms that had not filed their FY2025 annual report by `T_post` (late filers) are excluded at sample selection (P2).

## Comparison model (D0.2)

Not chosen yet. Requirement: commercial API, preferably a reasoning model, with documented cutoff. Choose when the comparison-model API account is available (needed only from P9).

## Rough cost (main design, primary model)

From the dry-run prompt (≈ 1.5k system + 8k user characters, mostly Korean and numbers), assume ~8k input and ~1.5k output tokens per valuation call. Main design ≈ 37k valuation calls (R§10):
- Input ≈ 296M tokens × $0.10 ≈ $30; output ≈ 55M tokens × $0.30 ≈ $17 → **≈ $50** at DeepInfra Llama 4 Scout prices, before retries and extensions.
- Replace with measured token counts after the probe and the pilot.

## To finish Step 0.6
1. Create an account with a host for the primary model (e.g., DeepInfra) and put the key in `.env` as `PRIMARY_API_KEY`.
2. Run, for each candidate:
   `python scripts/probes/probe_model.py --base-url <endpoint> --model <id> -n 5` (and once with `--json-mode`).
3. Fill `config/models.yaml` with the chosen model.
