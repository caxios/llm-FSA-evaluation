"""OpenDART client: cached, rate-limited, idempotent.

Every response is stored under data/raw/dart/ exactly as received (with a .meta.json sidecar).
If the raw file exists, it is parsed instead of calling the API, unless `refresh=True`.
Endpoint details were verified by the P0 probes (docs/data_access_memo.md).
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from lxml import etree
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import PROJECT_ROOT, require_env
from src.data.parsing import parse_amount
from src.data.rate_limit import QuotaExhausted, RateLimiter
from src.utils.io import write_raw

log = logging.getLogger(__name__)

BASE_URL = "https://opendart.fss.or.kr/api"
RAW_ROOT = PROJECT_ROOT / "data" / "raw" / "dart"
DAILY_QUOTA = 20_000
NO_DATA = "013"
AUTH_CODES = {"010", "011", "012", "901"}
QUOTA_CODE = "020"
AMOUNT_COLUMNS = ("thstrm_amount", "frmtrm_amount", "bfefrmtrm_amount")
ANNUAL = "11011"


class DartError(RuntimeError):
    pass


class DartAuthError(DartError):
    pass


class _Transient(Exception):
    """Network error or HTTP 5xx; retried."""


def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    days_in_month = [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28,
                     31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(d.day, days_in_month))


def split_windows(bgn: date, end: date, months: int = 3) -> list[tuple[date, date]]:
    """Split [bgn, end] into consecutive windows of at most `months` months (inclusive)."""
    windows, start = [], bgn
    while start <= end:
        stop = min(add_months(start, months) - timedelta(days=1), end)
        windows.append((start, stop))
        start = stop + timedelta(days=1)
    return windows


def _fmt(d: date) -> str:
    return d.strftime("%Y%m%d")


class DartClient:
    def __init__(
        self,
        api_key: str | None = None,
        raw_root: Path = RAW_ROOT,
        limiter: RateLimiter | None = None,
        session: requests.Session | None = None,
        refresh: bool = False,
    ) -> None:
        self.api_key = api_key or require_env("OPENDARTAPI_KEY")
        self.raw_root = raw_root
        self.limiter = limiter or RateLimiter(
            per_second=5, daily_quota=DAILY_QUOTA, state_path=raw_root / "_quota.json"
        )
        self.session = session or requests.Session()
        self.refresh = refresh

    # ------------------------------------------------------------------ transport

    @retry(
        retry=retry_if_exception_type(_Transient),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _request(self, endpoint: str, params: dict[str, Any]) -> requests.Response:
        self.limiter.acquire()
        try:
            resp = self.session.get(
                f"{BASE_URL}/{endpoint}", params={"crtfc_key": self.api_key, **params}, timeout=60
            )
        except requests.RequestException as exc:
            raise _Transient(str(exc)) from exc
        if resp.status_code >= 500:
            raise _Transient(f"HTTP {resp.status_code}")
        if resp.status_code != 200:
            raise DartError(f"{endpoint}: HTTP {resp.status_code}")
        return resp

    def _get_json(self, endpoint: str, params: dict[str, Any], cache: Path) -> dict:
        """Return the JSON body for `endpoint`, from the raw cache when available."""
        if cache.exists() and not self.refresh:
            return json.loads(cache.read_text(encoding="utf-8"))
        resp = self._request(endpoint, params)
        body = resp.json()
        status = body.get("status")
        if status == QUOTA_CODE:
            raise QuotaExhausted(f"OpenDART quota exhausted: {body.get('message')}")
        if status in AUTH_CODES:
            raise DartAuthError(f"{endpoint}: {status} {body.get('message')}")
        if status not in ("000", NO_DATA):
            raise DartError(f"{endpoint} {params}: {status} {body.get('message')}")
        # '013' (no data) is cached too, so it is not fetched again.
        write_raw(cache, body, url=f"{BASE_URL}/{endpoint}", params=params, status=status)
        return body

    def _get_bytes(self, endpoint: str, params: dict[str, Any], cache: Path) -> bytes:
        if cache.exists() and not self.refresh:
            return cache.read_bytes()
        resp = self._request(endpoint, params)
        content = resp.content
        if content[:2] != b"PK":  # error responses come back as JSON/XML instead of a ZIP
            try:
                body = resp.json()
            except ValueError:
                body = {"message": resp.text[:300]}
            if body.get("status") == QUOTA_CODE:
                raise QuotaExhausted(body.get("message"))
            raise DartError(f"{endpoint} {params}: {body.get('status')} {body.get('message')}")
        write_raw(cache, content, url=f"{BASE_URL}/{endpoint}", params=params, status="000")
        return content

    @staticmethod
    def _rows(body: dict) -> pd.DataFrame:
        return pd.DataFrame(body.get("list", []))

    # ------------------------------------------------------------------ endpoints

    def corp_codes(self) -> pd.DataFrame:
        """All companies registered with DART: corp_code, corp_name, corp_eng_name,
        stock_code, modify_date."""
        cache = self.raw_root / "corpCode" / "corpCode.zip"
        content = self._get_bytes("corpCode.xml", {}, cache)
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            xml = zf.read(zf.namelist()[0])
        root = etree.fromstring(xml)
        rows = [{c.tag: (c.text or "").strip() for c in el} for el in root.iter("list")]
        return pd.DataFrame(rows)

    def company(self, corp_code: str) -> dict:
        body = self._get_json("company.json", {"corp_code": corp_code},
                              self.raw_root / "company" / f"{corp_code}.json")
        return body if body.get("status") == "000" else {}

    def financial_statements(
        self, corp_code: str, bsns_year: int, reprt_code: str = ANNUAL, fs_div: str = "CFS"
    ) -> pd.DataFrame:
        """Full statements; amount columns parsed to float (KRW). Empty if no data."""
        params = {"corp_code": corp_code, "bsns_year": str(bsns_year),
                  "reprt_code": reprt_code, "fs_div": fs_div}
        cache = self.raw_root / "fs" / corp_code / f"{bsns_year}_{reprt_code}_{fs_div}.json"
        df = self._rows(self._get_json("fnlttSinglAcntAll.json", params, cache))
        for col in AMOUNT_COLUMNS:
            if col in df:
                df[col] = df[col].map(parse_amount)
        if "ord" in df:
            df["ord"] = pd.to_numeric(df["ord"], errors="coerce")
        return df

    def search_filings(
        self,
        bgn: date,
        end: date,
        corp_code: str | None = None,
        pblntf_ty: str | None = None,
        corp_cls: str | None = None,
    ) -> pd.DataFrame:
        """Filing list over [bgn, end]. Without corp_code, DART allows ≤ 3-month windows, so
        the range is split; pages (max 100 rows) are followed."""
        windows = [(bgn, end)] if corp_code else split_windows(bgn, end, 3)
        frames = []
        for w_bgn, w_end in windows:
            page = 1
            while True:
                params = {"bgn_de": _fmt(w_bgn), "end_de": _fmt(w_end), "page_no": str(page),
                          "page_count": "100"}
                for key, val in (("corp_code", corp_code), ("pblntf_ty", pblntf_ty),
                                 ("corp_cls", corp_cls)):
                    if val:
                        params[key] = val
                tag = "_".join(str(params.get(k, "all")) for k in
                               ("corp_code", "pblntf_ty", "corp_cls"))
                cache = (self.raw_root / "filings" / tag /
                         f"{params['bgn_de']}_{params['end_de']}_p{page}.json")
                body = self._get_json("list.json", params, cache)
                frames.append(self._rows(body))
                if page >= int(body.get("total_page") or 1):
                    break
                page += 1
        frames = [f for f in frames if not f.empty]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def cb_issuance_decisions(self, corp_code: str, bgn: date, end: date) -> pd.DataFrame:
        params = {"corp_code": corp_code, "bgn_de": _fmt(bgn), "end_de": _fmt(end)}
        cache = self.raw_root / "cb_decision" / f"{corp_code}_{_fmt(bgn)}_{_fmt(end)}.json"
        return self._rows(self._get_json("cvbdIsDecsn.json", params, cache))

    def _periodic(self, endpoint: str, folder: str, corp_code: str, bsns_year: int,
                  reprt_code: str) -> pd.DataFrame:
        params = {"corp_code": corp_code, "bsns_year": str(bsns_year), "reprt_code": reprt_code}
        cache = self.raw_root / folder / corp_code / f"{bsns_year}_{reprt_code}.json"
        return self._rows(self._get_json(endpoint, params, cache))

    def share_totals(self, corp_code: str, bsns_year: int, reprt_code: str = ANNUAL):
        return self._periodic("stockTotqySttus.json", "shares", corp_code, bsns_year, reprt_code)

    def dividends(self, corp_code: str, bsns_year: int, reprt_code: str = ANNUAL):
        return self._periodic("alotMatter.json", "dividends", corp_code, bsns_year, reprt_code)

    def investments(self, corp_code: str, bsns_year: int, reprt_code: str = ANNUAL):
        return self._periodic("otrCprInvstmntSttus.json", "investments", corp_code, bsns_year,
                              reprt_code)

    def document(self, rcept_no: str) -> Path:
        """Download a filing's original documents; returns the directory of extracted files."""
        doc_dir = self.raw_root / "documents" / rcept_no
        content = self._get_bytes("document.xml", {"rcept_no": rcept_no},
                                  doc_dir / f"{rcept_no}.zip")
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                target = doc_dir / name
                if not target.exists():
                    target.write_bytes(zf.read(name))
        return doc_dir
