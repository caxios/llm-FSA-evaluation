"""P4: conditions A/B/D/C built from one package."""

import pytest

from src.conditions.build import CONDITIONS, make_condition
from src.conditions.identifiers import FirmIdentifiers, name_variants
from src.conditions.redactor import find_identifiers
from src.data.render import render_user_prompt
from tests.fakes import PACKAGE_NAMES, load_package


def ids_for(pkg, extra_investees=()):
    names = name_variants(pkg.meta.real_name)
    return FirmIdentifiers(firm_id=pkg.meta.firm_id, names=names, ticker=pkg.meta.ticker,
                           investees=list(extra_investees))


def planted(pkg, label="에이비씨전자 지분법투자"):
    """A package with an investee name planted in a line label and its notes item."""
    p = pkg.model_copy(deep=True)
    line = p.bs.by_category("nonop:")[0]
    line.label = label
    for it in p.notes.non_operating_assets:
        if it.line_id == line.line_id:
            it.label = label
    return p, line.line_id


@pytest.mark.parametrize("name", PACKAGE_NAMES)
def test_no_identifier_in_abd_and_structure_identical(name):
    pkg, line_id = planted(load_package(name), f"{load_package(name).meta.real_name} 투자")
    ids = ids_for(pkg, ["에이비씨전자"])
    renders = {}
    for cond in CONDITIONS:
        cp = make_condition(pkg, cond, ids, fake_name="윤슬소재")
        renders[cond] = cp.render(include_cb=True)
        if cond != "C":
            assert find_identifiers(renders[cond], ids) == [], cond
            assert any(r.field == f"BS.{line_id}" for r in cp.redaction_log)
    lines = {c: r.splitlines() for c, r in renders.items()}
    assert len({len(v) for v in lines.values()}) == 1          # same line count
    for c in ("A", "B", "D"):                                  # differ only in company block
        diff = [i for i, (x, y) in enumerate(zip(lines["A"], lines[c], strict=True)) if x != y]
        assert diff in ([], [1], [2], [1, 2])
    assert pkg.meta.real_name in renders["C"]


def test_c_equals_unredacted_render():
    pkg, _ = planted(load_package("mid"))
    cp = make_condition(pkg, "C", ids_for(pkg, ["에이비씨전자"]))
    assert cp.redaction_log == []
    assert cp.render() == render_user_prompt(pkg, "C")


def test_company_blocks_and_industry_override():
    pkg = load_package("large_pref")
    ids = ids_for(pkg)
    blocks = {c: make_condition(pkg, c, ids, fake_name="마루테크",
                                industry_label="국내 제조 기업").company_block
              for c in CONDITIONS}
    assert blocks["A"] == "기업명: (비공개)\n업종: (비공개)"
    assert blocks["B"] == "기업명: (비공개)\n업종: 국내 제조 기업"
    assert blocks["D"] == "기업명: 마루테크\n업종: 국내 제조 기업"
    assert blocks["C"] == f"기업명: {pkg.meta.real_name}\n업종: 국내 제조 기업"
    with pytest.raises(ValueError):
        make_condition(pkg, "D", ids)
    with pytest.raises(ValueError):
        make_condition(pkg, "E", ids)  # type: ignore[arg-type]


def test_input_package_untouched_and_cb_text_redacted():
    pkg = load_package("small_cb_single")
    h = pkg.package_hash()
    ids = FirmIdentifiers(firm_id="S001", names=["하이퍼코퍼레이션"], investees=["무보증"])
    cp = make_condition(pkg, "A", ids)
    assert pkg.package_hash() == h
    assert "무보증" not in cp.package.cb.filing_text and "무보증" in pkg.cb.filing_text
