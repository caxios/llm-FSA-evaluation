"""Probe: CB issuance decisions (cvbdIsDecsn.json) and outstanding-balance sources.

Questions:
- Exact fields: face amount, conversion price, refixing floor, conversion period, maturity,
  call/put terms.
- Is the outstanding CB balance available from any structured endpoint?
- With corp_code given, can list.json search a multi-year window (for refixing disclosures)?
"""

from __future__ import annotations

from _common import dart_get, dart_json, save_fixture, section

# KOSDAQ firms with CB issuance decisions in March 2026 (found by probe_dart_filings.py)
FIRMS = {"ks_industry": "00618410", "bitnara": "00367482"}


def main() -> None:
    for label, corp in FIRMS.items():
        section(f"cvbdIsDecsn {label} ({corp}), 2020-2026")
        data, latency = dart_json("cvbdIsDecsn.json", corp_code=corp, bgn_de="20200101",
                                  end_de="20261005")
        print(f"  status={data['status']} {data['message']} rows={len(data.get('list', []))} "
              f"({latency:.2f}s)")
        rows = data.get("list", [])
        if rows:
            print("  fields:")
            for k, v in rows[-1].items():
                print(f"    {k} = {v}")
            save_fixture("dart", f"cb_decision_{label}.json", data)

        section(f"list.json with corp_code {label}: multi-year window")
        d, _ = dart_json("list.json", corp_code=corp, bgn_de="20200101", end_de="20261005",
                         page_count="100")
        print(f"  status={d['status']} {d['message']} total={d.get('total_count')}")
        refix = [r for r in d.get("list", []) if "전환가액" in r["report_nm"]]
        print(f"  conversion-price filings on page 1: {len(refix)}")
        for r in refix[:5]:
            print(f"   {r['rcept_dt']} {r['report_nm'].strip()} rcept_no={r['rcept_no']}")

    section("Structured outstanding-balance candidates (periodic-report key info)")
    # Unredeemed balance endpoints listed in the OpenDART guide (periodic report key info).
    candidates = ["cprndNrdmpBlce.json", "srtpdPsndbtNrdmpBlce.json",
                  "entrprsBilScritsNrdmpBlce.json", "newCaplScritsNrdmpBlce.json",
                  "cndlCaplScritsNrdmpBlce.json"]
    corp = FIRMS["ks_industry"]
    for ep in candidates:
        resp, _ = dart_get(ep, corp_code=corp, bsns_year="2025", reprt_code="11011")
        try:
            d = resp.json()
            rows = d.get("list", [])
            print(f"  {ep}: HTTP {resp.status_code} status={d.get('status')} "
                  f"{d.get('message')} rows={len(rows)}")
            if rows:
                print(f"    keys={list(rows[0].keys())}")
                print(f"    first={rows[0]}")
                save_fixture("dart", f"nrdmp_{ep.replace('.json', '')}_ks_industry.json", d)
        except ValueError:
            print(f"  {ep}: HTTP {resp.status_code} (non-JSON)")


if __name__ == "__main__":
    main()
