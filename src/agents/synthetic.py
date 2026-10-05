"""Synthetic agents (P5 §5.4): no API calls, same `Agent` protocol and runner path.

Used in P6 to validate the metrics against agents with known behaviour.

  OracleAgent      reads the true values from the package, applies fixed assumptions
                   (growth 3%, margin = mean of the three reported years with a 5% floor,
                   tax 22%, WACC 8%, g 2%) and values with `valuation_tools`. Noise
                   multiplies every amount the oracle reads (flows, cash, debt,
                   non-operating assets, CB face) by exp(N(0, sd)), so the per-share value
                   moves by exactly that factor and every reported field stays
                   self-consistent. Applies dilution correctly (if-converted, min rule).
  AnchoredAgent    reports anchor[firm_id] x noise, ignoring the package.
  MixtureAgent     exp(w log V_oracle + (1 - w) log V_anchor) x noise.
  NoDilutionAgent  Oracle that extracts the convertible shares but does not apply them.
  CalcErrorAgent   Oracle whose reported per-share value is 10% off its own calculation.
  ConditionMixtureAgent  Mixture with a weight per information condition (E4 checks).
Projections assume capex = D&A (steady state) and no working-capital change, so FCFF is
NOPAT: many packages report no separate depreciation line.
Noise draws are seeded from the request (messages, rep, agent), so reruns reproduce.
"""

from __future__ import annotations

import math

import numpy as np

from src.agents.base import RunRecord, RunRequest, make_record
from src.agents.valuation_tools import value_from_inputs
from src.data.package_schema import InputPackage
from src.parse.schema import (
    Assumptions,
    Dilution,
    Extracted,
    Meta,
    ProjectionYear,
    ToolInputs,
    ValuationOutput,
)
from src.utils.hashing import stable_hash

GROWTH, TAX, WACC, G = 0.03, 0.22, 0.08, 0.02
MARGIN_FLOOR = 0.05   # keeps the oracle's value positive for most loss-making firms


def _v(st, canonical: str, year: int) -> float | None:
    line = st.find(canonical)
    return None if line is None else line.values.get(year)


def true_extraction(pkg: InputPackage) -> Extracted:
    y = pkg.latest_year
    op = _v(pkg.is_, "operating_income", y) or 0.0
    revenue = _v(pkg.is_, "revenue", y)
    if revenue is None:
        revenue = (_v(pkg.is_, "operating_expense", y) or 0.0) + op
    da = sum(abs(_v(pkg.cf, c, y) or 0.0) for c in ("depreciation", "amortisation"))
    capex = sum(abs(_v(pkg.cf, c, y) or 0.0) for c in ("capex_ppe", "capex_intangibles"))
    face = conv_price = None
    if pkg.cb is not None and pkg.cb.instruments:
        face = sum(i.face_outstanding for i in pkg.cb.instruments)
        shares_cb = sum(i.convertible_shares for i in pkg.cb.instruments)
        conv_price = face * 1e6 / shares_cb
    return Extracted(
        base_year=y, revenue=revenue, operating_income=op,
        depreciation_amortization=da or None, capex=capex or None,
        change_in_working_capital=0.0,
        cash_and_equivalents=_v(pkg.bs, "cash", y) or 0.0,
        total_borrowings=sum(i.amount for i in pkg.notes.borrowings),
        non_operating_assets=sum(i.amount for i in pkg.notes.non_operating_assets),
        shares_outstanding=pkg.shares.common_outstanding,
        convertible_bonds_outstanding=face, conversion_price=conv_price)


def oracle_margin(pkg: InputPackage) -> float:
    margins = []
    for y in pkg.years:
        rev, op = _v(pkg.is_, "revenue", y), _v(pkg.is_, "operating_income", y)
        if rev and op is not None:
            margins.append(op / rev)
    return max(float(np.mean(margins)) if margins else 0.0, MARGIN_FLOOR)


def _scaled(ex: Extracted, f: float) -> Extracted:
    if f == 1.0:
        return ex
    upd = {k: (getattr(ex, k) * f if getattr(ex, k) is not None else None)
           for k in ("revenue", "operating_income", "depreciation_amortization", "capex",
                     "cash_and_equivalents", "total_borrowings", "non_operating_assets",
                     "convertible_bonds_outstanding")}
    return ex.model_copy(update=upd)


def oracle_inputs(pkg: InputPackage, noise_factor: float = 1.0, apply_dilution: bool = True
                  ) -> ToolInputs:
    ex = _scaled(true_extraction(pkg), noise_factor)
    margin = oracle_margin(pkg)
    projections = []
    for t in range(1, 6):
        rev = ex.revenue * (1 + GROWTH) ** t
        ebit = rev * margin
        reinvest = (ex.capex or 0.0) * (1 + GROWTH) ** t
        projections.append(ProjectionYear(revenue=rev, ebit=ebit, tax=max(ebit, 0.0) * TAX,
                                          depreciation_amortization=reinvest, capex=reinvest,
                                          change_in_nwc=0.0))
    shares_cb = None
    if pkg.cb is not None and pkg.cb.instruments:
        shares_cb = sum(i.convertible_shares for i in pkg.cb.instruments)
    return ToolInputs(
        extracted=ex,
        assumptions=Assumptions(revenue_growth=[GROWTH] * 5, operating_margin=[margin] * 5,
                                tax_rate=TAX, wacc=WACC, terminal_growth=G,
                                assumption_rationale="synthetic oracle"),
        projections=projections,
        dilution=Dilution(dilution_applied=apply_dilution and shares_cb is not None,
                          convertible_shares=shares_cb),
        meta=Meta(data_anomaly_flag=False, sources_used="synthetic"))


