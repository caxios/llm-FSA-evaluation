"""P3: non-operating asset perturbation (E3, D2)."""

import pytest

from src.perturb import PerturbationOutOfRange, perturb
from src.utils.hashing import stable_hash
from tests.fakes import PACKAGE_NAMES, load_package


def h(statement):
    return stable_hash(statement.model_dump(mode="json"))


@pytest.mark.parametrize("name", PACKAGE_NAMES)
def test_non_operating(name):
    pkg = load_package(name)
    y = pkg.latest_year
    x = 0.05 * pkg.bs.value("total_equity", y)
    out, meta = perturb(pkg, "non_operating", x_mn=x)
    for c in ("non_current_assets", "total_assets", "total_equity"):
        assert out.bs.value(c, y) == pytest.approx(pkg.bs.value(c, y) + x)
    asset = out.bs.line(meta.params["asset_line"])
    assert asset.category == "nonop:fvoci"
    note = [i for i in out.notes.non_operating_assets if i.line_id == asset.line_id]
    assert len(note) == 1 and note[0].amount == pytest.approx(asset.values[y])
    assert h(out.is_) == h(pkg.is_) and h(out.cf) == h(pkg.cf)


def test_line_created_when_absent_and_oci_reserve_used():
    pkg = load_package("mid")  # no FVOCI line; reports an OCI reserve
    assert not pkg.bs.by_category("nonop:fvoci")
    y = pkg.latest_year
    out, meta = perturb(pkg, "non_operating", x_mn=500.0)
    asset = out.bs.line(meta.params["asset_line"])
    assert asset.derived and asset.parent == "non_current_assets"
    assert asset.label == "기타포괄손익-공정가치 측정 금융자산"
    assert asset.values == {y - 2: None, y - 1: None, y: 500.0}
    assert out.bs.line(meta.params["equity_line"]).canonical == "oci_reserve"
    assert out.bs.value("oci_reserve", y) == pytest.approx(pkg.bs.value("oci_reserve", y) + 500)


def test_existing_line_and_other_equity():
    pkg = load_package("large_pref")  # FVOCI line exists; no OCI reserve line
    fv = [ln for ln in pkg.bs.by_category("nonop:fvoci") if ln.parent == "non_current_assets"]
    out, meta = perturb(pkg, "non_operating", x_mn=500.0)
    assert meta.params["asset_line"] == fv[0].line_id
    assert out.bs.line(meta.params["equity_line"]).canonical == "other_equity"


def test_negative_raises():
    with pytest.raises(PerturbationOutOfRange):
        perturb(load_package("mid"), "non_operating", x_mn=-1.0)
