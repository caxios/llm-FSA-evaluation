"""Probe: OpenDART full financial statements (fnlttSinglAcntAll.json).

Questions (P0 plan, Step 0.5):
- Does one annual report return three years (thstrm / frmtrm / bfefrmtrm) for BS, IS/CIS, CF?
- How consistently is account_id populated with IFRS/DART taxonomy IDs?
- Is basic EPS present as a line? Currency? Coverage for FY2022-FY2025?
"""

from __future__ import annotations

from collections import Counter

from _common import SAMSUNG, corp_codes, dart_json, save_fixture, section

YEARS = [2022, 2023, 2024, 2025]
UNMAPPED = "-표준계정코드 미사용-"


def find_corp(name: str) -> str:
    rows = [r for r in corp_codes() if r["corp_name"] == name and r["stock_code"]]
    return rows[0]["corp_code"]


def describe(rows: list[dict]) -> None:
    by_sj = Counter(r["sj_div"] for r in rows)
    print(f"  rows={len(rows)} by sj_div={dict(by_sj)}")
    for sj in sorted(by_sj):
        sub = [r for r in rows if r["sj_div"] == sj]
        cols = {c: sum(1 for r in sub if (r.get(c) or "").strip() not in ("", "-")) for c in
                ("thstrm_amount", "frmtrm_amount", "bfefrmtrm_amount")}
        unmapped = sum(1 for r in sub if r.get("account_id") == UNMAPPED)
        print(f"  {sj}: rows={len(sub)} non-empty columns={cols} unmapped_account_id={unmapped}")
    currencies = Counter(r.get("currency") for r in rows)
    print(f"  currency={dict(currencies)}")
    eps = [r for r in rows
           if "PerShare" in (r.get("account_id") or "") or "주당" in r["account_nm"]]
    for r in eps[:4]:
        print(f"  EPS-like: {r['sj_div']} {r['account_id']} {r['account_nm']} "
              f"{r['thstrm_amount']} / {r['frmtrm_amount']} / {r.get('bfefrmtrm_amount')}")
    keys = ["ifrs-full_CashAndCashEquivalents", "ifrs-full_Assets", "ifrs-full_Revenue",
            "dart_OperatingIncomeLoss", "ifrs-full_ProfitLossAttributableToOwnersOfParent",
            "ifrs-full_IncreaseDecreaseInCashAndCashEquivalents"]
    for k in keys:
        hit = [r for r in rows if r.get("account_id") == k]
        print(f"  {k}: {'found ' + hit[0]['sj_div'] if hit else 'MISSING'}")


def main() -> None:
    firms = {"samsung": SAMSUNG, "hansol_chemical": find_corp("한솔케미칼")}
    for label, corp in firms.items():
        for fs_div in ("CFS", "OFS"):
            for year in YEARS:
                data, latency = dart_json("fnlttSinglAcntAll.json", corp_code=corp,
                                          bsns_year=str(year), reprt_code="11011", fs_div=fs_div)
                section(f"{label} {fs_div} FY{year}: status={data['status']} "
                        f"{data['message']} ({latency:.2f}s)")
                if data["status"] != "000":
                    continue
                describe(data["list"])
                if year == 2024:
                    save_fixture("dart", f"fs_{label}_{year}_{fs_div}.json", data)
                if label == "samsung" and fs_div == "CFS" and year == 2024:
                    print("  sample row keys:", list(data["list"][0].keys()))


if __name__ == "__main__":
    main()
