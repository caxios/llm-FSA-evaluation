"""P3: share-count perturbation (E3, D3.1)."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.perturb import perturb
from tests.fakes import PACKAGE_NAMES, load_package

PKGS = {n: load_package(n) for n in PACKAGE_NAMES}


@pytest.mark.parametrize("name", PACKAGE_NAMES)
def test_shares_double(name):
    pkg = PKGS[name]
    out, meta = perturb(pkg, "shares", m=2.0)
    assert meta.params == {"m": 2.0}
    assert out.shares.common_outstanding == 2 * pkg.shares.common_outstanding
    assert out.shares.preferred_issued == 2 * pkg.shares.preferred_issued
    assert (out.bs, out.cf) == (pkg.bs, pkg.cf)
    for y in pkg.years:
        for field in ("eps", "dps_common"):
            v, w = getattr(pkg.per_share, field)[y], getattr(out.per_share, field)[y]
            assert (v is None and w is None) or w == pytest.approx(v / 2)
            if v is not None:  # EPS x shares invariant
                assert w * out.shares.common_outstanding == pytest.approx(
                    v * pkg.shares.common_outstanding)
    eps = pkg.is_.find("eps_basic")
    if eps is not None:
        y = pkg.latest_year
        assert out.is_.value("eps_basic", y) == pytest.approx(eps.values[y] / 2)


def test_m_one_is_identity():
    for pkg in PKGS.values():
        assert perturb(pkg, "shares", m=1.0)[0] == pkg


def test_cb_gets_split_adjustment():
    pkg = PKGS["unmapped_heavy"]
    out, _ = perturb(pkg, "shares", m=2.0)
    for a, b in zip(pkg.cb.instruments, out.cb.instruments, strict=True):
        assert b.conversion_price == a.conversion_price / 2
        assert b.convertible_shares == pytest.approx(a.convertible_shares * 2)
        assert b.refix_floor == a.refix_floor / 2
        assert b.face_outstanding == a.face_outstanding
    assert f"{round(4241 / 2):,}원" in out.cb.filing_text
    dil_a = sum(i.convertible_shares for i in pkg.cb.instruments) / pkg.shares.common_outstanding
    dil_b = sum(i.convertible_shares for i in out.cb.instruments) / out.shares.common_outstanding
    assert dil_a == pytest.approx(dil_b)


@settings(max_examples=30, deadline=None)
@given(name=st.sampled_from(PACKAGE_NAMES), a=st.floats(0.5, 5.0), b=st.floats(0.5, 5.0))
def test_composition(name, a, b):
    pkg = PKGS[name]
    twice = perturb(perturb(pkg, "shares", m=a)[0], "shares", m=b)[0]
    once = perturb(pkg, "shares", m=a * b)[0]
    assert twice.shares.common_issued == pytest.approx(once.shares.common_issued)
    for y in pkg.years:
        v, w = twice.per_share.eps[y], once.per_share.eps[y]
        assert (v is None and w is None) or v == pytest.approx(w)
