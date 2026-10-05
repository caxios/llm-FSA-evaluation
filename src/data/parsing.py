"""Parsers for the value formats used in DART and KRX responses."""

from __future__ import annotations

import math
import re
from datetime import date

_EMPTY = {"", "-", "－", "N/A", "n/a"}
_KOREAN_DATE = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_DOTTED_DATE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def parse_amount(value: str | float | int | None) -> float:
    """'1,234' -> 1234.0; '(1,234)' and '△1,234' -> -1234.0; '' / '-' / None -> NaN."""
    if value is None:
        return math.nan
    if isinstance(value, (int, float)):
        return float(value)
    s = value.strip().replace(",", "").replace(" ", "")
    if s in _EMPTY:
        return math.nan
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    if s and s[0] in "△▲-":
        negative, s = True, s[1:]
    try:
        number = float(s)
    except ValueError:
        return math.nan
    return -number if negative else number


def parse_date(value: str | None) -> date | None:
    """Parse '2029년 12월 24일', '2023.04.28', '2026-03-30', '20260330'."""
    if not value:
        return None
    s = value.strip()
    m = _KOREAN_DATE.search(s) or _DOTTED_DATE.search(s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if re.fullmatch(r"\d{8}", s):
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    return None


def unit_multiplier(caption: str | None) -> float:
    """Multiplier to KRW from a caption such as '(단위 : 원, 주)' or '(단위: 백만원)'."""
    if not caption:
        return 1.0
    s = caption.replace(" ", "")
    if "백만원" in s:
        return 1e6
    if "천원" in s:
        return 1e3
    if "억원" in s:
        return 1e8
    return 1.0


def rcept_date(rcept_no: str) -> date:
    """The first 8 digits of a DART receipt number are the filing date."""
    return date(int(rcept_no[:4]), int(rcept_no[4:6]), int(rcept_no[6:8]))
