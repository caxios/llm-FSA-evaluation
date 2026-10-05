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

## D1 (final) — Evaluation dates
- Date: 2026-10-05
- Phase: P0
- Decision: `T_post = 2026-04-01`, `T_pre = 2023-04-03` (optional replication only).
- Reason: both primary-model candidates (Llama 4 Scout, Gemma 3 27B) have an officially documented August 2024 cutoff, so the dates hold whichever is chosen; FY2025 statements and KRX data are available for these dates (`docs/data_access_memo.md`, `docs/model_selection_memo.md`).
- Condition: if the primary model ends up being a model with a different cutoff, revisit.
- Affects: `config/sample.yaml`, P2, P8

## D0.3–D0.6 — Data sources
- Date: 2026-10-05
- Phase: P0
- Decision:
  - D0.3 prices: KRX Open API close (official, unadjusted, point-in-time); split adjustment for E7 from `LIST_SHRS` and capital-change filings; yfinance `Close` only as fallback (yfinance `Adj Close` is dividend-adjusted and not used).
  - D0.4 listing and market cap: KRX Open API daily trading services (`stk_bydd_trd`, `ksq_bydd_trd`). pykrx is not used (requires a KRX login).
  - D0.5 industry: DART `induty_code` (KSIC); financial exclusion by 2-digit divisions 64–66.
  - D0.6 halt / admin issue: not trading (absent or zero volume) on the evaluation date = halted; admin issue from exchange disclosures in the prior 12 months.
- Reason: probe results (`docs/data_access_memo.md`).
- Open item: the KOSDAQ daily trading service (`ksq_bydd_trd`) is not yet approved for the project's KRX key.

## D0.1 — Primary model
- Date: 2026-10-05
- Phase: P0
- Options considered: Llama 4 Scout / Gemma 3 27B (open weights, Aug 2024 cutoff; need another provider); Gemini 3.7 Flash (cutoff March 2026, conflicts with `T_post`); Gemini 2.5 Flash (closed to new users); Gemini 2.5 Flash-Lite (cutoff January 2025).
- Decision: **Gemini 2.5 Flash-Lite** (`gemini-2.5-flash-lite`) via the Google Gemini API, per the user's instruction to use an earlier-released model.
- Reason: oldest GA model available on the project's key; documented cutoff 14 months before `T_post`, so D1 and the time-based identification (E7) remain valid.
- Trade-offs: closed-weight model (deviation from research plan §6.4, which specifies an open-weight primary model); high run-to-run noise in the probe; deprecation risk.
- Affects: `config/models.yaml`, research plan §6.3–§6.4 wording, P5, P7
- Research-plan deviation: yes (§6.4 "오픈웨이트 주 모델")

## P2 decisions (2026-10-05)

### D7 — Firms failing reported-statement identities
- Decision: **exclude** (no reconciling lines). After widening the checks to real filing formats (held-for-sale assets outside current/non-current; extra cash-flow adjustment lines such as FX translation or hyperinflation), 86 of 1,432 firms still fail and are excluded.
- Reason: with 1,321 valid packages (KOSPI 672, KOSDAQ 649) there is no need to patch statements.

