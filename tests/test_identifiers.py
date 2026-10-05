"""P4: identifier dictionary and industry labels."""

import pandas as pd
import pytest

from src.conditions.identifiers import (
    address_tokens,
    build_identifiers,
    ceo_names,
    homepage_domain,
    investee_names,
    name_variants,
    strip_legal,
)
from src.conditions.industry import division_labels, label_for, section_label


@pytest.mark.parametrize("raw,expected", [
    ("삼성전자(주)", "삼성전자"), ("㈜우진", "우진"), ("주식회사 크래프톤", "크래프톤"),
    ("(주)LG화학", "LG화학"), ("SAMSUNG ELECTRONICS CO,.LTD", "SAMSUNG ELECTRONICS"),
    ("Hyper Corporation", "Hyper"), ("두산퓨얼셀 주식회사", "두산퓨얼셀"),
])
def test_strip_legal(raw, expected):
    assert strip_legal(raw) == expected


def test_name_variants():
    v = name_variants("에스케이하이닉스(주)", "SK하이닉스", "SK hynix Inc.")
    assert {"에스케이하이닉스", "SK하이닉스", "SK hynix", "SKhynix"} <= set(v)
    assert "포스코" in name_variants("포스코홀딩스(주)")       # holding suffix dropped
    assert name_variants("", None) == []


def test_ceo_address_homepage():
    assert ceo_names("이재상, 백승한 각자대표") == ["이재상", "백승한"]
    assert ceo_names("맥쿼리자산운용(주)") == []
    assert address_tokens("경기도 화성시 동부대로970번길 110") == ["화성시"]
    assert address_tokens("서울특별시 강남구 테헤란로 427") == ["서울특별시", "강남구"]
    assert homepage_domain("www.woojininc.com") == "woojininc.com"
    assert homepage_domain("https://www.samsung.com/sec/") == "samsung.com"
    assert homepage_domain("-") is None and homepage_domain("") is None


def test_investees_drop_totals_and_generic_terms():
    inv = pd.DataFrame({"inv_prm": ["삼성전기㈜", "합계", "기타", "SDMA", "한국투자조합 1호",
                                    "삼성전자", "스테코㈜"]})
    out = investee_names(inv, own=["삼성전자"])
    assert out == ["삼성전기", "SDMA", "스테코"]
    assert investee_names(pd.DataFrame()) == []


def test_build_identifiers_with_overrides():
    company = {"corp_name": "삼성전자(주)", "stock_name": "삼성전자",
               "corp_name_eng": "SAMSUNG ELECTRONICS CO,.LTD", "stock_code": "005930",
               "ceo_nm": "전영현, 노태문", "adres": "경기도 수원시 영통구 삼성로 129",
               "hm_url": "www.samsung.com"}
    inv = pd.DataFrame({"inv_prm": ["삼성전기㈜"]})
    ids = build_identifiers("L001", company, inv, {"brands": ["갤럭시"]})
    assert ids.names[0] == "삼성전자" and "SAMSUNG ELECTRONICS" in ids.names
    assert ids.group_names == ["삼성"] and ids.ticker == "005930"
    assert ids.investees == ["삼성전기"] and ids.brands == ["갤럭시"]
    assert ids.address_tokens == ["수원시", "영통구"] and ids.homepage == "samsung.com"
    assert "005930" in ids.all_terms()


def test_industry_labels():
    assert label_for("26") == "국내 전자부품·컴퓨터·통신장비 제조 기업"
    assert label_for("12", {"12": 1}) == "국내 제조 기업"            # too few peers
    assert label_for("12", {"12": 50}) == division_labels()["12"]
    assert section_label("51") == "국내 운수·창고 기업" and label_for(None) is None
    for label in division_labels().values():
        assert "1위" not in label and "대표" not in label and label.startswith("국내")
