"""Synthetic agents (P5 §5.4): no API calls, same `Agent` protocol and runner path.

Used in P6 to validate the metrics against agents with known behaviour.

  OracleAgent      reads the true values from the package, applies fixed assumptions
                   (growth 3%, margin = last-year margin, tax 22%, WACC 8%, g 2%) and values
                   with `valuation_tools`; noise multiplies the projected operating flows
                   by exp(N(0, sd)), so every reported field stays self-consistent.
                   Applies dilution correctly (if-converted with the min rule).
  AnchoredAgent    reports anchor[firm_id] x noise, ignoring the package.
  MixtureAgent     exp(w log V_oracle + (1 - w) log V_anchor) x noise.
  NoDilutionAgent  Oracle that extracts the convertible shares but does not apply them.
  CalcErrorAgent   Oracle whose reported per-share value is 10% off its own calculation.
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


def oracle_inputs(pkg: InputPackage, noise_factor: float = 1.0, apply_dilution: bool = True
                  ) -> ToolInputs:
    ex = true_extraction(pkg)
    margin = ex.operating_income / ex.revenue if ex.revenue else 0.0
    projections = []
    for t in range(1, 6):
        rev = ex.revenue * (1 + GROWTH) ** t * noise_factor
        ebit = rev * margin
        reinvest = (ex.capex or 0.0) * (1 + GROWTH) ** t * noise_factor
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


SYNTHETIC = {"oracle": OracleAgent, "no_dilution": NoDilutionAgent,
             "calc_error": CalcErrorAgent}
