"""P3: scale perturbation (E2, E5)."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.perturb import PerturbationNotApplicable, perturb, without_cb
from tests.fakes import PACKAGE_NAMES, load_package

PKGS = {n: without_cb(load_package(n)) for n in PACKAGE_NAMES}


def monetary(pkg):
    out = {}
    for s in pkg.statements():
        for ln in s.lines:
            for y, v in ln.values.items():
                out[(ln.line_id, y)] = v
    for y, v in pkg.per_share.eps.items():
        out[("eps", y)] = v
    for y, v in pkg.per_share.dps_common.items():
        out[("dps", y)] = v
    for it in pkg.notes.borrowings + pkg.notes.non_operating_assets:
        out[("note", it.line_id)] = it.amount
    return out


def assert_scaled(a, b, k):
    va, vb = monetary(a), monetary(b)
    assert va.keys() == vb.keys()
    for key, v in va.items():
        assert (v is None and vb[key] is None) or vb[key] == pytest.approx(v * k, rel=1e-12)


@pytest.mark.parametrize("name", PACKAGE_NAMES)
@pytest.mark.parametrize("k", [0.5, 0.8, 1.25, 1.5, 2.0])
def test_scale_keeps_identities(name, k):
    out, meta = perturb(PKGS[name], "scale", k=k)
    assert meta.params == {"k": k}
    assert_scaled(PKGS[name], out, k)
    assert out.shares == PKGS[name].shares


def test_k_one_is_identity():
    pkg = PKGS["large_pref"]
    out, _ = perturb(pkg, "scale", k=1.0)
    assert out == pkg


def test_cb_package_raises():
    with pytest.raises(PerturbationNotApplicable):
        perturb(load_package("small_cb_single"), "scale", k=2.0)


@settings(max_examples=30, deadline=None)
@given(name=st.sampled_from(PACKAGE_NAMES), a=st.floats(0.3, 3.0), b=st.floats(0.3, 3.0))
def test_composition(name, a, b):
    pkg = PKGS[name]
    twice, _ = perturb(perturb(pkg, "scale", k=a)[0], "scale", k=b)
    once, _ = perturb(pkg, "scale", k=a * b)
    va, vb = monetary(twice), monetary(once)
    for key, v in va.items():
        assert (v is None and vb[key] is None) or vb[key] == pytest.approx(v, rel=1e-9)