### D2.1, D2.3, D2.4 — Package content
- All reported lines are kept; ~50 key lines carry a unique `canonical`, debt and non-operating asset lines carry a `category`, and every line has a `parent` subtotal taken from the DART `ord` grouping (a subtotal row precedes its components). Display order is rebuilt (DART `ord` is not the filing's display order).
- Share classes stored separately; internal unit KRW million (float), rendered as integers.
- Cash-flow signs are kept as reported; most firms report outflows as positive numbers. The package records `cf_outflow_sign` for P3.

### D2.6 — CB disclosure text
- Decision: the CB text in packages is **generated from structured data** (annual-report outstanding table + refixings + issuance terms), not the original filing text.
- Reason: lets P3 edit amounts and prices reliably; V0–V4 share one template.

### D2.7 — CB data cleaning
- Unit captions near the annual-report CB table are unreliable (neighbouring captions, share counts in thousands). Units are chosen so that outstanding face / conversion price matches the reported convertible shares (±5%); rows that match no combination, and residues below 10 million KRW, are dropped.
- Refixing floors from issuance filings can be stale after capital changes; a floor outside [0.65, 1.0] × the current conversion price is set to unknown (70 of 127 sample series keep a floor).
- Conversions between the fiscal year end and `T_post` are not observed (face amounts stay at year-end values). Limitation.

### D2.8 — Small-cap selection
- In-the-money CB at the `T_post` market price; ranked by dilution potential (ITM convertible shares / common shares), excluding firms above 100% (implausible or distressed). Selected range 25%–81%, median 36.6%.
- **Provisional**: KOSDAQ prices are yfinance closes until the KRX KOSDAQ service is approved. Re-run `build_packages.py --stage small,select,packages,truth,report` after approval.
- `cb_complex` (call options, net settlement) is unknown for now: the structured issuance data has no field for it.

### D2.9 — Availability at T_post
- A firm counts as filed by `T_post` if its original FY2025 annual report was filed by then, even when a corrected report came later (171 of 173 such firms). The corrected figures are used — a small look-ahead, recorded as a limitation.

### Pending from P2
- Administrative-issue exclusion (D0.6) not applied yet.
- `main_business` in `quiz_truth` must be filled by hand before E6 (P8).
- Hand checks required by the P2 exit criteria: 10 CB rows against the DART viewer; read the rendered prompts in `tests/fixtures/rendered/`.

## P3 decisions (2026-10-05)

### D2 — Equity counterpart of the non-operating asset perturbation
- Decision: FVOCI asset +X (existing non-current FVOCI line, else a new "기타포괄손익-공정가치 측정 금융자산" line) against the accumulated OCI reserve (`oci_reserve`, else `other_equity`, else a new "기타포괄손익누계액" line). IS and CF unchanged.
- Limitation: a fair-value gain arising in the year would also appear in the year's OCI; the IS is left unchanged so that the perturbation touches the balance sheet only.

### D3 — Balancing entry for CB V2
- Decision: cash +ΔF with a CF inflow on "전환사채의 발행" (created if absent); BS convertible-bond line +ΔF (the largest `debt:convertible` line, else a new "전환사채" line under non-current liabilities). Net debt and equity are unchanged (tested).

### D3.1, D3.2 — Shares and cash distribution
- D3.1: m = 2; EPS and DPS ÷ m in all years. When a CB block is present it gets the standard anti-dilution adjustment (conversion price and floor ÷ m, convertible shares × m), so the dilution ratio is unchanged.
- D3.2: DPS of the latest year + X / common shares outstanding. The dividend line follows the firm's sign convention; a "배당금의 지급" line is created under financing activities when none exists.

### D3.3 (implementation) — V3 floor when undisclosed
- The package carries only the current conversion price, so an undisclosed floor is set to 70% of the *current* price (equal to 70% of the initial price unless the series was already refixed). New prices are rounded up to the won so they never fall below the floor. Per-series `ratio` and `floor_assumed` are recorded in `PerturbMeta.instruments`. Series at the floor stay unchanged; a firm with every series at its floor is not applicable (4 of 50).

### D3.4 — CB block in scale packages
- `scale` refuses packages with a CB block; E2 callers pass `without_cb(pkg)`.

### D3.6 — CB text editing
- Decision: V2/V3 regenerate the CB text from the edited instruments with the P2 template (D2.6) instead of replacing numbers in place. `text_numbers` checks that every changed amount or price is gone and its new value is present. The general replacement helpers (`replace_amount`, `replace_price`) are implemented and tested for use on original filing text.
- V1 drops the CB block entirely (prompt shows "없음") rather than leaving an empty block.
- V4 placebos come from templates filled with the firm's own data (redeemed-CB placebo: earlier series number, median face and price, dates three years earlier). The package carries no actual redeemed series.

### P2 fix found by the P3 sweep
- 10 firms list equity components (자본잉여금, 기타자본, 기타포괄손익누계액) before the equity total in DART `ord`; the builder filed them under non-current assets, which put them in the wrong place in the rendered statements. The builder now reassigns equity components (by canonical, account ID or label) to equity; the 10 packages were rebuilt. Sample and ground truth unchanged.

---

## Research-plan revision

- 2026-10-05: `llm_valuation_research_plan.md` revised to v0.2, reflecting D1, D2.2, D3.3, D3.5, D5.2, D7.4, D8/D2.5. `implementation_plan.md` revised to v0.2.

## Pending

| ID | Decision | Status |
|---|---|---|
| D2, D3, D4, D6, D7 | Roadmap decisions (see `implementation_plan.md` R§16) | Resolved in their phases |
| D0.2 | Comparison model | Candidate: Gemini 3.7 Flash (probe 5/5). Decide in P9 |
