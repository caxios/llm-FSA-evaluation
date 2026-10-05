"""Probe: original filing documents (document.xml).

Questions:
- Archive format and encoding.
- Can the "unredeemed convertible bond" table in the annual report be located by header
  keywords? Which headers does it use?
"""

from __future__ import annotations

import io
import re
import zipfile

from _common import RAW, dart_get, dart_json, save_fixture, section
from bs4 import BeautifulSoup

FIRMS = {"bitnara": "00367482", "ks_industry": "00618410"}
KEYWORDS = ("미상환", "전환사채")


def annual_rcept_no(corp: str, year: int) -> str:
    data, _ = dart_json("fnlttSinglAcntAll.json", corp_code=corp, bsns_year=str(year),
                        reprt_code="11011", fs_div="CFS")
    if data["status"] != "000":
        data, _ = dart_json("fnlttSinglAcntAll.json", corp_code=corp, bsns_year=str(year),
                            reprt_code="11011", fs_div="OFS")
    return data["list"][0]["rcept_no"]


def table_text(tbl) -> list[list[str]]:
    rows = []
    for tr in tbl.find_all("tr"):
        # DART XML uses TE/TU cell tags in addition to TD/TH
        cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True))
                 for c in tr.find_all(["td", "th", "te", "tu"])]
        if cells:
            rows.append(cells)
    return rows


def main() -> None:
    for label, corp in FIRMS.items():
        rcept_no = annual_rcept_no(corp, 2025)
        section(f"{label}: FY2025 annual report rcept_no={rcept_no}")
        resp, latency = dart_get("document.xml", rcept_no=rcept_no)
        print(f"  HTTP {resp.status_code} content-type={resp.headers.get('content-type')} "
              f"bytes={len(resp.content)} ({latency:.2f}s)")
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        out_dir = RAW / "dart" / "documents" / rcept_no
        out_dir.mkdir(parents=True, exist_ok=True)
        zf.extractall(out_dir)
        for info in zf.infolist():
            print(f"  member {info.filename} ({info.file_size} bytes)")

        main_xml = max(zf.infolist(), key=lambda i: i.file_size)
        raw = zf.read(main_xml.filename)
        head = raw[:200].decode("utf-8", errors="replace")
        print(f"  head: {head[:120]!r}")
        text = raw.decode("utf-8", errors="replace")
        soup = BeautifulSoup(text, "lxml")
        tables = soup.find_all("table")
        print(f"  tables in main document: {len(tables)}")

        hits = []
        for i, tbl in enumerate(tables):
            rows = table_text(tbl)
            flat = " ".join(" ".join(r) for r in rows[:3])
            # the CB table header usually sits in the table or in the preceding title text
            prev = tbl.find_previous(string=re.compile("미상환 전환사채|미상환전환사채"))
            near_title = prev is not None and len(tbl.find_all_previous("table", limit=2)) >= 0
            if all(k in flat for k in KEYWORDS) or ("전환" in flat and "미상환" in flat):
                hits.append((i, rows))
            elif near_title and "전환가액" in flat:
                hits.append((i, rows))
        print(f"  candidate CB tables: {len(hits)}")
        for i, rows in hits[:3]:
            print(f"  -- table #{i} ({len(rows)} rows)")
            for r in rows[:8]:
                print(f"     {r}")
        if hits:
            i, _ = hits[0]
            save_fixture("dart", f"doc_cb_table_{label}.html", str(tables[i]))
            # unit caption: look for "(단위" text just before the table
            cap = tables[i].find_previous(string=re.compile(r"단위"))
            print(f"  unit caption near table: {cap.strip() if cap else None!r}")


if __name__ == "__main__":
    main()
