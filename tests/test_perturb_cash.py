"""P3: cash distribution (E3, D3.2)."""

import pytest

from src.perturb import PerturbationOutOfRange, perturb
from tests.fakes import PACKAGE_NAMES, load_package


@pytest.mark.parametrize("name", PACKAGE_NAMES)
def test_cash_distribution(name):
    pkg = load_package(name)
    y = pkg.latest_year
    x = 0.5 * pkg.bs.value("cash", y)
    out, meta = perturb(pkg, "cash", x_mn=x)
    for st, c in (("bs", "cash"), ("bs", "current_assets"), ("bs", "total_assets"),
                  ("bs", "retained_earnings"), ("bs", "total_equity"),
                  ("cf", "cff"), ("cf", "ending_cash")):
        a, b = getattr(pkg, st), getattr(out, st)
        assert b.value(c, y) == pytest.approx(a.value(c, y) - x), c
        assert b.value(c, y - 1) == a.value(c, y - 1)
    assert out.is_ == pkg.is_
    dps = out.per_share.dps_common[y] - (pkg.per_share.dps_common[y] or 0.0)
    assert dps == pytest.approx(x * 1e6 / pkg.shares.common_outstanding)
    assert meta.params["dps_delta"] == pytest.approx(dps)
    assert meta.year == y


def test_dividend_line_follows_sign_convention():
    pos = load_package("large_pref")       # outflows reported as positive numbers
    y = pos.latest_year
    out, _ = perturb(pos, "cash", x_mn=1000.0)
    assert out.cf.value("dividends_paid", y) == pos.cf.value("dividends_paid", y) + 1000

    mid = load_package("mid")              # no dividend line: one is created
    assert mid.cf.find("dividends_paid") is None
    out, meta = perturb(mid, "cash", x_mn=1000.0)
    line = out.cf.get("dividends_paid")
    assert line.derived and line.parent == "cff" and line.label == "배당금의 지급"
    assert line.values == {y - 2: None, y - 1: None, y: 1000.0}

    neg = load_package("unmapped_heavy")   # outflows reported as negative numbers
    out, meta = perturb(neg, "cash", x_mn=1000.0)
    assert out.cf.line(meta.params["dividend_line"]).values[y] == -1000.0


def test_zero_is_identity():
    pkg = load_package("large_pref")
    out, _ = perturb(pkg, "cash", x_mn=0.0)
    assert out == pkg


def test_guards():
    pkg = load_package("mid")
    cash = pkg.bs.value("cash", pkg.latest_year)
    with pytest.raises(PerturbationOutOfRange):
        perturb(pkg, "cash", x_mn=cash + 1)
    with pytest.raises(PerturbationOutOfRange):
        perturb(pkg, "cash", x_mn=-1.0)
    perturb(pkg, "cash", x_mn=cash)  # the whole balance is allowed
