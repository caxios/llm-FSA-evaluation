"""Probe: daily prices from KRX Open API, pykrx (OHLCV still works without login), yfinance.

Questions:
- Adjusted vs unadjusted availability, history depth.
- Agreement between sources on 3 tickers (difference table).
"""

from __future__ import annotations

import pandas as pd
import requests
from _common import require_env, save_fixture, section

TICKERS = {"005930": ".KS", "014680": ".KS", "069540": ".KQ"}  # Samsung, Hansol Chemical, Bitnara
DATES = ["2023-04-03", "2024-08-30", "2026-04-01"]


def krx_close(ticker: str, day: str) -> float | None:
    resp = requests.get("https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd",
                        params={"basDd": day.replace("-", "")},
                        headers={"AUTH_KEY": require_env("KRX_OPENAPI_KEY")}, timeout=60)
    if resp.status_code != 200:
        return None
    for row in resp.json().get("OutBlock_1", []):
        if row["ISU_CD"] == ticker:
            return float(row["TDD_CLSPRC"])
    return None


def main() -> None:
    import yfinance as yf
    from pykrx import stock

    records = []
    for ticker, suffix in TICKERS.items():
        section(f"{ticker}{suffix}")
        yf_raw = yf.download(f"{ticker}{suffix}", start="2015-01-01", end="2026-10-01",
                             auto_adjust=False, progress=False)
        if isinstance(yf_raw.columns, pd.MultiIndex):
            yf_raw.columns = yf_raw.columns.get_level_values(0)
        print(f"  yfinance rows={len(yf_raw)} first={yf_raw.index.min()} last={yf_raw.index.max()}"
              f" columns={list(yf_raw.columns)}")
        try:
            pk_raw = stock.get_market_ohlcv("20150101", "20260930", ticker, adjusted=False)
            pk_adj = stock.get_market_ohlcv("20150101", "20260930", ticker, adjusted=True)
            print(f"  pykrx rows={len(pk_raw)} first={pk_raw.index.min()} "
                  f"last={pk_raw.index.max()}")
        except Exception as exc:  # noqa: BLE001
            pk_raw = pk_adj = None
            print(f"  pykrx FAILED {exc}")
        for day in DATES:
            ts = pd.Timestamp(day)
            rec = {"ticker": ticker, "date": day}
            if ts in yf_raw.index:
                rec["yf_close"] = float(yf_raw.loc[ts, "Close"])
                rec["yf_adj_close"] = float(yf_raw.loc[ts, "Adj Close"])
            if pk_raw is not None and ts in pk_raw.index:
                rec["pykrx_close"] = float(pk_raw.loc[ts, "종가"])
                rec["pykrx_adj_close"] = float(pk_adj.loc[ts, "종가"])
            if suffix == ".KS":
                rec["krx_openapi_close"] = krx_close(ticker, day)
            records.append(rec)
        if ticker == "005930":
            save_fixture("prices", "yfinance_005930_2026-03.csv",
                         yf_raw.loc["2026-03-01":"2026-03-31"].to_csv())

    section("Comparison")
    df = pd.DataFrame(records)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
