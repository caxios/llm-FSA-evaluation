"""Point-in-time prices (decision D0.3).

Primary: KRX Open API official close (unadjusted). Fallback: yfinance `Close` (split-adjusted,
not dividend-adjusted), used when the KRX service for the market is not approved or the
ticker is missing. yfinance `Adj Close` is never used. The source is returned with each price.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.config import PROJECT_ROOT
from src.data.krx_client import KrxClient, KrxError, KrxNotApproved, Market
from src.utils.io import atomic_write

log = logging.getLogger(__name__)

RAW_ROOT = PROJECT_ROOT / "data" / "raw" / "prices"
YF_SUFFIX = {"KOSPI": ".KS", "KOSDAQ": ".KQ"}
HISTORY_START = date(2015, 1, 1)


@dataclass(frozen=True)
class PricePoint:
    ticker: str
    requested: date
    date: date
    close: float
    source: str  # "krx" | "yfinance"


class PriceNotFound(LookupError):
    pass


def _yf_download(symbol: str, start: date, end: date) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(symbol, start=start.isoformat(), end=end.isoformat(), auto_adjust=False,
                     progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


class PriceClient:
    def __init__(
        self,
        krx: KrxClient | None,
        raw_root: Path = RAW_ROOT,
        yf_download: Callable[[str, date, date], pd.DataFrame] = _yf_download,
        history_end: date | None = None,
        max_back: int = 10,
    ) -> None:
        self.krx = krx
        self.raw_root = raw_root
        self.yf_download = yf_download
        self.history_end = history_end or date.today()
        self.max_back = max_back
        self._krx_unavailable: set[str] = set()

    # -------------------------------------------------------------- yfinance fallback

    def yf_history(self, ticker: str, market: Market) -> pd.DataFrame:
        """Daily yfinance history (columns: date, close, volume), cached as raw CSV."""
        cache = self.raw_root / "yfinance" / f"{ticker}{YF_SUFFIX[market]}.csv"
        if not cache.exists():
            df = self.yf_download(f"{ticker}{YF_SUFFIX[market]}", HISTORY_START,
                                  self.history_end + timedelta(days=1))
            atomic_write(cache, df.to_csv().encode("utf-8"))
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        if df.empty:
            return pd.DataFrame(columns=["date", "close", "volume"])
        out = pd.DataFrame({"date": df.index.date, "close": df["Close"].astype(float),
                            "volume": df["Volume"].astype(float)})
        return out.dropna(subset=["close"]).reset_index(drop=True)

    def _from_yf(self, ticker: str, market: Market, on: date) -> PricePoint:
        hist = self.yf_history(ticker, market)
        window = hist[(hist["date"] <= on) & (hist["date"] >= on - timedelta(days=self.max_back))]
        if window.empty:
            raise PriceNotFound(f"{ticker}: no yfinance price within {self.max_back} days of {on}")
        row = window.iloc[-1]
        return PricePoint(ticker, on, row["date"], float(row["close"]), "yfinance")

    # -------------------------------------------------------------- public

    def price_on(self, ticker: str, market: Market, on: date) -> PricePoint:
        """Close on the last trading day on or before `on`."""
        if self.krx is not None and market not in self._krx_unavailable:
            try:
                df = self.krx.daily_on_or_before(on, market, self.max_back)
                hit = df[df["ticker"] == ticker]
                if not hit.empty:
                    row = hit.iloc[0]
                    return PricePoint(ticker, on, row["date"], float(row["close"]), "krx")
                log.info("%s not in KRX %s data for %s; trying yfinance", ticker, market, on)
            except KrxNotApproved:
                log.warning("KRX %s service not approved; using yfinance for %s", market, market)
                self._krx_unavailable.add(market)
            except KrxError as exc:
                log.warning("KRX lookup failed for %s on %s: %s", ticker, on, exc)
        return self._from_yf(ticker, market, on)
