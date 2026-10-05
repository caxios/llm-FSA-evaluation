"""P4: fake company names (D4.3)."""

import random

import pandas as pd
import pytest

from src.conditions.fake_names import (
    assign_fake_names,
    generate_candidates,
    is_acceptable,
    nearest,
    normalize_name,
    similarity,
    suffix_set,
)

LISTED = ["삼성전자(주)", "한빛소프트", "세진중공업", "가람정밀", "SK하이닉스", "LG전자"]
ALL = LISTED + ["한빛정밀(비상장)", "누리테크"]


def test_similarity():
    assert similarity("abc", "abc") == 1.0
    assert similarity("kitten", "sitting") == pytest.approx(1 - 3 / 7)
    assert similarity("가", "가나다라마") == pytest.approx(0.2)
    assert similarity("가", "가나다라마", threshold=0.5) == 0.0   # pruned by length gap


def test_acceptance_rules():
    every = {normalize_name(n) for n in ALL}
    assert not is_acceptable("한빛소프트", LISTED, every)          # exact listed
    assert not is_acceptable("누리테크", LISTED, every)            # exact (unlisted) name
    assert not is_acceptable("가람정밀공업", LISTED, every)         # too similar (0.67)
    assert is_acceptable("윤슬소재", LISTED, every)
    sim, near = nearest("세진정밀", [normalize_name(n) for n in LISTED])
    assert sim < 0.6 and near is not None


def test_suffix_sets_follow_industry():
    assert suffix_set("국내 전자부품·컴퓨터·통신장비 제조 기업") == "electronics"
    assert suffix_set("국내 기타 운송장비 제조 기업") == "manufacturing"
    assert suffix_set("국내 의료·정밀·광학기기 제조 기업") == "precision"
    assert suffix_set("국내 출판 기업") == "it" and suffix_set(None) == "general"
    names = generate_candidates("국내 의약품 제조 기업", random.Random(1), n=10)
    assert len(names) == len(set(names)) == 10


def test_assignment_unique_reproducible_and_clean():
    sample = pd.DataFrame({"firm_id": [f"S{i:03d}" for i in range(30)],
                           "industry_label": ["국내 식료품 제조 기업"] * 30})
    a = assign_fake_names(sample, 7, LISTED, ALL)
    b = assign_fake_names(sample, 7, LISTED, ALL)
    assert a.equals(b) and a["fake_name"].is_unique and len(a) == 30
    assert (a["max_similarity"] < 0.6).all()
    every = {normalize_name(n) for n in ALL}
    assert not set(a["fake_name"].map(normalize_name)) & every
    for bad in ("삼성", "현대", "LG", "SK", "롯데", "한화"):
        assert not a["fake_name"].str.contains(bad).any()
