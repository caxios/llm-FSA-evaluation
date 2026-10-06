# SSRN submission metadata

| Field | Value |
|---|---|
| Title | Do LLM Valuation Agents Read the Filing? Metamorphic Tests of Filing Fidelity on Korean Listed Firms |
| Author | Dong Gyu Park, Independent Researcher (parkdong1015@gmail.com) |
| File | `Park_2026_LLM_Valuation_Filing_Fidelity.pdf` |
| Date written | October 6, 2026 |
| Number of pages | 11 |
| Keywords | large language models, equity valuation, metamorphic testing, look-ahead bias, memorization, financial filings, convertible bonds, Korea |
| JEL codes | G12 (Asset Pricing; Trading Volume; Bond Interest Rates), G14 (Information and Market Efficiency; Event Studies), C45 (Neural Networks and Related Topics), M41 (Accounting) |
| Suggested eJournals / networks | Financial Economics Network (FEN): Capital Markets: Asset Pricing & Valuation; Accounting Research Network (ARN); Information Systems & eBusiness / Artificial Intelligence eJournal |
| Related link | https://github.com/caxios/llm-FSA-evaluation (if made public); arXiv link once posted |

## Abstract

Large language models (LLMs) are increasingly used to value companies from their filings, but outcome accuracy cannot tell whether a model computes from the filing or recalls what it already knows about the firm. We propose a metamorphic-testing design in which accounting-consistent perturbations of real filings have an exact theoretical effect on per-share value, so the model's response can be measured against a calibrated target. Using 150 Korean listed firms (50 large caps, 50 mid caps and 50 small caps with in-the-money convertible bonds), FY2025 DART filings and a preregistered protocol, we run about 63,000 model calls, mostly with Gemini 2.5 Flash-Lite. The primary agent delegates the arithmetic to a Python tool. None of the four preregistered primary hypotheses is supported after Holm correction. Large-cap scale elasticity is 0.993 (95% CI 0.951-1.035), so values scale with the statements; the firm-memory effect, its dose-response with memory strength, and convertible-bond dilution under-reaction are inconclusive. Exploratory analyses show that the model carries perturbed items into the valuation bridge almost exactly (median 1.00 of the change in cash or non-operating assets), but its projection assumptions vary so much between runs (enterprise value moves by about ±4 times the perturbation) that single-item effects are invisible in a single valuation. Pooled across firms, responses are close to theory for share-count changes (1.007) and non-operating assets (0.875), and larger than theory for cash distributions (1.61). Names pull values toward the price at the training cutoff (stale-anchor coefficient 0.245, p=0.003), and agents that compute themselves misreport their own arithmetic in about 98% of runs. Delegating computation and fixing or averaging assumptions are preconditions for filing-faithful LLM valuation.
