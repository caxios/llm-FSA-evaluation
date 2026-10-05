"""P3: perturbation interface, ancestry propagation, identity enforcement."""

import pytest

from src.perturb import REGISTRY, PerturbationInconsistent, PerturbMeta, perturb
from src.perturb.base import add_line, apply_delta, book_equity, chain, outflow_sign
from tests.fakes import PACKAGE_NAMES, load_package


def canon(lines):
    return [ln.canonical for ln in lines]


def test_chain_follows_parent_then_ancestry():
    pkg = load_package("large_pref")
    assert canon(chain(pkg.bs, pkg.bs.get("cash"))) == ["current_assets", "total_assets"]
    assert canon(chain(pkg.bs, pkg.bs.get("retained_earnings"))) == [
        "equity_owners", "total_equity", "total_liabilities_and_equity"]
    assert canon(chain(pkg.cf, pkg.cf.get("dividends_paid"))) == [
        "cff", "net_change_in_cash", "ending_cash"]


def test_chain_skips_unreported_subtotals():
    pkg = load_package("small_cb_single")  # reports the pre-FX change, no net change line
    assert pkg.cf.find("net_change_in_cash") is None
    line = pkg.cf.get("proceeds_from_convertible_bonds")
    assert canon(chain(pkg.cf, line)) == ["cff", "net_change_before_fx", "ending_cash"]


def test_apply_delta_and_leaf_override():
    pkg = load_package("large_pref")
    y = pkg.latest_year
    before = {c: pkg.cf.value(c, y) for c in ("dividends_paid", "cff", "ending_cash")}
    touched = apply_delta(pkg, "CF", "dividends_paid", y, -100.0, leaf_delta=100.0)
    assert len(touched) == 4
    assert pkg.cf.value("dividends_paid", y) == before["dividends_paid"] + 100
    assert pkg.cf.value("cff", y) == before["cff"] - 100
    assert pkg.cf.value("ending_cash", y) == before["ending_cash"] - 100
    assert pkg.cf.value("ending_cash", y - 1) == pytest.approx(
        load_package("large_pref").cf.value("ending_cash", y - 1))


def test_add_line_is_placed_after_siblings():
    pkg = load_package("mid")
    line = add_line(pkg.cf, "배당금의 지급", "cff", pkg.years, canonical="dividends_paid")
    ordered = sorted(pkg.cf.lines, key=lambda ln: ln.order)
    i = ordered.index(line)
    assert ordered[i - 1].parent == "cff" and ordered[i + 1].parent != "cff"
    assert [ln.order for ln in ordered] == list(range(len(ordered)))
    assert line.derived and line.values == {y: None for y in pkg.years}


def test_perturb_is_pure_and_checks_identities(monkeypatch):
    pkg = load_package("mid")
    h = pkg.package_hash()

    def broken(p):
        p.bs.get("cash").values[p.latest_year] += 1_000.0  # no counterpart
        return PerturbMeta(type="none")

    monkeypatch.setitem(REGISTRY, "broken", broken)
    with pytest.raises(PerturbationInconsistent):
        perturb(pkg, "broken")
    perturb(pkg, "cash", x_mn=100.0)
    assert pkg.package_hash() == h


def test_perturb_rejects_new_soft_violation(monkeypatch):
    def cash_only(p):  # balanced BS change that breaks ending cash = BS cash
        y = p.latest_year
        apply_delta(p, "BS", "cash", y, 1_000.0)
        apply_delta(p, "BS", "retained_earnings", y, 1_000.0)
        return PerturbMeta(type="none")

    monkeypatch.setitem(REGISTRY, "cash_only", cash_only)
    with pytest.raises(PerturbationInconsistent, match="cf_bs_cash"):
        perturb(load_package("large_pref"), "cash_only")


def test_unknown_perturbation():
    with pytest.raises(KeyError):
        perturb(load_package("mid"), "nope")


@pytest.mark.parametrize("name", PACKAGE_NAMES)
def test_helpers(name):
    pkg = load_package(name)
    assert outflow_sign(pkg) in (1, -1)
    assert book_equity(pkg) is not None
