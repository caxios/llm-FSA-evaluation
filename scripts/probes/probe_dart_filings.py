"""Probe: OpenDART filing search (list.json).

Questions:
- Max date window without corp_code; page size limit; pagination fields.
- Filtering major-event reports (pblntf_ty=B) and exchange disclosures (pblntf_ty=I).
- Exact report_nm strings for CB issuance and conversion-price adjustment.
"""

from __future__ import annotations

from collections import Counter

from _common import dart_json, save_fixture, section


def search(**params) -> dict:
    data, latency = dart_json("list.json", page_count="100", **params)
    print(f"  params={params} -> status={data['status']} {data['message']} "
          f"total={data.get('total_count')} pages={data.get('total_page')} ({latency:.2f}s)")
    return data


def main() -> None:
    section("Window limits without corp_code")
    for bgn, end in [("20260101", "20260331"), ("20260101", "20260430"), ("20250101", "20251231")]:
        search(bgn_de=bgn, end_de=end, pblntf_ty="B")

    section("Page size limit")
    data, _ = dart_json("list.json", bgn_de="20260301", end_de="20260331", pblntf_ty="B",
                        page_count="200")
    print(f"  page_count=200 -> status={data['status']} rows={len(data.get('list', []))} "
          f"page_count echoed={data.get('page_count')}")

    section("Major-event reports, KOSDAQ, Mar 2026: report_nm frequencies")
    rows = []
    for page in range(1, 6):
        d = search(bgn_de="20260301", end_de="20260331", pblntf_ty="B", corp_cls="K",
                   page_no=str(page))
        rows += d.get("list", [])
        if page >= int(d.get("total_page", 1)):
            break
    names = Counter(r["report_nm"].strip() for r in rows)
    for name, cnt in names.most_common(25):
        print(f"  {cnt:4d}  {name}")
    cb_rows = [r for r in rows if "전환사채" in r["report_nm"]]
    print(f"  CB-related rows: {len(cb_rows)}")
    for r in cb_rows[:8]:
        print(f"   {r['rcept_dt']} {r['corp_name']} ({r['corp_code']}, {r['stock_code']}) "
              f"{r['report_nm'].strip()} rcept_no={r['rcept_no']}")
    save_fixture("dart", "list_major_events_kosdaq_202603.json",
                 {"status": "000", "list": rows[:60]})

    section("Exchange disclosures (pblntf_ty=I), KOSDAQ, Mar 2026: conversion-price adjustments")
    rows_i = []
    for page in range(1, 11):
        d = search(bgn_de="20260301", end_de="20260331", pblntf_ty="I", corp_cls="K",
                   page_no=str(page))
        rows_i += d.get("list", [])
        if page >= int(d.get("total_page", 1)):
            break
    adj = [r for r in rows_i if "전환가액" in r["report_nm"]]
    print(f"  exchange rows scanned={len(rows_i)}; conversion-price rows={len(adj)}")
    for name, cnt in Counter(r["report_nm"].strip() for r in adj).most_common(10):
        print(f"  {cnt:4d}  {name}")
    for r in adj[:5]:
        print(f"   {r['rcept_dt']} {r['corp_name']} ({r['corp_code']}) rcept_no={r['rcept_no']}")
    save_fixture("dart", "list_exchange_conv_price_202603.json",
                 {"status": "000", "list": adj[:30]})


if __name__ == "__main__":
    main()
