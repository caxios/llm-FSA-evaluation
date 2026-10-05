from datetime import date

import pandas as pd

from src.data.universe import build_universe, fs_status, ksic_division

COMPANIES = pd.DataFrame([
    {"corp_code": "A", "corp_name": "삼성", "stock_code": "005930", "corp_cls": "Y",
     "induty_code": "264"},
    {"corp_code": "B", "corp_name": "은행", "stock_code": "105560", "corp_cls": "Y",
     "induty_code": "641"},
    {"corp_code": "C", "corp_name": "코스닥CB", "stock_code": "069540", "corp_cls": "K",
     "induty_code": "264"},
    {"corp_code": "D", "corp_name": "코스닥무CB", "stock_code": "123456", "corp_cls": "K",
     "induty_code": "582"},
    {"corp_code": "E", "corp_name": "코넥스", "stock_code": "999999", "corp_cls": "N",
     "induty_code": "264"},
])
KOSPI = pd.DataFrame([
    {"ticker": "005930", "close": 189600.0, "volume": 1e7, "market_cap": 1e15,
     "shares_listed": 5.9e9},
    {"ticker": "105560", "close": 1.0, "volume": 0.0, "market_cap": 1e12, "shares_listed": 1e8},
])
ISSUERS = pd.DataFrame([{"corp_code": "C", "n_filings": 3}])


def test_ksic_division():
    assert ksic_division("264") == "26" and ksic_division("") is None and ksic_division(None) \
        is None


def test_build_universe_flags():
    uni = build_universe(COMPANIES, KOSPI, None, ISSUERS, ["64", "65", "66"]).set_index(
        "corp_code")
    assert "E" not in uni.index  # KONEX dropped
    assert uni.loc["A", "in_universe"] and uni.loc["A", "market_cap"] == 1e15
    assert not uni.loc["B", "in_universe"] and uni.loc["B", "excl_financial"]
    assert uni.loc["B", "halted"]  # zero volume on the evaluation date
    assert uni.loc["C", "in_universe"] and uni.loc["C", "n_cb_filings"] == 3
    assert not uni.loc["D", "in_universe"]
    assert pd.isna(uni.loc["C", "halted"])  # KOSDAQ not covered by KRX data


def test_fs_status():
    fs = pd.DataFrame({"rcept_no": ["20260320001115"] * 2, "sj_div": ["BS", "IS"],
                       "thstrm_amount": [1.0, 2.0], "frmtrm_amount": [1.0, 2.0],
                       "bfefrmtrm_amount": [1.0, None]})
    s = fs_status(fs, "CFS", date(2026, 4, 1))
    assert s["filed_by_t_post"] and s["has_3y"] and s["rcept_dt"] == date(2026, 3, 20)
    late = fs.assign(rcept_no="20260622000085")
    assert not fs_status(late, "CFS", date(2026, 4, 1))["filed_by_t_post"]
    assert fs_status(pd.DataFrame(), "CFS", date(2026, 4, 1))["fs_div"] is None
    one_year = fs.drop(columns=["frmtrm_amount", "bfefrmtrm_amount"])
    assert not fs_status(one_year, "CFS", date(2026, 4, 1))["has_3y"]
