"""Output schemas (research plan Appendix A with D4 / D5.1 additions; P5 §5.1).

Units: amounts in KRW million, per-share values in KRW, rates as decimals (0.08).
Rates given as percentages (8.5) are converted to decimals and flagged in
`assumptions.normalized_percent`; the output stays valid and the event is logged.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "v1"
DONT_KNOW = {"모른다", "모름", "알 수 없음", "알수없음", "unknown", "n/a", "na", "-", ""}


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


def _five(v: list[float]) -> list[float]:
    if len(v) != 5:
        raise ValueError(f"expected 5 yearly values, got {len(v)}")
    return v


class Extracted(_Model):
    base_year: int
    unit: Literal["KRW_million"] = "KRW_million"
    revenue: float
    operating_income: float
    depreciation_amortization: float | None = None
    capex: float | None = None
    change_in_working_capital: float | None = None
    cash_and_equivalents: float
    total_borrowings: float
    non_operating_assets: float | None = None
    shares_outstanding: float = Field(gt=0)
    convertible_bonds_outstanding: float | None = None
    conversion_price: float | None = None


class Assumptions(_Model):
    revenue_growth: list[float]
    operating_margin: list[float]
    tax_rate: float
    wacc: float
    terminal_growth: float
    assumption_rationale: str = ""
    normalized_percent: bool = False

    _check_growth = field_validator("revenue_growth", "operating_margin")(_five)

    @model_validator(mode="after")
    def _rates(self) -> Assumptions:
        changed = False
        for name in ("tax_rate", "wacc", "terminal_growth"):
            v = getattr(self, name)
            if abs(v) > 1:
                object.__setattr__(self, name, v / 100)
                changed = True
        for name in ("revenue_growth", "operating_margin"):
            vals = getattr(self, name)
            if any(abs(x) > 1 for x in vals):
                object.__setattr__(self, name, [x / 100 for x in vals])
                changed = True
        if changed:
            object.__setattr__(self, "normalized_percent", True)
        if self.wacc <= self.terminal_growth:
            raise ValueError(f"wacc ({self.wacc}) must exceed terminal_growth "
                             f"({self.terminal_growth})")
        if self.wacc <= 0:
            raise ValueError("wacc must be positive")
        return self


class Calculation(_Model):
    fcff: list[float]
    terminal_value: float
    enterprise_value: float
    net_debt: float
    non_operating_assets_added: float = 0.0
    equity_value: float
    shares_used: float = Field(gt=0)
    discounting_convention: Literal["end_of_year", "mid_year"]

    _check_fcff = field_validator("fcff")(_five)


class Dilution(_Model):
    dilution_applied: bool
    convertible_shares: float | None = None
    diluted_shares: float | None = None


class Result(_Model):
    value_per_share: float
    ev_ebitda_crosscheck_per_share: float | None = None


class Meta(_Model):
    data_anomaly_flag: bool
    data_anomaly_note: str = ""
    sources_used: str = ""


class ValuationOutput(_Model):
    extracted: Extracted
    assumptions: Assumptions
    calculation: Calculation
    dilution: Dilution
    result: Result
    meta: Meta


# ---------------------------------------------------------------- tool agent (D5.2)


class ProjectionYear(_Model):
    revenue: float
    ebit: float
    tax: float
    depreciation_amortization: float
    capex: float
    change_in_nwc: float


class ToolInputs(_Model):
    """What the tool agent's single call returns; Python does the valuation."""

    extracted: Extracted
    assumptions: Assumptions
    projections: list[ProjectionYear]
    dilution: Dilution
    ev_ebitda_multiple: float | None = None
    meta: Meta

    @field_validator("projections")
    @classmethod
    def _five_years(cls, v: list[ProjectionYear]) -> list[ProjectionYear]:
        if len(v) != 5:
            raise ValueError(f"expected 5 projection years, got {len(v)}")
        return v


# ---------------------------------------------------------------- E5 / E6


class IdentificationOutput(_Model):
    guess_name: str | None = None
    guess_ticker: str | None = None
    confidence: float = Field(ge=0, le=1)

    @field_validator("guess_name", "guess_ticker", mode="before")
    @classmethod
    def _unknown(cls, v):
        return None if v is None or str(v).strip().lower() in DONT_KNOW else str(v).strip()

    @field_validator("confidence", mode="before")
    @classmethod
    def _pct(cls, v):
        return float(v) / 100 if v is not None and float(v) > 1 else v


class QuizOutput(_Model):
    """E6 answers. Q1-Q3 in KRW 100 million (억 원), Q4 in KRW; "모른다" -> None."""

    q1_market_cap: float | None = None
    q2_revenue: float | None = None
    q3_operating_income: float | None = None
    q4_share_price: float | None = None
    q5_main_business: str | None = None
    q6_market: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _unknown(cls, v):
        if v is None or (isinstance(v, str) and v.strip().lower() in DONT_KNOW):
            return None
        if isinstance(v, str):
            s = v.replace(",", "").strip()
            try:
                return float(s)
            except ValueError:
                return v.strip()
        return v


SCHEMAS: dict[str, type[BaseModel]] = {
    "valuation": ValuationOutput, "tool": ToolInputs,
    "identification": IdentificationOutput, "quiz": QuizOutput,
}
