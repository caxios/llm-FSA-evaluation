"""P3: Korean amount detection and replacement in CB disclosure text."""

import pytest

from src.perturb.text_numbers import find_amounts, find_prices, replace_amount, replace_price

# (snippet, value in KRW, expected matched substrings)
AMOUNT_CASES = [
    ("- 미상환 권면총액: 20,000,000,000원", 2e10, ["20,000,000,000원"]),
    ("사채의 권면총액 200억원", 2e10, ["200억원"]),
    ("사채의 권면(전자등록)총액 200억 원", 2e10, ["200억 원"]),
    ("권면총액 20,000,000,000원(200억원)", 2e10, ["20,000,000,000원", "200억원"]),
    ("(단위: 백만원)\n| 제10회 | 6,100 |", 6.1e9, ["6,100"]),
    ("(단위 : 천원)\n| 제10회 | 6,100,000 |", 6.1e9, ["6,100,000"]),
    ("<미상환 전환사채 발행현황> (단위: 원, 주)\n| 10 | 6,100,000,000 | 2,110 |", 6.1e9,
     ["6,100,000,000"]),
    ("발행금액 6100000000원", 6.1e9, ["6100000000원"]),
    ("미상환잔액 3,000백만원", 3e9, ["3,000백만원"]),
    ("미상환잔액 3,000 백만원", 3e9, ["3,000 백만원"]),
    ("권면총액 1,234억 5,678만원", 123_456_780_000, ["1,234억 5,678만원"]),
    ("발행총액 1조 2,000억원", 1.2e12, ["1조 2,000억원"]),
    ("발행총액 1.5억원", 1.5e8, ["1.5억원"]),
    ("약 50억원 규모", 4.99e9, ["50억원"]),          # rounded mention
    ("약 50억원 규모", 5.1e9, []),
    ("만기일 2028-10-30, 제16회차", 1.6e10, []),     # dates and series numbers
    ("(단위: 백만원)\n| 6,100 |\n\n6,100", 6.1e9, ["6,100"]),  # caption ends at blank line
    ("전환가액 5,000원, 권면총액 5,000,000,000원", 5e9, ["5,000,000,000원"]),
    ("사채 총액 금 오십억원정", 5e9, []),             # spelled-out numerals are not handled
    ("전환청구로 3억 원이 감소하여 잔액은 17억 원", 1.7e9, ["17억 원"]),
]


@pytest.mark.parametrize("text,value,expected", AMOUNT_CASES)
def test_find_amounts(text, value, expected):
    assert [s.text for s in find_amounts(text, value)] == expected


PRICE_CASES = [
    ("- 현재 전환가액: 1,355원", 1355, ["1,355원"]),
    ("전환가액 1,355 원으로 조정", 1355, ["1,355 원"]),
    ("(단위: 원, 주)\n| 10 | 2028-10-30 | 8,000,000,000 | 1,355 | 5,904,059 |", 1355,
     ["1,355"]),
    ("(단위: 백만원)\n| 1,355 |", 1355, []),            # a KRW-million table, not a price
    ("전환 시 발행할 주식: 보통주 1,355주", 1355, []),
    ("(단위: 백만원)\n조정 후 전환가액 1,355원", 1355, ["1,355원"]),
]


@pytest.mark.parametrize("text,price,expected", PRICE_CASES)
def test_find_prices(text, price, expected):
    assert [s.text for s in find_prices(text, price)] == expected


def test_replace_keeps_each_format():
    text = "권면총액 20,000,000,000원(200억 원)\n(단위: 백만원)\n| 20,000 |"
    new, n = replace_amount(text, 2e10, 4e10)
    assert n == 3
    assert new == "권면총액 40,000,000,000원(400억 원)\n(단위: 백만원)\n| 40,000 |"


@pytest.mark.parametrize("text,a,b", [
    ("권면총액 20,000,000,000원(200억 원)\n(단위: 백만원)\n| 20,000 |", 2e10, 4e10),
    ("권면총액 1,234억 5,678만원", 123_456_780_000, 246_913_560_000),
    ("발행총액 1조 2,000억원, 미상환 3,000백만원", 1.2e12, 2.4e12),
    ("발행금액 6100000000원", 6.1e9, 12.2e9),
])
def test_round_trip(text, a, b):
    once, n1 = replace_amount(text, a, b)
    back, n2 = replace_amount(once, b, a)
    assert n1 == n2 >= 1 and back == text


def test_korean_rendering_drops_zero_parts():
    new, n = replace_amount("총액 1,234억 5,678만원", 123_456_780_000, 2e11)
    assert n == 1 and new == "총액 2,000억원"


def test_replace_price():
    text = "- 현재 전환가액: 1,355원 (최저한도: 1,047원)\n(단위: 원, 주)\n| 1,355 |"
    new, n = replace_price(text, 1355, 1047)
    assert n == 2
    assert new == "- 현재 전환가액: 1,047원 (최저한도: 1,047원)\n(단위: 원, 주)\n| 1,047 |"
