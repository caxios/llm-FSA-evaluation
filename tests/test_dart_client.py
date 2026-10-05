from datetime import date

import pytest

from src.data.dart_client import DartAuthError, DartClient, DartError, split_windows
from src.data.rate_limit import QuotaExhausted, RateLimiter
from tests.fakes import FakeResponse, FakeSession, load_fixture


def make_client(tmp_path, routes, refresh=False):
    session = FakeSession(routes)
    client = DartClient(api_key="TESTKEY", raw_root=tmp_path / "dart",
                        limiter=RateLimiter(per_second=1e6), session=session, refresh=refresh)
    return client, session


def test_split_windows_three_months():
    w = split_windows(date(2020, 10, 5), date(2021, 6, 30))
    assert w[0] == (date(2020, 10, 5), date(2021, 1, 4))
    assert w[-1][1] == date(2021, 6, 30)
    assert all(b < a2 for (_, b), (a2, _) in zip(w, w[1:], strict=False))
    assert split_windows(date(2026, 1, 1), date(2026, 3, 31)) == [(date(2026, 1, 1),
                                                                    date(2026, 3, 31))]


def test_financial_statements_parse_and_cache(tmp_path):
    fixture = load_fixture("dart", "fs_samsung_2024_CFS.json")
    client, session = make_client(tmp_path, {"fnlttSinglAcntAll.json":
                                             lambda p: FakeResponse(body=fixture)})
    df = client.financial_statements("00126380", 2024)
    assert set(df["sj_div"]) >= {"BS", "IS", "CF"}
    cash = df[df["account_id"] == "ifrs-full_CashAndCashEquivalents"].iloc[0]
    assert cash["thstrm_amount"] == pytest.approx(53_705_579e6, rel=1e-6)
    assert df["ord"].dtype.kind in "if"
    # second call is served from the raw cache
    client.financial_statements("00126380", 2024)
    assert len(session.calls) == 1
    # the API key is never written to disk
    meta = next((tmp_path / "dart" / "fs").rglob("*.meta.json")).read_text(encoding="utf-8")
    assert "TESTKEY" not in meta


def test_no_data_is_cached_and_empty(tmp_path):
    client, session = make_client(tmp_path, {"fnlttSinglAcntAll.json": lambda p: FakeResponse(
        body={"status": "013", "message": "조회된 데이타가 없습니다."})})
    assert client.financial_statements("x", 2025).empty
    assert client.financial_statements("x", 2025).empty
    assert len(session.calls) == 1


@pytest.mark.parametrize("status,exc", [("020", QuotaExhausted), ("010", DartAuthError),
                                        ("100", DartError)])
def test_status_errors(tmp_path, status, exc):
    client, _ = make_client(tmp_path, {"company.json": lambda p: FakeResponse(
        body={"status": status, "message": "err"})})
    with pytest.raises(exc):
        client.company("00126380")


def test_search_filings_paginates_and_splits(tmp_path):
    def handler(params):
        page = int(params["page_no"])
        rows = [{"rcept_no": f"{params['bgn_de']}{page:06d}", "corp_code": "1",
                 "report_nm": "x", "rcept_dt": params["bgn_de"]}]
        return FakeResponse(body={"status": "000", "total_page": 2, "list": rows})

    client, session = make_client(tmp_path, {"list.json": handler})
    df = client.search_filings(date(2026, 1, 1), date(2026, 6, 30), pblntf_ty="B")
    assert len(df) == 4  # 2 windows x 2 pages
    windows = {p["bgn_de"] for _, p in session.calls}
    assert windows == {"20260101", "20260401"}


def test_search_filings_with_corp_code_single_window(tmp_path):
    client, session = make_client(tmp_path, {"list.json": lambda p: FakeResponse(
        body={"status": "000", "total_page": 1, "list": [{"rcept_no": "1"}]})})
    client.search_filings(date(2020, 1, 1), date(2026, 10, 5), corp_code="00367482")
    assert len(session.calls) == 1


def test_document_rejects_error_body(tmp_path):
    client, _ = make_client(tmp_path, {"document.xml": lambda p: FakeResponse(
        body={"status": "014", "message": "파일이 존재하지 않습니다."})})
    with pytest.raises(DartError):
        client.document("20260101000001")
