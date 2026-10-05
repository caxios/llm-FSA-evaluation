"""P3: CB variants V0-V4 (E8, D3, D3.3)."""

import pytest

from src.data.render import render_user_prompt
from src.perturb import PerturbationNotApplicable, perturb
from src.perturb.cb import v3_price
from tests.fakes import CB_PACKAGE_NAMES, load_package


def enterprise_equity(pkg):
    """E = equity - net debt, from the balance sheet (latest year)."""
    y = pkg.latest_year
    debt = sum(ln.values.get(y) or 0.0 for ln in pkg.bs.by_category("debt:"))
    return pkg.bs.value("total_equity", y) - (debt - pkg.bs.value("cash", y))


@pytest.mark.parametrize("name", CB_PACKAGE_NAMES)
def test_v0_is_unchanged(name):
    pkg = load_package(name)
    out, meta = perturb(pkg, "cb_v0")
    assert out == pkg
    assert meta.params["face_mn"] == pytest.approx(sum(i.face_outstanding
                                                       for i in pkg.cb.instruments))
    assert len(meta.instruments) == len(pkg.cb.instruments)


@pytest.mark.parametrize("name", CB_PACKAGE_NAMES)
def test_v1_removes_cb_terms(name):
    pkg = load_package(name)
    out, _ = perturb(pkg, "cb_v1")
    assert out.cb is None and (out.bs, out.cf) == (pkg.bs, pkg.cf)
    text = render_user_prompt(out, "C", include_cb=True)
    for ins in pkg.cb.instruments:
        assert f"{round(ins.conversion_price):,}원" not in text
        assert f"{round(ins.face_outstanding * 1e6):,}" not in text
    assert "전환가액" not in text
    assert text.rstrip().endswith("없음")


@pytest.mark.parametrize("name", CB_PACKAGE_NAMES)
def test_v2_doubles_face_and_keeps_equity(name):
    pkg = load_package(name)
    y = pkg.latest_year
    out, meta = perturb(pkg, "cb_v2")
    delta = sum(i.face_outstanding for i in pkg.cb.instruments)
    assert meta.params["delta_face_mn"] == pytest.approx(delta)
    for a, b in zip(pkg.cb.instruments, out.cb.instruments, strict=True):
        assert b.face_outstanding == 2 * a.face_outstanding
        assert b.convertible_shares == pytest.approx(2 * a.convertible_shares)
        assert b.conversion_price == a.conversion_price
        assert f"{round(b.face_outstanding * 1e6):,}원" in out.cb.filing_text
    assert enterprise_equity(out) == pytest.approx(enterprise_equity(pkg))
    assert out.bs.value("cash", y) == pytest.approx(pkg.bs.value("cash", y) + delta)
    assert out.cf.value("ending_cash", y) == pytest.approx(pkg.cf.value("ending_cash", y) + delta)
    bal = out.bs.line(meta.params["bs_line"])
    assert bal.category == "debt:convertible"
    assert [i.amount for i in out.notes.borrowings if i.line_id == bal.line_id] == [
        bal.values[y]]


def test_v2_creates_lines_when_absent():
    pkg = load_package("small_cb_multi")   # no BS convertible-bond line
    assert not pkg.bs.by_category("debt:convertible")
    out, meta = perturb(pkg, "cb_v2")
    bal = out.bs.line(meta.params["bs_line"])
    assert bal.derived and bal.label == "전환사채" and bal.parent == "non_current_liabilities"


@pytest.mark.parametrize("name", CB_PACKAGE_NAMES)
def test_v3_respects_floor(name):
    pkg = load_package(name)
    out, meta = perturb(pkg, "cb_v3")
    for a, b, d in zip(pkg.cb.instruments, out.cb.instruments, meta.instruments, strict=True):
        floor = a.refix_floor if a.refix_floor is not None else 0.7 * a.conversion_price
        assert b.conversion_price >= floor - 1e-9
        assert b.conversion_price >= 0.5 * a.conversion_price
        assert d["ratio"] == pytest.approx(b.conversion_price / a.conversion_price)
        assert d["floor_assumed"] == ("yes" if a.refix_floor is None else "no")
        assert b.convertible_shares == pytest.approx(b.face_outstanding * 1e6
                                                     / b.conversion_price)
        if d["changed"] == "yes":
            assert f"현재 전환가액: {round(b.conversion_price):,}원" in out.cb.filing_text
            assert f"현재 전환가액: {round(a.conversion_price):,}원" not in out.cb.filing_text
    assert (out.bs, out.is_, out.cf) == (pkg.bs, pkg.is_, pkg.cf)


def test_v3_price_rule():
    pkg = load_package("unmapped_heavy")
    ins = pkg.cb.instruments[0]          # Pc 4,241, floor 2,984 (> 0.5 Pc)
    assert v3_price(ins) == (2984.0, False)
    ins.refix_floor = 1500.0             # floor below 0.5 Pc -> 0.5 Pc, rounded up
    assert v3_price(ins) == (2121.0, False)
    ins.refix_floor = None               # undisclosed -> 70% of Pc
    assert v3_price(ins) == (2969.0, True)


def test_v3_at_floor_is_not_applicable():
    pkg = load_package("unmapped_heavy")
    for ins in pkg.cb.instruments:
        ins.refix_floor = ins.conversion_price
    with pytest.raises(PerturbationNotApplicable, match="floor"):
        perturb(pkg, "cb_v3")


@pytest.mark.parametrize("name", CB_PACKAGE_NAMES)
@pytest.mark.parametrize("placebo,marker", [("redeemed_cb", "상환 완료"),
                                            ("irrelevant", "본점소재지 변경")])
def test_v4_adds_text_only(name, placebo, marker):
    pkg = load_package(name)
    out, meta = perturb(pkg, "cb_v4", placebo=placebo)
    assert out.cb.filing_text.startswith(pkg.cb.filing_text + "\n\n")
    assert marker in out.cb.filing_text and "{" not in out.cb.filing_text
    assert out.cb.instruments == pkg.cb.instruments
    assert out.cb.outstanding_table_text == pkg.cb.outstanding_table_text
    assert (out.bs, out.is_, out.cf, out.shares) == (pkg.bs, pkg.is_, pkg.cf, pkg.shares)
    assert meta.params["placebo"] == placebo
    assert perturb(pkg, "cb_v4", placebo=placebo)[0] == out   # deterministic


def test_v4_unknown_placebo():
    with pytest.raises(ValueError):
        perturb(load_package("small_cb_single"), "cb_v4", placebo="other")


@pytest.mark.parametrize("variant", ["cb_v0", "cb_v1", "cb_v2", "cb_v3"])
def test_cb_variants_need_cb(variant):
    with pytest.raises(PerturbationNotApplicable):
        perturb(load_package("mid"), variant)
