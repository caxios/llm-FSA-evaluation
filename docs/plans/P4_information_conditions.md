# P4 — Information Conditions (Redaction & Fake Names)

| Item | Value |
|---|---|
| Roadmap | R§6 |
| Week | 5 |
| Status | Implemented 2026-10-05 (manual audit and fake-name review by a person pending) |
| Version | v0.1 (2026-10-05) |
| Depends on | P2 Step 2.1 (schema), P1 (`corpCode` list, company info, investee names) |
| Unlocks | P7 |

> **Implementation notes (2026-10-05)** — see `docs/decisions_log.md` (P4 decisions):
> - Code: `src/conditions/{identifiers,redactor,build,fake_names,industry,pipeline}.py`; config `fake_name_parts.yaml`, `redaction_overrides.yaml` (reviewer-confirmed identifiers and ignored tokens), `industry_labels.yaml` (+ KSIC sections, `min_peers`), `models.yaml` (`comparison` entry). Scripts: `build_conditions.py` (identifiers, fake names, automated leak check → `docs/redaction_report.md`), `redaction_llm_check.py` (→ `docs/redaction_llm_review.md`), `redaction_audit_sample.py` (→ `docs/redaction_audit.md`).
> - Entry point for P5: `src.conditions.pipeline.conditioned(firm_id, condition)` returns a `ConditionedPackage` whose `render()` is the prompt.
> - `FirmIdentifiers` adds `segments`. Matching: one regex pass, longest term first; terms of ≤ 2 characters and Latin-letter terms match only as whole tokens; Korean terms of ≥ 3 characters also match with spaces between characters. Placeholder values ("-") are ignored.
> - Results on the 150 firms: no statement or notes label contains an identifier (0 redactions); automated leak check 0; LLM residual check round 1 (gemini-3.7-flash, 300 prompts, $1.26) found no identifier (only "국내" from the industry label, ignored) — converged. 13 firms in divisions with fewer than 10 universe peers use the KSIC section label. Fake names: 150, unique, max similarity 0.57.

## 1. Objective

Produce the four information conditions of E4 from one package:

| Condition | Company name | Industry label | Purpose |
|---|---|---|---|
| A | hidden | hidden | Numbers only |
| B | hidden | generic label | + industry prior |
| D | fake name | generic label | + presence of a name |
| C | real name | generic label | + firm-specific memory |

Redaction must remove every *direct* identifier from conditions A, B, and D. Indirect identification through the numbers themselves cannot be removed; E5 measures it instead.

## 2. Entry conditions

- Package schema frozen; renderer from P2 Step 2.4 (or a stub that renders the fixture packages).
- `corpCode.xml` and per-firm `company` and `investments` raw data from P1.

## 3. Decisions resolved in this phase

| ID | Decision | Recommendation |
|---|---|---|
| D4.1 | Company-block format in condition A | Keep the block with explicit "(비공개)" values rather than dropping it. Identical structure across conditions avoids a format confound |
| D4.2 | Industry label granularity | KSIC division level (2-digit) mapped to a short generic Korean label. Finer labels (e.g., "memory semiconductors") nearly identify the firm |
| D4.3 | Similarity threshold for fake names | Reject if normalized Levenshtein similarity ≥ 0.6 to any listed name (after removing legal suffixes), or an exact match to any name in `corpCode.xml` |
| D4.4 | Model used for the LLM residual check | The comparison (commercial) model, so the primary model never sees redacted packages outside the experiment |

## 4. Deliverables

```
src/conditions/__init__.py
src/conditions/identifiers.py    # per-firm identifier dictionary
src/conditions/redactor.py
src/conditions/fake_names.py
src/conditions/industry.py       # KSIC -> label
src/conditions/build.py          # make_condition(pkg, cond) -> ConditionedPackage
config/industry_labels.yaml
config/fake_name_parts.yaml
scripts/redaction_llm_check.py
scripts/redaction_audit_sample.py
tests/test_identifiers.py
tests/test_redactor.py
tests/test_fake_names.py
tests/test_conditions_build.py
data/processed/fake_names.parquet
data/processed/identifiers/{firm_id}.json
docs/redaction_audit.md
```

