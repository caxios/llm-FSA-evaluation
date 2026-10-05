"""Input package schema (P2 Step 2.1): one standardized, accounting-consistent firm record.

All monetary values are KRW million (float, unrounded). Per-share values are KRW.
Statements keep every reported line (D2.1); key lines carry a unique `canonical` ID and
multi-line groups (debt, non-operating assets) carry a `category`. `parent` names the
subtotal a line rolls into; config/ancestry.yaml maps subtotals to their own parents, so
P3 can propagate a change to every affected subtotal.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.utils.hashing import stable_hash

SCHEMA_VERSION = "1.0"
Kind = Literal["monetary", "count", "ratio", "per_share"]
StatementCode = Literal["BS", "IS", "CF"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class LineItem(Model):
    line_id: str                          # unique within the package, e.g. "bs_012"
    label: str                            # Korean label as reported (redacted in P4)
    account_id: str                       # DART account_id ("-표준계정코드 미사용-" if none)
    canonical: str | None = None          # unique key line, e.g. "cash"
    category: str | None = None           # e.g. "debt:convertible", "nonop:fvoci"
    parent: str | None = None             # canonical of the subtotal this line rolls into
    kind: Kind = "monetary"
    values: dict[int, float | None]       # fiscal year -> value
    order: int                            # display order (assigned by the builder)
    indent: int = 0
    derived: bool = False                 # line created by the builder or a perturbation


class Statement(Model):
    code: StatementCode
    title: str                            # e.g. "재무상태표", "포괄손익계산서"
    lines: list[LineItem]

    def find(self, canonical: str) -> LineItem | None:
        for line in self.lines:
            if line.canonical == canonical:
                return line
        return None

    def get(self, canonical: str) -> LineItem:
        line = self.find(canonical)
        if line is None:
            raise KeyError(f"{self.code}: no line with canonical '{canonical}'")
        return line

    def value(self, canonical: str, year: int) -> float:
        v = self.get(canonical).values.get(year)
        if v is None:
            raise KeyError(f"{self.code}.{canonical}: no value for {year}")
        return v

    def by_category(self, prefix: str) -> list[LineItem]:
        return [ln for ln in self.lines if ln.category and ln.category.startswith(prefix)]

    def line(self, line_id: str) -> LineItem:
        for ln in self.lines:
            if ln.line_id == line_id:
                return ln
        raise KeyError(line_id)


class ShareInfo(Model):
    common_issued: float
    common_treasury: float = 0.0
    preferred_issued: float = 0.0
    preferred_treasury: float = 0.0
    as_of: date | None = None

    @property
    def common_outstanding(self) -> float:
        return self.common_issued - self.common_treasury

    @property
    def preferred_outstanding(self) -> float:
        return self.preferred_issued - self.preferred_treasury


class PerShare(Model):
    eps: dict[int, float | None]          # basic EPS (KRW)
    dps_common: dict[int, float | None]   # cash dividend per common share (KRW)


class NoteItem(Model):
    label: str
    amount: float                         # latest fiscal year, KRW million
    line_id: str                          # BS line it was derived from
    category: str


class NotesSummary(Model):
    """Derived from balance-sheet lines, not parsed from note text (D2.2)."""

    borrowings: list[NoteItem] = Field(default_factory=list)
    non_operating_assets: list[NoteItem] = Field(default_factory=list)


class CBInstrument(Model):
    series: str
    face_outstanding: float               # KRW million
    conversion_price: float               # KRW per share, as of eval_date
    convertible_shares: float             # face_outstanding * 1e6 / conversion_price
    refix_floor: float | None = None      # KRW per share
    issue_date: date | None = None
    maturity: date | None = None
    complex_terms: bool | None = None     # call option / net settlement; None = unknown


class CBBlock(Model):
    instruments: list[CBInstrument]
    filing_text: str                      # Korean disclosure text (generated, D2.6)
    outstanding_table_text: str


class PackageMeta(Model):
    firm_id: str                          # "L001", "M001", "S001", or "U<corp_code>"
    corp_code: str
    ticker: str
    real_name: str
    ksic: str | None
    industry_label: str | None
    group: Literal["L", "M", "S", "U"]    # U = universe (not in the sample)
    market: Literal["KOSPI", "KOSDAQ"]
    eval_date: date
    fiscal_year: int
    source_rcept_no: str
    fs_div: Literal["CFS", "OFS"]
    net_change_includes_fx: bool | None = None
    flags: list[str] = Field(default_factory=list)


class InputPackage(Model):
    schema_version: str = SCHEMA_VERSION
    meta: PackageMeta
    unit: Literal["KRW_million"] = "KRW_million"
    years: list[int]                      # ascending, length 3
    bs: Statement
    is_: Statement = Field(alias="is")
    cf: Statement
    per_share: PerShare
    shares: ShareInfo
    notes: NotesSummary
    cb: CBBlock | None = None

    @model_validator(mode="after")
    def _check(self) -> InputPackage:
        if self.years != sorted(self.years) or len(self.years) != 3:
            raise ValueError("years must be three ascending fiscal years")
        for st, code in ((self.bs, "BS"), (self.is_, "IS"), (self.cf, "CF")):
            if st.code != code:
                raise ValueError(f"statement code mismatch: {st.code} != {code}")
        ids = [ln.line_id for st in self.statements() for ln in st.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("line_id values must be unique")
        return self

    @property
    def latest_year(self) -> int:
        return self.years[-1]

    def statements(self) -> tuple[Statement, Statement, Statement]:
        return self.bs, self.is_, self.cf

    def statement(self, code: StatementCode) -> Statement:
        return {"BS": self.bs, "IS": self.is_, "CF": self.cf}[code]

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True, indent=1)

    @classmethod
    def from_json(cls, text: str) -> InputPackage:
        return cls.model_validate_json(text)

    def package_hash(self) -> str:
        return stable_hash(self.model_dump(mode="json", by_alias=True))
