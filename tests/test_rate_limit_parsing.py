import math
from datetime import date

import pytest

from src.data.parsing import parse_amount, parse_date, rcept_date, unit_multiplier
from src.data.rate_limit import QuotaExhausted, RateLimiter


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s


def test_rate_limiter_spaces_calls():
    c = FakeClock()
    lim = RateLimiter(per_second=2, clock=c.clock, sleep=c.sleep)
    lim.acquire()
    lim.acquire()
    c.t += 0.2
    lim.acquire()
    assert c.slept == pytest.approx([0.5, 0.3])


def test_daily_quota_persists_across_instances(tmp_path):
    state = tmp_path / "quota.json"
    day = lambda: date(2026, 10, 5)  # noqa: E731
    a = RateLimiter(per_second=1000, daily_quota=2, state_path=state, today=day)
    a.acquire()
    b = RateLimiter(per_second=1000, daily_quota=2, state_path=state, today=day)
    b.acquire()
    assert b.used_today() == 2
    with pytest.raises(QuotaExhausted):
        b.acquire()
    tomorrow = RateLimiter(per_second=1000, daily_quota=2, state_path=state,
                           today=lambda: date(2026, 10, 6))
    tomorrow.acquire()  # new day, new budget


@pytest.mark.parametrize("raw,expected", [
    ("1,234", 1234.0), ("(1,234)", -1234.0), ("△500", -500.0), ("-7", -7.0),
    (" 8,000,000,000 ", 8e9), ("12.5", 12.5), (42, 42.0),
])
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["", "-", None, "N/A", "abc"])
def test_parse_amount_missing(raw):
    assert math.isnan(parse_amount(raw))


@pytest.mark.parametrize("raw,expected", [
    ("2029년 12월 24일", date(2029, 12, 24)), ("2023.04.28", date(2023, 4, 28)),
    ("2026-03-30", date(2026, 3, 30)), ("20260330", date(2026, 3, 30)),
    ("2025년 11월 27일 ~ 2027년 10월 26일", date(2025, 11, 27)), ("-", None), (None, None),
])
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


def test_unit_multiplier_and_rcept_date():
    assert unit_multiplier("(단위 : 원, 주)") == 1
    assert unit_multiplier("(단위: 천원)") == 1e3
    assert unit_multiplier("(단위 : 백만원)") == 1e6
    assert rcept_date("20260320001115") == date(2026, 3, 20)
