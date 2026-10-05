"""P4: redaction rules."""

import pytest

from src.conditions.identifiers import FirmIdentifiers
from src.conditions.redactor import find_identifiers, redact_text

IDS = FirmIdentifiers(
    firm_id="L001", names=["삼성전자", "SAMSUNG ELECTRONICS"], ticker="005930",
    ceo=["전영현"], address_tokens=["수원시"], homepage="samsung.com",
    investees=["삼성전기", "SDMA"], brands=["갤럭시"], group_names=["삼성"],
    segments=["DX부문", "DS부문"])


@pytest.mark.parametrize("text,expected,rule", [
    ("삼성전기 지분법투자", "관계회사 지분법투자", "investee"),
    ("종속기업투자(삼성전기)", "종속기업투자(종속회사)", "investee"),
    ("삼성전자 별도 기준", "당사 별도 기준", "name"),
    ("삼성 전자 매출", "당사 매출", "name"),                  # spaced-out name
    ("Samsung Electronics 지분", "당사 지분", "name"),        # case-insensitive
    ("갤럭시 판매 수익", "주요 제품 판매 수익", "brand"),
    ("삼성 계열사 매출", "당사 계열사 매출", "group"),          # whole token
    ("종목코드 005930", "종목코드", "ticker"),
    ("DX부문 매출액", "부문1 매출액", "segment"),
])
def test_rules(text, expected, rule):
    out, log = redact_text(text, IDS, "label")
    assert out == expected
    assert log and log[0].rule == rule and log[0].field == "label"


def test_longest_match_and_no_false_positives():
    # investee "삼성전기" wins over group "삼성"; short group name not matched inside words
    out, log = redact_text("삼성전기와 삼성물산우선주", IDS)
    assert out == "관계회사와 삼성물산우선주"
    assert [r.rule for r in log] == ["investee"]
    ids = FirmIdentifiers(firm_id="X", group_names=["LG", "SK"], names=["우진"])
    for label in ("ELG 장비", "리스크관리", "SKU 재고", "우진건설투자", "매출채권"):
        assert redact_text(label, ids)[0] == label


def test_segments_numbered_across_fields():
    seg: dict[str, str] = {}
    a, _ = redact_text("DS부문 매출", IDS, segment_map=seg)
    b, _ = redact_text("DX부문 매출", IDS, segment_map=seg)
    c, _ = redact_text("DS부문 이익", IDS, segment_map=seg)
    assert (a, b, c) == ("부문1 매출", "부문2 매출", "부문1 이익")


def test_placeholders_and_empty_dictionary():
    ids = FirmIdentifiers(firm_id="X", homepage="-", names=["-"])
    assert redact_text("| 1,000 | - |", ids) == ("| 1,000 | - |", [])
    assert redact_text("매출액", FirmIdentifiers(firm_id="X")) == ("매출액", [])


def test_find_identifiers():
    hits = find_identifiers("당사는 삼성전기 지분과 005930 언급", IDS)
    assert ("investee", "삼성전기") in hits and ("ticker", "005930") in hits
    assert find_identifiers("수원시", IDS) == []           # address excluded by default
