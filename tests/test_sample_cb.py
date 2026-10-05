"""P2: sample selection rules and CB state at the evaluation date."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.data.cb_truth import build_cb_block, current_instruments, reconcile_units
from src.data.ground_truth import anchor_row
from src.data.sample import apply_exclusions, mid_band, select_large, select_mid, select_small


def universe(n=500):
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "corp_code": [f"C{i:04d}" for i in range(n)],
        "market": ["KOSPI"] * n,
        "market_cap": np.sort(rng.uniform(1e9, 1e14, n))[::-1],
        "excl_build": [i % 37 == 0 for i in range(n)],
    })


def test_exclusions_and_large():
    df = apply_exclusions(universe())
    assert not df.loc[0, "eligible"]  # i % 37 == 0
    large = select_large(df, 50)
    assert len(large) == 50 and large["eligible"].all()
    assert large["market_cap"].is_monotonic_decreasing
    assert "C0000" not in set(large["corp_code"])


def test_mid_selection_contrast_within_quintiles():
    df = apply_exclusions(universe())
    band = mid_band(df, (101, 400))
    assert band["cap_rank"].between(101, 400).all() and len(band) == 300
    news = pd.Series(np.arange(len(band)) % 97, index=band["corp_code"].values)
    mid = select_mid(band, news, n=50, seed=7)
    assert len(mid) == 50 and mid["corp_code"].is_unique
    for _, g in mid.groupby("cap_quintile"):
        assert (g["news_group"] == "high").sum() == 5 and (g["news_group"] == "low").sum() == 5
        assert g[g.news_group == "high"]["newsworthiness"].min() > \
            g[g.news_group == "low"]["newsworthiness"].max()
    again = select_mid(band, news, n=50, seed=7)
    assert list(again["corp_code"]) == list(mid["corp_code"])  # seeded


def test_select_small_rules():
    cand = pd.DataFrame({
        "corp_code": ["a", "b", "c", "d", "e"],
        "eligible": [True, True, True, False, True],
        "itm": [True, True, False, True, True],
        "dilution": [0.30, 0.10, 0.50, 0.40, 2.5],
        "cb_complex": [None, None, None, None, None],
    })
    s = select_small(cand, n=10)
    assert list(s["corp_code"]) == ["a", "b"]  # c not ITM, d ineligible, e implausible


@pytest.mark.parametrize("face,price,shares,expected", [
    (6_100_000_000, 2110, 2_891_398, 6_100_000_000),      # consistent in KRW
    (6_100, 2110, 2_891_398, 6_100_000_000),              # table in KRW million
    (6_100_000, 2110, 2_891, 6_100_000_000),              # KRW thousand, shares in thousand
    (223, 1343, 0, None),                                  # conversion residue
    (5_000_000_000, 1000, 9_999, None),                    # inconsistent
])
def test_reconcile_units(face, price, shares, expected):
    got = reconcile_units(face, price, shares)
    assert (got is None and expected is None) or got == pytest.approx(expected)


def test_current_instruments_applies_refixing_and_maturity():
    out = pd.DataFrame([
        {"series": "10", "face_outstanding": 8e9, "conv_price": 1495.0,
         "convertible_shares": 5_351_170, "maturity": date(2028, 10, 30),
         "issue_date": date(2025, 10, 30)},
        {"series": "5", "face_outstanding": 5.6e9, "conv_price": 1003.0,
         "convertible_shares": 5_583_250, "maturity": date(2026, 3, 23),
         "issue_date": date(2023, 3, 23)},   # matured before T_post
    ])
    refix = pd.DataFrame([
        {"series": "10", "price_after": 1355.0, "effective_date": date(2026, 3, 30)},
        {"series": "10", "price_after": 1200.0, "effective_date": date(2026, 8, 30)},  # after
    ])
    terms = pd.DataFrame([{"series": "10", "refix_floor": 1047.0}])
    ins = current_instruments(out, refix, terms, date(2026, 4, 1))
    assert len(ins) == 1
    i = ins[0]
    assert (i.series, i.conversion_price, i.refix_floor) == ("10", 1355.0, 1047.0)
    assert i.face_outstanding == pytest.approx(8000.0)          # KRW million
    assert i.convertible_shares == pytest.approx(8e9 / 1355)
    block = build_cb_block(ins, date(2026, 4, 1))
    assert "1,355원" in block.filing_text and "1,047원" in block.filing_text
    assert build_cb_block([], date(2026, 4, 1)) is None


def test_stale_refix_floor_is_dropped():
    out = pd.DataFrame([{"series": "30", "face_outstanding": 1.2e9, "conv_price": 456.0,
                         "convertible_shares": 2_631_579, "maturity": date(2027, 9, 6),
                         "issue_date": date(2024, 9, 6)}])
    terms = pd.DataFrame([{"series": "30", "refix_floor": 2500.0}])  # pre-reverse-split value
    ins = current_instruments(out, pd.DataFrame(), terms, date(2026, 4, 1))
    assert ins[0].refix_floor is None
    assert "최저한도" not in build_cb_block(ins, date(2026, 4, 1)).filing_text


def test_anchor_row():
    r = anchor_row("L001", "x", 100.0, 150.0, date(2025, 1, 1), "krx", "krx")
    assert r["log_diff"] == pytest.approx(np.log(1.5)) and r["e7_candidate"]
    assert not anchor_row("L001", "x", 100.0, 120.0, date(2025, 1, 1), "krx", "krx")[
        "e7_candidate"]
    assert anchor_row("L001", "x", None, 120.0, date(2025, 1, 1), None, "krx")["log_diff"] \
        is None
