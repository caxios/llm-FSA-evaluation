# P3 — Perturbation Engine

| Item | Value |
|---|---|
| Roadmap | R§5 |
| Weeks | 4–5 |
| Status | Implemented 2026-10-05 (human read of V2/V3 texts pending) |
| Version | v0.1 (2026-10-05) |
| Depends on | P2 Step 2.1 (schema freeze, fixtures, `check_identities`, ancestry map) |
| Unlocks | P6, P7 |

> **Implementation notes (2026-10-05)** — see `docs/decisions_log.md` (P3 decisions):
> - Code: `src/perturb/{base,scale,shares,cash_distribution,non_operating,cb,text_numbers,sizing}.py`, placebo templates in `src/perturb/templates/`. Sweep: `scripts/sweep_identities.py` → `results/qa/perturbation_sweep.csv` and `results/qa/cb_variant_samples.md` (V0/V2/V3 texts of 5 seeded small caps for the human read).
> - Interface: registered functions edit the copy `perturb()` hands them; `perturb()` raises `PerturbationInconsistent` on any hard identity violation and on any *new* soft violation (ending cash ≠ BS cash). Expected failures are `PerturbationOutOfRange` and `PerturbationNotApplicable`. `PerturbMeta` adds `instruments` (per-series CB details).
> - Ancestry is resolved per package: the line's own `parent`, then `config/ancestry.yaml`, skipping subtotals the firm does not report. CF now routes `cfo/cfi/cff → net_change_before_fx → net_change_in_cash → ending_cash`.
> - Cash-flow lines follow the firm's sign convention (`cf_outflow_sign`): a dividend of X is shown as +X (or −X) while the financing subtotal falls by X. Missing lines (dividends paid, FVOCI asset, OCI reserve, BS convertible bond, CF CB proceeds) are created as `derived` lines with earlier years unreported.
> - CB texts are regenerated from edited instruments (D3.6) rather than edited in place; `text_numbers` verifies the old values are gone and the new ones present. V1 drops the CB block (`cb = None`), so the prompt reads "없음".
> - Sweep on the 150 packages: 2,100 perturbations, 0 identity violations, 0 unexpected errors. Out of range: 66 cash distributions above the cash balance (46 firms, mostly the 10% tier). Not applicable: 4 small caps for V3 (every series at its floor). V3 effective ratios 0.70–0.94.
> - The sweep exposed a P2 builder bug: 10 firms list equity components before the equity total in DART `ord`, so those lines were filed under non-current assets (also visible in their rendered prompts). Fixed in `package_builder.py`; the 10 packages were rebuilt (`build_packages.py --stage packages,truth,report`). Test coverage of `src/perturb/`: 94%.

## 1. Objective

Implement every input transformation used by E2, E3, E5, and E8 as pure, tested functions that (a) keep the statements accounting-consistent and (b) return the metadata needed to compute the theoretical value change in P6. Also implement the perturbation-size rule of §6.8.

## 2. Entry conditions

- `InputPackage` schema frozen; 5 fixture packages; `check_identities()` and `config/ancestry.yaml` available.

## 3. Decisions resolved in this phase

| ID | Decision | Recommendation |
|---|---|---|
| D2 | Equity counterpart for the non-operating asset perturbation | `other_equity` (OCI reserve). Economically this is a fair-value gain on an FVOCI asset: no P&L and no cash effect, so the IS and CF stay unchanged |
| D3 | Balancing entry for CB V2 (double the CB balance) | Cash +ΔF in the latest year, with a matching CF financing inflow. Net debt and $E$ stay unchanged, so the theoretical change isolates dilution |
| D3.1 | Share multiplier `m` for E3 | `m = 2` (as if a 2-for-1 split). Paid-in capital unchanged; EPS and DPS halved in all years |
| D3.2 | DPS update in the cash-distribution perturbation | Latest-year `dps_common += X / common_outstanding`, since a special dividend would show up in DPS. Without this the package is internally inconsistent |
| D3.3 | V3 conversion-price change | **Resolved 2026-10-05.** `Pc_new = max(refix_floor, 0.5 × Pc)`; if the floor is not disclosed, assume 70% of the initial conversion price. Firms already at the floor are excluded from V3 and listed. Record the effective ratio per firm. The pilot only checks the anomaly-flag rate |
| D3.5 | Minimum size for single-item perturbations | **Resolved 2026-10-05.** At least 5% of the agent's baseline equity value, capped at 10% (see `sizing.py`) |
| D3.4 | CB information in scale-perturbation packages | E2 packages exclude the CB block (CB text appears only in E8). Scaling face values while keeping the conversion price would change the dilution ratio, so the transformation would no longer be a pure scale change |

