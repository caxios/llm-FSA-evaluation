"""P2: package schema, identity checks, builder (on recorded DART responses), renderer."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.data.account_map import load_account_map, normalize_label
from src.data.package_builder import build_package, build_shares
from src.data.package_schema import InputPackage
from src.data.render import render_company_block, render_user_prompt
from src.perturb.consistency import check_identities
from tests.fakes import FIXTURES, load_fixture

PKG_DIR = FIXTURES / "packages"
NAMES = ["large_pref", "mid", "small_cb_multi", "small_cb_single", "unmapped_heavy"]


def load_pkg(name: str) -> InputPackage:
    return InputPackage.from_json((PKG_DIR / f"{name}.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ schema & identities

@pytest.mark.parametrize("name", NAMES)
def test_fixture_round_trip_and_hash(name):
    pkg = load_pkg(name)
    again = InputPackage.from_json(pkg.to_json())
    assert again == pkg
    assert again.package_hash() == pkg.package_hash()


@pytest.mark.parametrize("name", NAMES)
def test_fixtures_pass_identities(name):
    assert check_identities(load_pkg(name)) == []


def test_identity_check_catches_broken_balance():
    pkg = load_pkg("large_pref")
    cash = pkg.bs.get("cash")
    cash.values[pkg.latest_year] += 1_000.0  # leaf change without updating subtotals...
    pkg.bs.get("total_assets").values[pkg.latest_year] += 1_000.0  # ...or the other side
    checks = {v.check for v in check_identities(pkg)}
    assert "bs_balance" in checks and "bs_assets_split" in checks


def test_identity_check_catches_cash_roll_break():
    pkg = load_pkg("mid")
    pkg.cf.get("ending_cash").values[pkg.latest_year] += 500.0
    checks = {v.check for v in check_identities(pkg)}
    assert "cf_cash_roll" in checks


def test_accessors():
    pkg = load_pkg("large_pref")
    assert pkg.bs.value("total_assets", 2025) == pytest.approx(566_942_110.0)
    with pytest.raises(KeyError):
        pkg.bs.get("does_not_exist")
    assert all(ln.category.startswith("debt:") for ln in pkg.bs.by_category("debt:"))


def test_small_fixture_has_consistent_cb_block():
    pkg = load_pkg("small_cb_multi")
    assert pkg.cb is not None and len(pkg.cb.instruments) >= 2
    for ins in pkg.cb.instruments:
        assert ins.convertible_shares == pytest.approx(ins.face_outstanding * 1e6
                                                       / ins.conversion_price)
        assert f"{round(ins.conversion_price):,}원" in pkg.cb.filing_text


# ------------------------------------------------------------------ builder


@pytest.fixture(scope="module")
def samsung_build():
    fs = pd.DataFrame(load_fixture("dart", "fs_samsung_2025_CFS.json")["list"])
    for col in ("thstrm_amount", "frmtrm_amount", "bfefrmtrm_amount"):
        fs[col] = pd.to_numeric(fs[col].str.replace(",", ""), errors="coerce")
    fs["ord"] = pd.to_numeric(fs["ord"])
    shares = pd.DataFrame(load_fixture("dart", "shares_samsung_2025.json")["list"])
    divs = pd.DataFrame(load_fixture("dart", "dividends_samsung_2025.json")["list"])
    company = load_fixture("dart", "company_samsung.json")
    return build_package(corp_code="00126380", fs=fs, fs_div="CFS", company=company,
                         shares=shares, dividends=divs, fiscal_year=2025,
                         eval_date=date(2026, 4, 1), market="KOSPI")


def test_builder_on_recorded_samsung(samsung_build):
    r = samsung_build
    assert r.status == "ok", r.issues
    pkg = r.package
    assert pkg.years == [2023, 2024, 2025]
    # KRW -> KRW million; per-share values stay in KRW
    assert pkg.bs.value("cash", 2025) == pytest.approx(57_856_378.0)
    assert pkg.per_share.eps[2025] == 6605
    assert pkg.per_share.dps_common == {2023: 1444.0, 2024: 1446.0, 2025: 1668.0}
    assert pkg.shares.common_outstanding == 5_827_808_935
    assert pkg.meta.industry_label == "국내 전자부품·컴퓨터·통신장비 제조 기업"
    # sections from the DART ord grouping
    assert pkg.bs.get("cash").parent == "current_assets"
    assert pkg.bs.get("retained_earnings").parent == "equity_owners"
    assert pkg.cf.get("dividends_paid").parent == "cff"
    # display order: revenue first in the income statement, totals after components
    assert pkg.is_.lines[0].canonical == "revenue"
    order = {ln.canonical: ln.order for ln in pkg.bs.lines if ln.canonical}
    assert order["current_assets"] < order["cash"] < order["total_assets"]
    assert pkg.meta.net_change_includes_fx is True


def test_builder_matches_fixture_package(samsung_build):
    built, fixture = samsung_build.package, load_pkg("large_pref")
    fixture.meta.firm_id, fixture.meta.group = built.meta.firm_id, built.meta.group
    assert built.bs == fixture.bs and built.is_ == fixture.is_ and built.cf == fixture.cf


@pytest.mark.parametrize("names,common,pref", [
    (["보통주", "우선주", "합계"], 100, 10),
    (["의결권 있는 주식", "의결권 없는 주식", "합계"], 100, 10),
    (["보통주(의결권있는주식)", "우선주(의결권없는주식)", "합계"], 100, 10),
    (["의결권이없는주식", "의결권이있는주식", "합계"], 10, 100),
    (["기명식보통주", "합계", "비고"], 100, 0),
])
def test_build_shares_name_variants(names, common, pref):
    rows = [{"se": n, "istc_totqy": str(v), "tesstk_co": "-", "stlm_dt": "2025-12-31"}
            for n, v in zip(names, [100, 10, 110], strict=False)]
    s = build_shares(pd.DataFrame(rows))
    assert (s.common_issued, s.preferred_issued) == (common, pref)


def test_normalize_label_strips_numbering():
    assert normalize_label("V. 영업이익(손실)") == "영업이익손실"
    assert normalize_label("ⅩIII. 당기총포괄손실") == "당기총포괄손실"
    assert normalize_label("1. 기본주당손실") == "기본주당손실"


def test_category_rules():
    amap = load_account_map()
    assert amap.category("-표준계정코드 미사용-", "전환사채", "non_current_liabilities") == \
        "debt:convertible"
    assert amap.category("ifrs-full_NoncurrentLeaseLiabilities", "리스부채",
                         "non_current_liabilities") == "debt:lease"
    assert amap.category("-표준계정코드 미사용-", "관계기업투자주식", "non_current_assets") == \
        "nonop:equity_method"
    # asset-side lease receivables are not debt
    assert amap.category("ifrs-full_NoncurrentFinanceLeaseReceivables", "장기금융리스채권",
                         "non_current_assets") is None


# ------------------------------------------------------------------ renderer


@pytest.mark.parametrize("name", NAMES)
def test_render_deterministic_and_golden(name):
    pkg = load_pkg(name)
    text = render_user_prompt(pkg, "C", include_cb=pkg.cb is not None)
    assert text == render_user_prompt(pkg, "C", include_cb=pkg.cb is not None)
    golden = FIXTURES / "rendered" / f"{name}.txt"
    if not golden.exists():  # first run writes the golden file; review it by hand
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(text, encoding="utf-8")
    assert text == golden.read_text(encoding="utf-8")


def test_company_block_structure_identical_across_conditions():
    pkg = load_pkg("mid")
    blocks = {c: render_company_block(pkg, c, fake_name="한빛정밀") for c in "ABDC"}
    keys = {c: [ln.split(":")[0] for ln in b.splitlines()] for c, b in blocks.items()}
    assert len({tuple(k) for k in keys.values()}) == 1
    assert pkg.meta.real_name not in blocks["A"] + blocks["B"] + blocks["D"]
    assert pkg.meta.real_name in blocks["C"]
    with pytest.raises(ValueError):
        render_company_block(pkg, "D")


def test_render_negative_numbers_and_cb_section():
    pkg = load_pkg("small_cb_single")
    text = render_user_prompt(pkg, "C", include_cb=True)
    assert "[추가 공시]\n[전환사채 미상환 현황" in text
    assert "없음" in render_user_prompt(pkg, "C", include_cb=False).split("[추가 공시]")[1]
    assert Path  # keep import used
