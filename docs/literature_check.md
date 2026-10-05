# Literature Check (P0 Step 0.7)

Research plan §16 checklist. Overlap: **none** / **partial** / **major**. A "major" overlap triggers a design review before P1.

Status as of 2026-10-05: **first pass by web search (abstracts and summaries only).** No major overlap found. Every "partial" item still needs a full read before the paper's related-work section is written, and the positioning in §3 of the research plan should be updated to cite them.

| # | Item | Status | Overlap | Notes / differentiation |
|---|---|---|---|---|
| 1 | Glasserman & Lin (2023), arXiv:2309.17322 | Searched | partial | Anonymization of headlines; finds a "distraction effect" larger than look-ahead bias, stronger for large firms. Supports our use of anonymization as a secondary tool and our large-vs-small contrast. Our identification relies on metamorphic deltas, not anonymization |
| 2 | Lopez-Lira, Tang & Zhu, "The Memorization Problem", arXiv:2504.14765 | Searched | partial | Shows forecasts within the training window cannot separate skill from recall. This is the motivation for our design; we do not forecast outcomes, we measure responses to controlled input changes |
| 2b | Gao, Jiang & Yan, "A Test of Lookahead Bias in LLM Forecasts", arXiv:2512.23847 | Searched | partial | Statistical test using a "lookahead propensity" score. Complementary: they detect memorization in forecasts; we measure filing fidelity in valuation with calibrated targets |
| 3 | Lee et al. (2025), "Your AI, Not Your View", arXiv:2507.20957 (ICAIF '25) | Searched | partial | Already positioned in research plan §3.2. Public leaderboard: linqalpha.com/leaderboard. No follow-up on valuation-level calibrated measurement found in this pass |
| 4 | Search "metamorphic testing LLM finance / valuation" | Searched | none | Metamorphic testing of LLMs exists for robustness, fairness, and agents (e.g., arXiv:2312.06056 METAL, 2504.07982, 2601.06112 ReliabilityBench), but none for financial valuation |
| 5 | Search "LLM valuation anchoring / memorized prices" | Searched | partial | See entries 5a–5c below: closest related work |
| 6 | Search "knowledge conflict numerical reasoning" | TODO | | |

## Closest related work (read in full before writing)

### 5a. "Profit Mirage: Revisiting Information Leakage in LLM-based Financial Agents", arXiv:2510.07920
- What it does: builds counterfactual market environments (perturbed earnings reports, replaced price series, altered indicators) to test whether trading agents adapt to inputs or rely on memorized patterns.
- Overlap: **partial — closest in spirit** (counterfactual input perturbation to expose memorization).
- Differentiation: trading decisions and returns vs. our valuation outputs; their perturbations have no exact theoretical response size, while ours (scale, cash, shares, non-operating assets, CB dilution) have a calibrated target change, giving continuous fidelity measures (β, R); we decompose attenuation into industry prior / name presence / firm-specific memory and study the memory-absent case (KOSDAQ CBs).

### 5b. "From Knowing to Doing: A Memory-Controlled Benchmark for LLM Trading Agents on Stock Markets", arXiv:2605.28359
- What it does: memory-controlled benchmark for trading agents, addressing overlap between backtests and knowledge cutoffs.
- Overlap: **partial** (controls for memory in finance agents).
- Differentiation: benchmark of trading performance vs. our measurement of valuation fidelity to filings.

### 5c. Garcia, "Algorithmic Anchoring: How Prompt-Embedded Reference Points Bias LLM Financial Estimates", SSRN 6366838
- What it does: controlled equity-valuation experiment with fictional companies; anchors embedded in the prompt shift valuations.
- Overlap: **partial** (valuation anchoring).
- Differentiation: prompt-provided anchors on fictional firms vs. our internal (memorized) anchors on real firms; this supports our decision never to show prices in the prompt (§6.5), because provided anchors are a different phenomenon.

## Action items
- [ ] Full read of 5a, 5b, 5c, 1, 2, 2b.
- [ ] Complete search 6 ("knowledge conflict numerical reasoning").
- [ ] Update research plan §3 (related work table, §3.5) to cite 5a–5c and 2/2b.
