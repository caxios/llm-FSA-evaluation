"""Probe: share totals, dividends, company info, investments in other companies.

Questions:
- Issued / treasury / outstanding by share class (stockTotqySttus.json)
- DPS (alotMatter.json)
- induty_code (KSIC) and identifiers for redaction (company.json)
- Names of invested companies (otrCprInvstmntSttus.json), used for redaction in P4
"""

from __future__ import annotations

from _common import SAMSUNG, dart_json, save_fixture, section, trim

FIRMS = {"samsung": SAMSUNG, "bitnara": "00367482"}


def main() -> None:
    for label, corp in FIRMS.items():
        section(f"{label}: company.json")
        d, _ = dart_json("company.json", corp_code=corp)
        print({k: d.get(k) for k in ("corp_name", "corp_name_eng", "stock_name", "stock_code",
                                     "ceo_nm", "corp_cls", "induty_code", "adres", "hm_url",
                                     "est_dt", "acc_mt")})
        save_fixture("dart", f"company_{label}.json", d)

        section(f"{label}: stockTotqySttus.json FY2025")
        d, _ = dart_json("stockTotqySttus.json", corp_code=corp, bsns_year="2025",
                         reprt_code="11011")
        print(f"  status={d['status']} {d['message']}")
        for r in d.get("list", []):
            print(f"  {r.get('se')}: issued(istc_totqy)={r.get('istc_totqy')} "
                  f"treasury(tesstk_co)={r.get('tesstk_co')} outstanding(distb_stock_co)="
                  f"{r.get('distb_stock_co')}")
        if d.get("list"):
            print(f"  keys={list(d['list'][0].keys())}")
        save_fixture("dart", f"shares_{label}_2025.json", d)

        section(f"{label}: alotMatter.json FY2025")
        d, _ = dart_json("alotMatter.json", corp_code=corp, bsns_year="2025", reprt_code="11011")
        print(f"  status={d['status']} {d['message']}")
        for r in d.get("list", []):
            if "주당" in r.get("se", ""):
                print(f"  {r.get('se')} [{r.get('stock_knd')}]: {r.get('thstrm')} / "
                      f"{r.get('frmtrm')} / {r.get('lwfr')}")
        save_fixture("dart", f"dividends_{label}_2025.json", d)

        section(f"{label}: otrCprInvstmntSttus.json FY2025")
        d, _ = dart_json("otrCprInvstmntSttus.json", corp_code=corp, bsns_year="2025",
                         reprt_code="11011")
        rows = d.get("list", [])
        print(f"  status={d['status']} {d['message']} rows={len(rows)}")
        print(f"  sample names: {[r.get('inv_prm') for r in rows[:10]]}")
        if rows:
            print(f"  keys={list(rows[0].keys())}")
        save_fixture("dart", f"investments_{label}_2025.json", trim(d, n=30))


if __name__ == "__main__":
    main()
