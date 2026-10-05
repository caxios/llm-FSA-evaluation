from datetime import date

import pandas as pd
import pytest

from src.data.krx_client import KrxClient, KrxNotApproved
from src.data.price_client import PriceClient, PriceNotFound
from src.data.rate_limit import RateLimiter
from tests.fakes import FakeResponse, FakeSession, load_fixture

KOSPI = load_fixture("krx", "openapi_kospi_daily_20260401.json")


def krx_client(tmp_path, routes):
    session = FakeSession(routes)
    return KrxClient(api_key="K", raw_root=tmp_path / "krx", limiter=RateLimiter(1e6),
                     session=session), session


def test_daily_parses_numeric_columns_and_caches(tmp_path):
    client, session = krx_client(tmp_path, {"stk_bydd_trd": lambda p: FakeResponse(body=KOSPI)})
    df = client.daily(date(2026, 4, 1), "KOSPI")
    first = df.iloc[0]
    assert first["ticker"] == "095570"
    assert first["close"] == 5170 and first["market_cap"] == 233956764030
    client.daily(date(2026, 4, 1), "KOSPI")
    assert len(session.calls) == 1


def test_not_approved_raises(tmp_path):
    client, _ = krx_client(tmp_path, {"ksq_bydd_trd": lambda p: FakeResponse(
        status_code=401, body={"respMsg": "Unauthorized API Call", "respCode": "401"})})
    with pytest.raises(KrxNotApproved):
        client.daily(date(2026, 4, 1), "KOSDAQ")


def test_daily_on_or_before_skips_holidays(tmp_path):
    def handler(p):
        return FakeResponse(body=KOSPI if p["basDd"] == "20260401" else {"OutBlock_1": []})

    client, session = krx_client(tmp_path, {"stk_bydd_trd": handler})
    df = client.daily_on_or_before(date(2026, 4, 4), "KOSPI")  # Saturday -> Wed 1 Apr
    assert (df["date"] == date(2026, 4, 1)).all()
    assert [p["basDd"] for _, p in session.calls] == ["20260404", "20260403", "20260402",
                                                       "20260401"]


def fake_yf(symbol, start, end):
    idx = pd.to_datetime(["2026-03-30", "2026-03-31", "2026-04-01"])
    return pd.DataFrame({"Close": [3000.0, 3050.0, 3115.0], "Adj Close": [1.0, 1.0, 1.0],
                         "Volume": [10, 20, 30]}, index=idx)


def test_price_on_uses_krx_first(tmp_path):
    krx, _ = krx_client(tmp_path, {"stk_bydd_trd": lambda p: FakeResponse(body=KOSPI)})
    prices = PriceClient(krx, raw_root=tmp_path / "prices", yf_download=fake_yf)
    pp = prices.price_on("095570", "KOSPI", date(2026, 4, 1))
    assert (pp.close, pp.source) == (5170.0, "krx")


def test_price_on_falls_back_to_yfinance_close_not_adjusted(tmp_path):
    krx, session = krx_client(tmp_path, {"ksq_bydd_trd": lambda p: FakeResponse(
        status_code=401, body={"respCode": "401"})})
    prices = PriceClient(krx, raw_root=tmp_path / "prices", yf_download=fake_yf)
    pp = prices.price_on("069540", "KOSDAQ", date(2026, 4, 2))
    assert (pp.close, pp.date, pp.source) == (3115.0, date(2026, 4, 1), "yfinance")
    prices.price_on("069540", "KOSDAQ", date(2026, 3, 31))
    assert len(session.calls) == 1  # KRX not retried after "not approved"


def test_price_not_found(tmp_path):
    prices = PriceClient(None, raw_root=tmp_path / "prices", yf_download=fake_yf)
    with pytest.raises(PriceNotFound):
        prices.price_on("069540", "KOSDAQ", date(2025, 1, 1))
