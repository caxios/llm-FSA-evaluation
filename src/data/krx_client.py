"""KRX Open API client (daily trading data by issue).

pykrx is not used: it now requires a KRX login (docs/data_access_memo.md). Each market is a
separate KRX Open API service and needs its own approval; an unapproved service returns
HTTP 401, raised here as KrxNotApproved.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd
import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import PROJECT_ROOT, require_env
from src.data.parsing import parse_amount
from src.data.rate_limit import RateLimiter
from src.utils.io import write_raw

log = logging.getLogger(__name__)

BASE_URL = "https://data-dbg.krx.co.kr/svc/apis/sto"
RAW_ROOT = PROJECT_ROOT / "data" / "raw" / "krx"
Market = Literal["KOSPI", "KOSDAQ"]
SERVICES: dict[str, str] = {"KOSPI": "stk_bydd_trd", "KOSDAQ": "ksq_bydd_trd"}
COLUMNS = {
    "ISU_CD": "ticker", "ISU_NM": "name", "MKT_NM": "market", "SECT_TP_NM": "section",
    "TDD_CLSPRC": "close", "ACC_TRDVOL": "volume", "ACC_TRDVAL": "value",
    "MKTCAP": "market_cap", "LIST_SHRS": "shares_listed",
}
NUMERIC = ("close", "volume", "value", "market_cap", "shares_listed")


class KrxError(RuntimeError):
    pass


class KrxNotApproved(KrxError):
    """The service is not approved for this API key (HTTP 401)."""


class _Transient(Exception):
    pass


class KrxClient:
    def __init__(
        self,
        api_key: str | None = None,
        raw_root: Path = RAW_ROOT,
        limiter: RateLimiter | None = None,
        session: requests.Session | None = None,
        refresh: bool = False,
    ) -> None:
        self.api_key = api_key or require_env("KRX_OPENAPI_KEY")
        self.raw_root = raw_root
        self.limiter = limiter or RateLimiter(per_second=3)
        self.session = session or requests.Session()
        self.refresh = refresh

    @retry(retry=retry_if_exception_type(_Transient), wait=wait_exponential(min=1, max=30),
           stop=stop_after_attempt(5), reraise=True)
    def _request(self, service: str, bas_dd: str) -> requests.Response:
        self.limiter.acquire()
        try:
            resp = self.session.get(f"{BASE_URL}/{service}", params={"basDd": bas_dd},
                                    headers={"AUTH_KEY": self.api_key}, timeout=60)
        except requests.RequestException as exc:
            raise _Transient(str(exc)) from exc
        if resp.status_code >= 500:
            raise _Transient(f"HTTP {resp.status_code}")
        return resp

    def daily(self, on: date, market: Market) -> pd.DataFrame:
        """All issues traded in `market` on `on`. Empty DataFrame on non-trading days."""
        service = SERVICES[market]
        bas_dd = on.strftime("%Y%m%d")
        cache = self.raw_root / "daily" / f"{market}_{bas_dd}.json"
        if cache.exists() and not self.refresh:
            body = json.loads(cache.read_text(encoding="utf-8"))
        else:
            resp = self._request(service, bas_dd)
            if resp.status_code == 401:
                raise KrxNotApproved(f"KRX service '{service}' is not approved for this key")
            if resp.status_code != 200:
                raise KrxError(f"{service} {bas_dd}: HTTP {resp.status_code}")
            body = resp.json()
            if "OutBlock_1" not in body:
                raise KrxError(f"{service} {bas_dd}: unexpected body {str(body)[:200]}")
            write_raw(cache, body, url=f"{BASE_URL}/{service}", params={"basDd": bas_dd},
                      status=resp.status_code)
        df = pd.DataFrame(body["OutBlock_1"])
        if df.empty:
            return pd.DataFrame(columns=list(COLUMNS.values()) + ["date"])
        df = df.rename(columns=COLUMNS)[list(COLUMNS.values())]
        for col in NUMERIC:
            df[col] = df[col].map(parse_amount)
        df["date"] = on
        return df

    def daily_on_or_before(self, on: date, market: Market, max_back: int = 10) -> pd.DataFrame:
        """Data for the last trading day on or before `on` (looks back up to `max_back` days)."""
        for back in range(max_back + 1):
            df = self.daily(on - timedelta(days=back), market)
            if not df.empty:
                return df
        raise KrxError(f"no trading day within {max_back} days before {on} ({market})")
