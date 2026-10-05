from datetime import date
from pathlib import Path

import pytest

from src.data.cb_collect import collect_cb_terms, find_cb_issuers
from src.data.cb_parser import parse_refixing, parse_unredeemed_cb_table
from src.data.dart_client import DartClient
from src.data.rate_limit import RateLimiter
from tests.fakes import FIXTURES, FakeResponse, FakeSession, load_fixture

DART = FIXTURES / "dart"


def wrap(table_html: str) -> str:
    # the saved fixture is the bare table; the unit caption precedes it in real documents
    return f"<P>(단위 : 원, 주)</P>{table_html}"


def test_unredeemed_table_bitnara():
    df, info = parse_unredeemed_cb_table(wrap((DART / "doc_cb_table_bitnara.html")
                                              .read_text(encoding="utf-8")))
    assert info["found"] and info["unit"].startswith("(단위")
    assert list(df["series"]) == ["9", "11", "13", "14"]
    s11 = df[df["series"] == "11"].iloc[0]
    assert s11["conv_price"] == 634
    assert s11["face_outstanding"] == 479_666_647
    assert s11["convertible_shares"] == 756_572
    assert s11["maturity"] == date(2026, 5, 30)
    assert df["face_outstanding"].sum() == pytest.approx(15_479_666_870)


def test_unredeemed_table_ks_industry():
    df, _ = parse_unredeemed_cb_table(wrap((DART / "doc_cb_table_ks_industry.html")
                                           .read_text(encoding="utf-8")))
    assert len(df) == 1
    row = df.iloc[0]
    assert (row["series"], row["conv_price"], row["convertible_shares"]) == ("15", 2110,
                                                                            2_891_398)
    assert row["issue_date"] == date(2024, 11, 27)


def test_unredeemed_table_absent():
    df, info = parse_unredeemed_cb_table("<table><tr><td>무관한 표</td></tr></table>")
    assert not info["found"] and df.empty and info["status"] == "not_found"


def test_unredeemed_table_none_declared():
    doc = "<P>(3) 미상환 전환사채 발행현황</P><P>해당사항 없습니다.</P>"
    df, info = parse_unredeemed_cb_table(doc)
    assert df.empty and info["status"] == "none_declared"


def test_unredeemed_table_thousands_unit():
    html = (DART / "doc_cb_table_ks_industry.html").read_text(encoding="utf-8")
    df, _ = parse_unredeemed_cb_table(f"<P>(단위 : 천원, 주)</P>{html}")
    assert df.iloc[0]["face_outstanding"] == pytest.approx(6_100_000_000e3)


@pytest.mark.parametrize("name,series,before,after,eff", [
    ("doc_refix_20260330902339.xml", "10", 1495, 1355, date(2026, 3, 30)),
    ("doc_refix_20260826900489.xml", "17", 5769, 4039, date(2026, 8, 26)),
])
def test_parse_refixing(name, series, before, after, eff):
    df = parse_refixing(Path(DART / name))
    assert len(df) == 1
    row = df.iloc[0]
    assert (row["series"], row["price_before"], row["price_after"], row["effective_date"]) == (
        series, before, after, eff)


def dart_with(tmp_path, routes):
    return DartClient(api_key="K", raw_root=tmp_path / "dart", limiter=RateLimiter(1e6),
                      session=FakeSession(routes))


def test_collect_cb_terms_dedupes_and_parses(tmp_path):
    fixture = load_fixture("dart", "cb_decision_ks_industry.json")
    dart = dart_with(tmp_path, {"cvbdIsDecsn.json": lambda p: FakeResponse(body=fixture)})
    df = collect_cb_terms(dart, "00618410", date(2020, 1, 1), date(2026, 10, 5))
    assert df["series"].is_unique
    s19 = df[df["series"] == "19"].iloc[0]
    assert s19["face"] == 7_000_000_000 and s19["conv_price"] == 1623
    assert s19["refix_floor"] == 1137 and s19["maturity"] == date(2029, 12, 24)


def test_find_cb_issuers_filters_titles(tmp_path):
    fixture = load_fixture("dart", "list_major_events_kosdaq_202603.json")
    fixture = {**fixture, "total_page": 1}
    dart = dart_with(tmp_path, {"list.json": lambda p: FakeResponse(body=fixture)})
    out = find_cb_issuers(dart, date(2026, 3, 1), date(2026, 3, 31))
    expected = {r["corp_code"] for r in fixture["list"]
                if "전환사채권발행결정" in r["report_nm"].replace(" ", "")}
    assert set(out["corp_code"]) == expected
    assert "00618410" in expected  # KS인더스트리 issued a CB in March 2026
