"""Convertible-bond data collection for KOSDAQ candidates (P1.4)."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from src.data.cb_parser import main_document, parse_refixing, parse_unredeemed_cb_table
from src.data.dart_client import DartClient, DartError
from src.data.parsing import parse_amount, parse_date, rcept_date

log = logging.getLogger(__name__)

# Matches "주요사항보고서(전환사채권발행결정)" including "[기재정정]"/"[첨부정정]" prefixes.
CB_ISSUANCE_TITLE = "전환사채권발행결정"
REFIXING_TITLE = "전환가액의조정"


def find_cb_issuers(dart: DartClient, bgn: date, end: date, corp_cls: str = "K") -> pd.DataFrame:
    """Firms with at least one CB issuance decision (major-event report) in [bgn, end].

    Returns one row per corp_code: corp_name, stock_code, n_filings, first_rcept_dt,
    last_rcept_dt.
    """
    filings = dart.search_filings(bgn, end, pblntf_ty="B", corp_cls=corp_cls)
    if filings.empty:
        return pd.DataFrame(columns=["corp_code", "corp_name", "stock_code", "n_filings",
                                     "first_rcept_dt", "last_rcept_dt"])
    hits = filings[filings["report_nm"].str.replace(" ", "").str.contains(CB_ISSUANCE_TITLE)]
    return (hits.groupby("corp_code")
            .agg(corp_name=("corp_name", "last"), stock_code=("stock_code", "last"),
                 n_filings=("rcept_no", "count"), first_rcept_dt=("rcept_dt", "min"),
                 last_rcept_dt=("rcept_dt", "max"))
            .reset_index())


def collect_cb_terms(dart: DartClient, corp_code: str, bgn: date, end: date) -> pd.DataFrame:
    """Normalized CB issuance terms; one row per series (latest filing wins for corrections)."""
    raw = dart.cb_issuance_decisions(corp_code, bgn, end)
    if raw.empty:
        return pd.DataFrame()
    out = pd.DataFrame({
        "corp_code": corp_code,
        "rcept_no": raw["rcept_no"],
        "rcept_dt": raw["rcept_no"].map(rcept_date),
        "series": raw["bd_tm"].astype(str).str.extract(r"(\d+)", expand=False),
        "kind": raw.get("bd_knd"),
        "face": raw["bd_fta"].map(parse_amount),
        "conv_price": raw["cv_prc"].map(parse_amount),
        "convertible_shares": raw["cvisstk_cnt"].map(parse_amount),
        "pct_of_shares": raw.get("cvisstk_tisstk_vs", pd.Series(dtype=str)).map(parse_amount),
        "refix_floor": raw.get("act_mktprcfl_cvprc_lwtrsprc",
                               pd.Series(dtype=str)).map(parse_amount),
        "maturity": raw["bd_mtd"].map(parse_date),
        "conv_start": raw["cvrqpd_bgd"].map(parse_date),
        "conv_end": raw["cvrqpd_edd"].map(parse_date),
        "board_date": raw["bddd"].map(parse_date),
        "issue_method": raw.get("bdis_mthn"),
    })
    out = out.sort_values("rcept_no").drop_duplicates("series", keep="last")
    return out.reset_index(drop=True)


def collect_refixings(dart: DartClient, corp_code: str, bgn: date, end: date) -> pd.DataFrame:
    """Conversion-price adjustments disclosed in [bgn, end], parsed from the documents."""
    filings = dart.search_filings(bgn, end, corp_code=corp_code, pblntf_ty="I")
    if filings.empty:
        return pd.DataFrame()
    hits = filings[filings["report_nm"].str.replace(" ", "").str.contains(REFIXING_TITLE)]
    frames = []
    for rcept_no in hits["rcept_no"]:
        try:
            doc = main_document(dart.document(rcept_no), rcept_no)
        except (DartError, FileNotFoundError) as exc:
            log.warning("refixing document %s unavailable: %s", rcept_no, exc)
            continue
        rows = parse_refixing(doc)
        if rows.empty:
            log.warning("refixing document %s: no rows parsed", rcept_no)
            continue
        rows.insert(0, "rcept_no", rcept_no)
        rows.insert(0, "corp_code", corp_code)
        frames.append(rows)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def unredeemed_cb_table(dart: DartClient, corp_code: str, rcept_no: str) -> tuple[pd.DataFrame,
                                                                                    dict]:
    """Outstanding CBs from an annual report (by its rcept_no)."""
    doc = main_document(dart.document(rcept_no), rcept_no)
    table, info = parse_unredeemed_cb_table(doc)
    table.insert(0, "rcept_no", rcept_no)
    table.insert(0, "corp_code", corp_code)
    info.update(corp_code=corp_code, rcept_no=rcept_no)
    return table, info