class _Synthetic:
    structure = "SYN"
    name = "synthetic"

    def __init__(self, noise_sd: float = 0.05):
        self.noise_sd = noise_sd

    def params(self) -> dict:
        return {"noise_sd": self.noise_sd}

    def identity(self) -> dict:
        return {"synthetic": self.name, **self.params()}

    def _z(self, req: RunRequest) -> float:
        seed = int(stable_hash({"m": req.messages, "rep": req.rep, "a": self.identity()})[:15],
                   16)
        return float(np.random.default_rng(seed).normal(0.0, 1.0)) * self.noise_sd

    def value(self, req: RunRequest, pkg: InputPackage) -> ValuationOutput:
        raise NotImplementedError

    def run(self, req: RunRequest, package: InputPackage | None = None) -> RunRecord:
        if package is None:
            raise ValueError("synthetic agents need the package")
        try:
            out = self.value(req, package)
            return make_record(req, self.identity(), valid=True,
                               output=out.model_dump(mode="json"), raws=[], error=None,
                               model_reported=self.name)
        except (ValueError, ZeroDivisionError) as e:
            return make_record(req, self.identity(), valid=False, output=None, raws=[],
                               error=f"synthetic: {e}", model_reported=self.name)


class OracleAgent(_Synthetic):
    name = "oracle"
    apply_dilution = True

    def value(self, req: RunRequest, pkg: InputPackage) -> ValuationOutput:
        return value_from_inputs(oracle_inputs(pkg, math.exp(self._z(req)),
                                               self.apply_dilution))


class NoDilutionAgent(OracleAgent):
    name = "no_dilution"
    apply_dilution = False


class CalcErrorAgent(OracleAgent):
    name = "calc_error"
    error = 0.10

    def value(self, req: RunRequest, pkg: InputPackage) -> ValuationOutput:
        out = super().value(req, pkg)
        out.result.value_per_share *= 1 + self.error
        return out


class AnchoredAgent(_Synthetic):
    name = "anchored"

    def __init__(self, anchor: dict[str, float], noise_sd: float = 0.05):
        super().__init__(noise_sd)
        self.anchor = anchor

    def params(self) -> dict:
        return {"noise_sd": self.noise_sd, "anchor": self.anchor}

    def value(self, req: RunRequest, pkg: InputPackage) -> ValuationOutput:
        out = value_from_inputs(oracle_inputs(pkg))
        out.result.value_per_share = self.anchor[req.firm_id] * math.exp(self._z(req))
        return out


class MixtureAgent(AnchoredAgent):
    name = "mixture"

    def __init__(self, anchor: dict[str, float], w: float, noise_sd: float = 0.05):
        super().__init__(anchor, noise_sd)
        self.w = w

    def params(self) -> dict:
        return {**super().params(), "w": self.w}

    def value(self, req: RunRequest, pkg: InputPackage) -> ValuationOutput:
        out = value_from_inputs(oracle_inputs(pkg))
        v_oracle = out.result.value_per_share
        if v_oracle <= 0:
            raise ValueError("mixture needs a positive oracle value")
        log_v = self.w * math.log(v_oracle) + (1 - self.w) * math.log(self.anchor[req.firm_id])
        out.result.value_per_share = math.exp(log_v + self._z(req))
        return out


class ConditionMixtureAgent(MixtureAgent):
    """Mixture whose oracle weight depends on the information condition (P6 validation of
    the E4 decomposition)."""

    name = "condition_mixture"

    def __init__(self, anchor: dict[str, float], w_by_condition: dict[str, float],
                 noise_sd: float = 0.05):
        super().__init__(anchor, w=1.0, noise_sd=noise_sd)
        self.w_by_condition = w_by_condition

    def params(self) -> dict:
        return {**super().params(), "w_by_condition": self.w_by_condition}

    def value(self, req: RunRequest, pkg: InputPackage) -> ValuationOutput:
        self_w = self.w_by_condition[req.condition]
        out = value_from_inputs(oracle_inputs(pkg))
        v_oracle = out.result.value_per_share
        if v_oracle <= 0:
            raise ValueError("mixture needs a positive oracle value")
        log_v = self_w * math.log(v_oracle) + (1 - self_w) * math.log(self.anchor[req.firm_id])
        out.result.value_per_share = math.exp(log_v + self._z(req))
        return out


SYNTHETIC = {"oracle": OracleAgent, "no_dilution": NoDilutionAgent,
             "calc_error": CalcErrorAgent}