## 5. Design

### 5.1 Scope of redaction

What appears in the E2/E3 prompt (§6.5): company block, three statements (line labels), share info, notes summary. Business descriptions are never included. CB filing text appears only in E8, which runs in condition C, so CB text is out of redaction scope for the main design. The redactor is still written generically (it works on any text field) for E10 and robustness runs.

Where identifiers can leak in the E2 prompt:
- Company block (handled by construction).
- Custom line labels (e.g., an investment line naming a subsidiary or affiliate, such as "○○전자 지분법투자").
- Notes summary labels derived from those lines.

### 5.2 Identifier dictionary (`identifiers.py`)

```python
class FirmIdentifiers(BaseModel):
    firm_id: str
    names: list[str]          # corp_name, stock_name, English name, without legal suffixes,
                              # common abbreviations (e.g., "삼성전자" -> "삼성")
    ticker: str
    ceo: list[str]
    address_tokens: list[str] # city/district from adres
    homepage: str | None
    investees: list[str]      # from otrCprInvstmntSttus (subsidiaries, affiliates)
    brands: list[str]         # starts empty; filled by the LLM check + manual review
    group_names: list[str]    # chaebol group prefix if any (e.g., "SK", "LG", "현대")

def build_identifiers(firm_id, company: dict, investments: pd.DataFrame) -> FirmIdentifiers
```
Group-name prefixes are dangerous because short tokens (e.g., "LG") also occur inside unrelated words. Match them only as whole tokens.

### 5.3 Condition construction (`build.py`)

```python
class ConditionedPackage(BaseModel):
    condition: Literal["A", "B", "D", "C"]
    package: InputPackage           # labels redacted where needed
    company_block: str              # rendered block
    redaction_log: list[Redaction]  # what was replaced, where

def make_condition(pkg, condition, identifiers, fake_name: str | None) -> ConditionedPackage
```

Company block (Korean, fixed structure):
```
기업명: {name}
업종: {industry}
```
| Condition | `{name}` | `{industry}` |
|---|---|---|
| A | (비공개) | (비공개) |
| B | (비공개) | label |
| D | fake name | label |
| C | real name | label |

For A, B, D: run the redactor on all line labels and notes labels. For C: no redaction (labels as reported).

### 5.4 Redactor (`redactor.py`)

```python
class Redaction(BaseModel):
    field: str; original: str; replacement: str; rule: str

def redact_text(text: str, ids: FirmIdentifiers) -> tuple[str, list[Redaction]]
```
Rules, applied in order:
1. Investee and affiliate names → "관계회사" (or "종속회사" when the line is a subsidiary investment).
2. Firm names and abbreviations → "당사".
3. Brands → "주요 제품".
4. Ticker, homepage, CEO, address tokens → removed.
5. Segment names (if any appear in labels) → "부문1", "부문2", … in first-seen order.

Matching: Unicode-normalized (NFC), longest match first, whole-token for names ≤ 2 characters.

### 5.5 LLM residual check (`scripts/redaction_llm_check.py`)

For each firm, render conditions A and B and ask the comparison model (Korean):
"아래 재무 자료에서 특정 회사, 그룹, 브랜드, 인물, 지역을 식별할 수 있는 단어나 표현을 모두 나열하세요. 없으면 '없음'이라고 답하세요."
- The output is a JSON list of tokens. Tokens are reviewed by a person, and confirmed ones go into `brands`/`names` in the identifier dictionary. Then redaction is re-run.
- This check asks only about **explicit tokens**. Whether the *numbers* reveal the firm is measured separately in E5.

### 5.6 Fake names (`fake_names.py`)

