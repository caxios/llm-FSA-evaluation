# Decisions Log

Every design decision and every deviation from the research plan (`llm_valuation_research_plan.md`) or the preregistration is recorded here. IDs follow `implementation_plan.md` (D1–D8) and the phase plans in `docs/plans/` (Dn.k).

Format per entry: date, phase, options considered, decision, reason, affected documents/code, and whether it deviates from the research plan.

---

## D7.4 — Role of T_pre
- Date: 2026-10-05
- Phase: decided before P0 (formally owned by P7)
- Options considered: (a) drop T_pre entirely; (b) keep it as an optional pre-cutoff replication of E2; (c) build E7 on T_pre filings
- Decision: **(b) optional exploratory replication.** E7 uses T_post filings with the cutoff-date price as a regressor, as specified in §6.7. A T_pre replication of E2 (conditions A and C, ~20 firms) runs in P8 only if the remaining budget allows.
- Reason: §6.7 (the E7 procedure) does not use T_pre filings; §6.3 listing T_pre "for E7" is inconsistent with it.
- Affects: P1 Step 11, P7, P8 module 8, research plan §6.3
- Research-plan deviation: yes (§6.3 wording)

## D3.3 — V3 conversion-price change
- Date: 2026-10-05
- Phase: P3
- Options considered: (a) Pc × 0.5 as in the research plan; (b) a price that respects the bond's refixing floor
- Decision: **(b)** `Pc_new = max(refix_floor, 0.5 × Pc)`. If the floor is not disclosed, assume 70% of the initial conversion price. Firms whose current Pc is already at the floor are excluded from V3 (no feasible change) and listed. The effective ratio `Pc_new / Pc` is recorded per firm.
- Reason: refixing floors are typically 70% of the initial price; ×0.5 would contradict the bond's own terms and invite data-anomaly judgments.
- Trade-off: smaller theoretical changes in V3, so the dose-response test (H3c) has less spread; V2 still provides a large change.
- Affects: P3 `cb.py`, P6 `dilution.py`, P7 (anomaly-rate check), research plan §6.7 E8 table
- Research-plan deviation: yes

## D5.2 — Tool agent (structure T) design
- Date: 2026-10-05
- Phase: P5
- Options considered: (a) multi-turn function calling; (b) one structured call (extraction + assumptions + dilution decision) followed by deterministic Python valuation
- Decision: **(b).** The model extracts values and sets assumptions; Python computes FCFF, discounting, terminal value, the equity bridge, per-share value, and dilution.
- Reason: simpler, model-agnostic, cleanly separates reflection failures from computation failures. Token cost is lower than the §10.3 estimate (3–5×).
- Trade-off: "agent" is less autonomous, so H4 is framed as "delegating computation to a tool" rather than as a general agent comparison.
- Affects: P5 `tool.py`, P9, research plan §6.4 and §10.3
- Research-plan deviation: partial (cost estimate, framing)

## D2.2 — Notes summary source
- Date: 2026-10-05
- Phase: P2
- Options considered: (a) parse note text from filings; (b) derive the borrowings and non-operating asset summaries from balance-sheet lines
- Decision: **(b).**
- Reason: parsing note text across 150 firms is costly and fragile.
- Trade-off: the input is further from real-world usage; listed as a limitation in the paper.
- Affects: P2 `package_builder.py`, research plan §6.5 (input package table) and limitations
- Research-plan deviation: yes (§6.5 "핵심 주석 요약")

## D1 — T_post selection rule
- Date: 2026-10-05
- Phase: P0
- Decision: choose after verifying the primary model's training cutoff in P0. `T_post` must be at least 3 months after the cutoff; prefer the FY2025 annual-report date (April 2026) if the cutoff and data coverage allow. Newer open-weight models with later cutoffs are eligible candidates.
- Affects: config/sample.yaml, P0 Step 0.6, P2, P8
- Research-plan deviation: no (§6.3 gives FY2024 as an example only)

## D8 / D2.5 — Mid-cap selection
- Date: 2026-10-05
- Phase: P2
- Decision: KOSPI market-cap ranks 101–400 after exclusions; split into 5 market-cap quintiles; within each, 5 firms from the top and 5 from the bottom tercile of "newsworthiness", measured as the count of DART filings in the 12 months before `T_post`.
- Reason: cap-matched contrast in newsworthiness, reducing the collinearity between memory strength and market cap.
- Affects: P2 `sample.py`
- Research-plan deviation: no (operationalizes §6.2)

## D5 — Prompt language
- Date: 2026-10-05
- Phase: P5
- Decision: **Korean** for all prompts (valuation, identification, memory quiz).
- Reason: inputs are Korean DART filings; matches realistic use.
- Affects: P0 Step 0.6 (probe in Korean only), P5 prompts
- Research-plan deviation: no

## D3.5 — Minimum size for single-item perturbations
- Date: 2026-10-05
- Phase: P3
- Options considered: (a) §6.8 rule only (smallest size that reaches the target precision); (b) §6.8 rule plus a floor of 5% of equity value
- Decision: **(b).** Size = max(§6.8 precision lower bound, 5% of the agent's baseline equity value), capped by the §6.8 upper bound (10% of equity value, non-negative cash). If the precision lower bound exceeds the upper bound, `n` is increased as in §6.8.
- Reason: without a floor, low-noise firms get very small perturbations and high-noise firms large ones, so perturbation size is confounded with firm characteristics; models may also treat very small changes as rounding.
- Trade-off: some firms get larger perturbations than the precision rule requires; still within the 10% cap. Size dependence is checked separately with the 2/5/10% tiers.
- Affects: P3 `sizing.py`, research plan §6.8
- Research-plan deviation: yes (addition to §6.8)

---

## Research-plan revision

- 2026-10-05: `llm_valuation_research_plan.md` revised to v0.2, reflecting D1, D2.2, D3.3, D3.5, D5.2, D7.4, D8/D2.5. `implementation_plan.md` revised to v0.2.

## Pending

| ID | Decision | Status |
|---|---|---|
| D2, D3, D4, D6, D7 | Roadmap decisions (see `implementation_plan.md` R§16) | Resolved in their phases |
