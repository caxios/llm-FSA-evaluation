"""Probe: KRX Open API and pykrx.

Questions:
- Historical listing and market cap as of arbitrary past dates?
- Does pykrx still work without a KRX login?
- Any source for administrative-issue / trading-halt flags as of a past date?
"""

from __future__ import annotations

import time

import requests
from _common import require_env, save_fixture, section

KRX_BASE = "https://data-dbg.krx.co.kr/svc/apis"
# Services under the KRX Open API (each needs separate approval on openapi.krx.co.kr)
SERVICES = {
    "kospi_daily": "sto/stk_bydd_trd",       # KOSPI daily trading by issue (incl. MKTCAP)
    "kosdaq_daily": "sto/ksq_bydd_trd",      # KOSDAQ daily trading by issue
    "kospi_base": "sto/stk_isu_base_info",   # KOSPI issue base info
    "kosdaq_base": "sto/ksq_isu_base_info",  # KOSDAQ issue base info
}
DATES = ["20260401", "20230403", "20240830"]


def krx_get(service: str, bas_dd: str) -> tuple[requests.Response, float]:
    t0 = time.perf_counter()
    resp = requests.get(f"{KRX_BASE}/{service}", params={"basDd": bas_dd},
                        headers={"AUTH_KEY": require_env("KRX_OPENAPI_KEY")}, timeout=60)
    return resp, time.perf_counter() - t0


def probe_openapi() -> None:
    for label, service in SERVICES.items():
        for bas_dd in DATES:
            resp, latency = krx_get(service, bas_dd)
            section(f"KRX Open API {label} basDd={bas_dd}: "
                    f"HTTP {resp.status_code} ({latency:.2f}s)")
            try:
                data = resp.json()
            except ValueError:
                print(f"  non-JSON: {resp.text[:200]!r}")
                continue
            rows = data.get("OutBlock_1")
            if rows is None:
                print(f"  body: {str(data)[:300]}")
                continue
            print(f"  rows={len(rows)} keys={list(rows[0].keys()) if rows else None}")
            if rows:
                print(f"  first={rows[0]}")
                if bas_dd == DATES[0]:
                    save_fixture("krx", f"openapi_{label}_{bas_dd}.json",
                                 {"OutBlock_1": rows[:30]})


def probe_pykrx() -> None:
    section("pykrx")
    try:
        from pykrx import stock
    except Exception as exc:  # noqa: BLE001
        print(f"  import failed: {exc}")
        return
    checks = {
        "get_market_ticker_list(20230403, KOSPI)":
            lambda: stock.get_market_ticker_list("20230403", market="KOSPI"),
        "get_market_cap(20230403, KOSPI)":
            lambda: stock.get_market_cap("20230403", market="KOSPI"),
        "get_market_ohlcv(20260301-20260331, 005930)":
            lambda: stock.get_market_ohlcv("20260301", "20260331", "005930"),
        "get_market_sector_classifications(20260401, KOSPI)":
            lambda: stock.get_market_sector_classifications("20260401", market="KOSPI"),
    }
    for name, fn in checks.items():
        try:
            out = fn()
            size = len(out)
            print(f"  {name}: OK, len={size}")
            if hasattr(out, "head"):
                print("   ", out.head(3).to_string().replace("\n", "\n    "))
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}: FAILED {type(exc).__name__}: {str(exc)[:200]}")


if __name__ == "__main__":
    probe_openapi()
    probe_pykrx()