## 4. Deliverables

```
src/perturb/__init__.py          # registry: name -> function
src/perturb/base.py              # PerturbMeta, helpers (apply_delta with ancestry)
src/perturb/scale.py
src/perturb/cash_distribution.py
src/perturb/shares.py
src/perturb/non_operating.py
src/perturb/cb.py
src/perturb/text_numbers.py      # Korean amount detection/replacement
src/perturb/sizing.py
scripts/sweep_identities.py
tests/test_perturb_base.py
tests/test_perturb_scale.py
tests/test_perturb_cash.py
tests/test_perturb_shares.py
tests/test_perturb_non_operating.py
tests/test_perturb_cb.py
tests/test_text_numbers.py
tests/test_sizing.py
```

## 5. Design

### 5.1 Common interface (`src/perturb/base.py`)

```python
class PerturbMeta(BaseModel):
    type: Literal["none", "scale", "cash", "shares", "non_operating",
                  "cb_v0", "cb_v1", "cb_v2", "cb_v3", "cb_v4"]
    params: dict[str, float | str]     # e.g. {"k": 1.25}, {"x_mn": 1200.0, "fraction": 0.05}
    year: int | None                   # year modified, if single-year
    notes: str = ""

PerturbFn = Callable[[InputPackage, ...], tuple[InputPackage, PerturbMeta]]

def apply_delta(pkg: InputPackage, statement: str, canonical: str, year: int, delta: float) -> None
    # adds delta to the leaf and to every ancestor in the resolved ancestry chain (in-place on a copy)

def perturb(pkg: InputPackage, name: str, **params) -> tuple[InputPackage, PerturbMeta]
    # deep-copies, dispatches through the registry, runs check_identities(), raises
    # PerturbationInconsistent if any violation, and returns (new_pkg, meta)
```

All functions are pure: the input package is never modified. `perturb()` is the only public entry point; it guarantees the identity check runs.

### 5.2 Perturbation specifications

**Scale** (`scale.py`) — `scale(pkg, k)`
- Every line with `kind == "monetary"` in BS, IS, CF, all years: `value *= k`.
- `per_share.eps`, `per_share.dps_common`, and IS `eps_basic` line: `*= k`.
- Notes summary amounts: `*= k`.
- Share counts, ratios: unchanged. `cb` must be `None` (D3.4); raise otherwise.
- Meta: `{"k": k}`. Theory (P6): $V^* = V_0 k$.

**Cash distribution** (`cash_distribution.py`) — `cash_distribution(pkg, x_mn)`
Latest year `Y` only:

| Line | Change |
|---|---|
| BS `cash` (+ ancestors `current_assets`, `total_assets`) | −X |
| BS `retained_earnings` (+ `equity_owners`, `total_equity`, `total_liabilities_and_equity`) | −X |
| CF `dividends_paid` (+ `cff`, `net_change_in_cash`, `ending_cash`) | −X (more negative) |
| `per_share.dps_common[Y]` | + X / common_outstanding (converted to KRW) |
| IS | unchanged (forgone interest ignored; documented limitation) |

Guards (raise `PerturbationOutOfRange`): `x_mn <= cash[Y]`; `x_mn >= 0`.
Meta: `{"x_mn": X}`. Theory: $\Delta V^* = -X / N_{\text{agent}}$.