```python
def generate_candidates(industry_label: str, rng, n: int = 50) -> list[str]
    # templates: {prefix}{core}{suffix}, e.g. prefix from ["한빛", "대성", "세진", "우림", ...],
    # suffix by industry: 제조 -> ["정밀", "산업", "테크", "소재"], IT -> ["시스템", "소프트", "네트웍스"]
def is_acceptable(name: str, listed_names: list[str], all_corp_names: set[str], threshold=0.6) -> bool
def assign_fake_names(sample: pd.DataFrame, seed: int) -> pd.DataFrame
    # firm_id, fake_name, industry_label, max_similarity, nearest_real_name
```
- Each firm gets exactly one fake name, fixed for all experiments. Names are unique across the sample.
- `config/fake_name_parts.yaml` contains name-part lists. Avoid parts that are well-known group prefixes (삼성, 현대, LG, SK, 롯데, 한화, GS, CJ, 포스코, 두산, …).

### 5.7 Industry labels (`industry.py`, `config/industry_labels.yaml`)

```yaml
"26": "국내 전자부품·컴퓨터·통신장비 제조 기업"
"20": "국내 화학제품 제조 기업"
"30": "국내 자동차 및 부품 제조 기업"
...
```
Every KSIC division present in the sample gets a reviewed label. Labels describe the industry, never the firm's position ("국내 1위", "대표") or product.

## 6. Step-by-step tasks

1. `industry.py` + label YAML for all divisions present in the sample; tests (every sample KSIC maps; no label contains a firm name). Commit.
2. `identifiers.py`; build dictionaries for fixtures; tests. Commit.
3. `redactor.py`; tests with crafted labels (investee line, abbreviation, short group prefix inside an unrelated word must NOT match). Commit.
4. `build.py` + company-block rendering; tests: structure identical across conditions (same line count and keys); C equals the unredacted render apart from the company block. Commit.
5. `fake_names.py`; tests: no exact match to `corpCode` names; similarity under threshold; determinism with seed; uniqueness. Commit.
6. Run on all 150 firms: build identifier dictionaries, assign fake names, write outputs.
7. Run `redaction_llm_check.py` on all firms (conditions A, B); review flagged tokens; update dictionaries; re-run until no new confirmed tokens appear.
8. Manual audit: `redaction_audit_sample.py` draws a stratified 10% sample (5 L, 5 M, 5 S; seeded) and writes rendered A/B/D prompts into `docs/redaction_audit.md` with a checklist per firm (name, ticker, brand, investee, CEO, address, segment names). Two passes by a person; record findings.
9. Close-out: record D4.x; tick P4.

## 7. Tests

| Test file | Key cases |
|---|---|
| `test_identifiers.py` | Suffix stripping (㈜, 주식회사, 홀딩스), abbreviations, investee extraction |
| `test_redactor.py` | Each rule; longest-match precedence; short-token false positives; redaction log content |
| `test_fake_names.py` | Collision checks; threshold; uniqueness; reproducibility |
| `test_conditions_build.py` | No real-name token in A/B/D renders for every fixture (search all name variants); company-block structure invariance; C unchanged |

## 8. Exit criteria & verification

- [x] Automated check across all 150 firms: no `names`/`ticker`/`investees` token appears in A/B/D renders.
- [x] LLM residual check converged (last round found no new confirmed tokens).
- [ ] Manual audit of 15 firms: zero direct identifiers remaining (`docs/redaction_audit.md`).
- [x] `fake_names.parquet` covers all 150 firms; max similarity < threshold (list for human review in `docs/redaction_report.md`).

## 9. Risks & fallbacks

| Risk | Fallback |
|---|---|
| Large caps identifiable from numbers alone | Expected; measured by E5 and handled in analysis (control + exclusion robustness) |
| Fake names sound implausible or comical | Have a person review the full list; regenerate rejects |
| Investee list incomplete | The LLM check catches the remaining names in labels; add them manually |
