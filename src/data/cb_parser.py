"""Parsers for convertible-bond tables in DART documents.

DART XML tables use TE/TU cell tags in addition to TD/TH (docs/data_access_memo.md).
"""

from __future__ import annotations

import bisect
import logging
import re
import warnings
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from src.data.parsing import parse_amount, parse_date, unit_multiplier

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
log = logging.getLogger(__name__)

CELL_TAGS = ["td", "th", "te", "tu"]
CB_COLUMNS = ["kind", "series", "issue_date", "maturity", "face_total", "stock_kind",
              "conv_period", "conv_ratio", "conv_price", "face_outstanding",
              "convertible_shares", "note"]


def load_soup(path_or_text: Path | str) -> BeautifulSoup:
    if isinstance(path_or_text, Path):
        text = path_or_text.read_text(encoding="utf-8", errors="replace")
    else:
        text = path_or_text
    return BeautifulSoup(text, "lxml")


def main_document(doc_dir: Path, rcept_no: str) -> Path:
    """The main report file (`{rcept_no}.xml`); attachments have suffixes like `_00760`."""
    main = doc_dir / f"{rcept_no}.xml"
    if main.exists():
        return main
    candidates = sorted(doc_dir.glob("*.xml"), key=lambda p: p.stat().st_size, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"no XML documents in {doc_dir}")
    return candidates[0]


def table_rows(table) -> list[list[str]]:
    rows = []
    for tr in table.find_all("tr"):
        cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in tr.find_all(CELL_TAGS)]
        if cells:
            rows.append(cells)
    return rows


def _series(text: str) -> str:
    m = re.search(r"\d+", text)
    return m.group(0) if m else text.strip()


def _is_unredeemed_cb_table(rows: list[list[str]]) -> bool:
    header = " ".join(" ".join(r) for r in rows[:2])
    return "전환청구가능기간" in header and "전환가능주식수" in header and "미상환" in header


_TABLE_OPEN = re.compile(r"<table\b", re.IGNORECASE)
_TABLE_CLOSE = re.compile(r"</table\s*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_UNIT = re.compile(r"단위\s*[:：]?[^)<]{0,20}")


def _read_text(source: Path | str) -> str:
    if isinstance(source, Path):
        return source.read_text(encoding="utf-8", errors="replace")
    return source


def _candidate_tables(raw: str, keyword: str) -> list[tuple[int, int]]:
    """(start, end) spans of the tables that contain `keyword`, found with regexes only.

    Annual reports are ~2 MB of XML with ~700 tables; parsing the whole document with
    BeautifulSoup is slow and memory-hungry, so only the matching tables are parsed.
    """
    opens = [m.start() for m in _TABLE_OPEN.finditer(raw)]
    spans: list[tuple[int, int]] = []
    for m in re.finditer(keyword, raw):
        i = bisect.bisect_right(opens, m.start()) - 1
        if i < 0:
            continue
        close = _TABLE_CLOSE.search(raw, m.start())
        if close is None:
            continue
        span = (opens[i], close.end())
        if span not in spans:
            spans.append(span)
    return spans


def _unit_before(raw: str, start: int, window: int = 3000) -> str | None:
    text = _TAG.sub(" ", raw[max(0, start - window):start])
    hits = _UNIT.findall(text)
    return f"({hits[-1].strip()})" if hits else None


def parse_unredeemed_cb_table(source: Path | str) -> tuple[pd.DataFrame, dict]:
    """Parse the annual report's "미상환 전환사채 발행현황" table.

    Returns (rows, info). Amounts are converted to KRW using the unit caption.
    info["status"]: "table" (table found; it may hold only a total row), "none_declared"
    (the section says there is nothing to report), or "not_found" (no table, no statement).
    """
    raw = _read_text(source)
    matches = []
    for start, end in _candidate_tables(raw, "전환청구가능기간"):
        table = BeautifulSoup(raw[start:end], "lxml").find("table")
        rows = table_rows(table) if table else []
        if rows and _is_unredeemed_cb_table(rows):
            matches.append((start, rows))
    info: dict = {"found": bool(matches), "status": "table", "n_tables": len(matches),
                  "unit": None, "warnings": []}
    if not matches:
        # Firms without CBs often write "미상환 전환사채 발행현황 ... 해당사항 없습니다".
        text = re.sub(r"\s+", "", _TAG.sub(" ", raw))
        m = re.search(r"미상환전환사채발행현황(.{0,30})", text)
        info["status"] = ("none_declared" if m and "해당사항" in m.group(1) else "not_found")
        return pd.DataFrame(columns=CB_COLUMNS), info
    if len(matches) > 1:
        info["warnings"].append(f"{len(matches)} matching tables; using the first")
    start, rows = matches[0]
    info["unit"] = _unit_before(raw, start)
    mult = unit_multiplier(info["unit"])

    records = []
    for cells in rows[2:]:  # two header rows
        if not cells or cells[0].replace(" ", "").startswith("합계"):
            continue
        if len(cells) < 11:
            info["warnings"].append(f"skipped short row: {cells}")
            continue
        rec = dict(zip(CB_COLUMNS, cells[:12] + [""] * (12 - len(cells[:12])), strict=True))
        records.append({
            **rec,
            "series": _series(rec["series"]),
            "issue_date": parse_date(rec["issue_date"]),
            "maturity": parse_date(rec["maturity"]),
            "face_total": parse_amount(rec["face_total"]) * mult,
            "conv_ratio": parse_amount(rec["conv_ratio"]),
            "conv_price": parse_amount(rec["conv_price"]),
            "face_outstanding": parse_amount(rec["face_outstanding"]) * mult,
            "convertible_shares": parse_amount(rec["convertible_shares"]),
        })
    return pd.DataFrame(records, columns=CB_COLUMNS), info


def parse_refixing(source: Path | str) -> pd.DataFrame:
    """Parse a "전환가액의조정" exchange disclosure.

    Returns rows: series, listed, price_before, price_after, effective_date.
    """
    soup = load_soup(source)
    rows = [r for t in soup.find_all("table") for r in table_rows(t)]
    effective = None
    for r in rows:
        if r[0].replace(" ", "").startswith("5.조정가액적용일") and len(r) > 1:
            effective = parse_date(r[1])
    records, in_section = [], False
    for r in rows:
        head = r[0].replace(" ", "")
        if head.startswith("1.조정에관한사항"):
            in_section = True
            continue
        if in_section and re.match(r"^\d+\.", head) and not head.isdigit():
            break
        if in_section and len(r) >= 4:
            records.append({
                "series": _series(r[0]),
                "listed": r[1],
                "price_before": parse_amount(r[2]),
                "price_after": parse_amount(r[3]),
                "effective_date": effective,
            })
    return pd.DataFrame(records, columns=["series", "listed", "price_before", "price_after",
                                          "effective_date"])