**Shares** (`shares.py`) — `shares(pkg, m)`
- `common_issued`, `common_treasury`, `preferred_*` × m.
- EPS (both places) and DPS ÷ m, all years.
- Meta: `{"m": m}`. Theory: $V^* = V_0 / m$.

**Non-operating assets** (`non_operating.py`) — `non_operating(pkg, x_mn)`
- Latest year: `fvoci_financial_assets` +X (create the line under non-current assets if absent, labelled "기타포괄손익-공정가치 측정 금융자산"), ancestors updated.
- `other_equity` +X with ancestors.
- Notes summary non-operating list updated to match.
- Meta: `{"x_mn": X}`. Theory: $\Delta V^* = +X / N_{\text{agent}}$.

**CB variants** (`cb.py`) — all require `pkg.cb is not None` and group `S`.

| Fn | Edit | Meta |
|---|---|---|
| `cb_v0(pkg)` | No change (CB block included) | `{F, Pc}` from instruments |
| `cb_v1(pkg)` | `cb.filing_text = ""`, `cb.outstanding_table_text = ""`, `instruments = []`. BS `convertible_bonds` line stays (the BS label still reveals a CB exists, but its terms do not) | `{}` |
| `cb_v2(pkg)` | For each instrument: `face_outstanding *= 2`; text amounts replaced via `text_numbers`; convertible shares in the table ×2; BS `convertible_bonds` +ΔF; BS `cash` +ΔF; CF `proceeds_from_bonds` (create if absent) +ΔF with `cff`, `net_change_in_cash`, `ending_cash` | `{F_new, Pc}` |
| `cb_v3(pkg)` | `conversion_price → Pc_new` per D3.3; text replaced; convertible shares in the table recomputed `F / Pc_new` | `{F, Pc_new, ratio}` |
| `cb_v4(pkg, placebo)` | Append a placebo filing to `filing_text`: `"redeemed_cb"` (a fully redeemed earlier CB of the same firm, if one exists, else a template) or `"irrelevant"` (head-office relocation template) | `{placebo}` |

Placebo templates live in `src/perturb/templates/` as Korean text with placeholders, written to look like real DART filings.

### 5.3 Korean amount handling (`text_numbers.py`)

```python
def renderings(value_krw: float) -> list[str]
    # "20,000,000,000", "20000000000", "20,000,000"(천원 context), "20,000"(백만원 context),
    # "200억", "200억원", "200억 원", "2,000억", "1,234억 5,678만" ...
def find_amounts(text: str, value_krw: float) -> list[Span]
def replace_amount(text: str, old_krw: float, new_krw: float) -> tuple[str, int]
    # replaces every detected mention in its original format; returns (new_text, n_replaced)
def find_prices(text: str, price_krw: float) -> list[Span]     # "8,000원", "8,000 원"
```
- Unit context: if a table caption says `(단위: 백만원)`, numbers in that table are interpreted in millions.
- `replace_amount` must report `n_replaced`; CB functions assert `n_replaced >= 1` per expected location, and log any mention left unchanged.

### 5.4 Size rule (`sizing.py`)

```python
class SizeDecision(BaseModel):
    firm_id: str
    perturbation: str
    fraction: float | None        # X as fraction of baseline equity value
    x_mn: float | None
    n: int
    status: Literal["ok", "increased_n", "excluded"]
    reason: str = ""

def lower_bound_per_share(sigma: float, n: int, target_se: float) -> float
    # sigma * sqrt(2/n) / target_se
def decide_size(firm_id, perturbation, v0: float, sigma: float, shares_agent: float,
                equity_value: float, cash_latest: float, cfg: ExperimentsConfig) -> SizeDecision
def tier_sizes(equity_value: float, tiers=(0.02, 0.05, 0.10)) -> list[float]
```
Algorithm for single-item perturbations (cash, non-operating):
1. For `n` in `[n_default, ..., n_max]` (step 5):
   - `lb = lower_bound_per_share(sigma, n, s*) * shares_agent` (KRW million).
   - `ub = min(0.10 * equity_value, cash_latest)` for cash; `0.10 * equity_value` for non-operating.
   - If `lb <= ub`: return `x = max(lb, 0.05 * equity_value)` capped at `ub`, `status = "ok"` or `"increased_n"`.
2. Otherwise `status = "excluded"` with the reason.

The 5% floor is decision D3.5 (resolved 2026-10-05; research plan §6.8 v0.2). It keeps perturbations comparable across firms when noise is low. Shares (`m = 2`) and scale perturbations are large by construction; `decide_size` only checks that the theoretical change exceeds `lb`.

Inputs `v0`, `sigma`, `shares_agent`, `equity_value` come from E0 runs (pilot or main), so sizing runs after E0.

## 6. Step-by-step tasks

1. **Base**: `PerturbMeta`, `apply_delta`, registry, `perturb()` wrapper with identity check. Tests: ancestry propagation; inconsistent result raises. Commit.
2. **Scale**. Tests: identities on all fixtures for each k; composition `scale(scale(p, a), b) == scale(p, a·b)` (within float tolerance); `k=1` is identity; CB package raises. Commit.
3. **Shares**. Tests: `m=1` identity; EPS × shares invariant; composition. Commit.
4. **Cash distribution**. Tests: X=0 identity; identities hold; DPS change equals X/N; guard raises for X > cash. Commit.
5. **Non-operating**. Tests: identities; line created when absent; notes summary updated; IS/CF untouched (hash of IS and CF unchanged). Commit.
6. **text_numbers**. Tests: a table of 20+ real snippets from CB filings (from P1 fixtures) with expected spans and replacements; round trip `replace(replace(t, a, b), b, a) == t`. Commit.
7. **CB variants** V0–V4 and placebo templates. Tests: V1 leaves no CB terms in rendered text (search for the conversion price and face amount strings); V2 identities hold and $E$ (equity − net debt, computed from BS) unchanged; V3 respects the floor; V4 adds text only. Commit.
8. **Sizing**. Tests: hand-computed cases for `ok`, `increased_n`, `excluded`; tier sizes. Commit.
9. **Sweep script** `scripts/sweep_identities.py`: for every package in `data/processed/packages/`, apply every applicable perturbation (k grid incl. 1.5 for E5; cash and non-operating at 2/5/10% of book equity as a proxy; shares m=2; CB V0–V4 for S), run identities, and write `results/qa/perturbation_sweep.csv`. Run once real packages exist.

## 7. Tests

Property-based tests with `hypothesis` for scale and shares (random k/m in a range, random fixture). All other tests are example-based. Coverage target for `src/perturb/`: ≥ 90% lines.

## 8. Exit criteria & verification

- [x] All unit tests pass on the 5 fixtures.
- [x] `sweep_identities.py` on all 150 packages: 0 violations, 0 unexpected exceptions; `PerturbationOutOfRange` cases listed with reasons.
- [ ] For 5 randomly chosen small caps, the rendered V2 and V3 texts are read by a human: every amount and price was updated, and the text still reads naturally (`results/qa/cb_variant_samples.md`).
- [x] D2, D3, D3.1–D3.4 recorded in the decisions log.

## 9. Risks & fallbacks

| Risk | Fallback |
|---|---|
| CB text amounts appear in formats the helper misses | Expand `renderings`; failing that, regenerate the CB text from structured fields with a template instead of editing the original text (apply to V0 too, so V0–V3 stay comparable) |
| Ancestry differs across firms in ways the map does not cover | Per-package ancestry resolution in the builder; sweep failures point to the cases |
| Perturbed statements look suspicious to reasoning models (anomaly flags) | Keep perturbations within the §6.8 range; the anomaly rate per perturbation type is monitored in the pilot |
