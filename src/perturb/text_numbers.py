"""Korean amount detection and replacement in disclosure text (P3 §5.3).

Recognized forms (value in KRW):
  plain      "20,000,000,000", "20000000000", "20,000,000,000원", "1,355 원", "3,000백만원"
             numbers without "원" take the unit of the nearest table caption above them
             ("(단위: 백만원)", "(단위: 천원)", "(단위: 원)") within the same block
             (a blank line ends a block); with no caption they are read as KRW
  korean     "200억", "200억원", "200억 원", "2,000억", "1,234억 5,678만", "1조 2,000억원"
A mention matches a value when it equals the value up to the rounding of its own last unit.
Replacements keep the mention's format (units, separators, commas, "원" suffix).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NUM = r"\d{1,3}(?:,\d{3})+(?![\d])|\d+"
UNITS = {"조": 1e12, "억": 1e8, "만": 1e4}
_KOREAN = re.compile(
    rf"(?<![\d,.])(?:{NUM})(?:\.\d+)?\s?[조억만](?:\s?(?:{NUM})(?:\.\d+)?\s?[조억만])*(?:\s?원)?")
_KOREAN_PART = re.compile(rf"({NUM})((?:\.\d+)?)(\s?)([조억만])")
_PLAIN = re.compile(rf"(?<![\d,.])({NUM})(?![\d.]|,\d)(\s?(?:백만\s?원|천\s?원|원))?")
_CAPTION = re.compile(r"단위\s*[:：]\s*(백만\s?원|천\s?원|원)")
CAPTION_UNITS = {"백만원": 1e6, "천원": 1e3, "원": 1.0}


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str
    value: float          # KRW
    granularity: float    # KRW value of the mention's last digit unit
    kind: str             # "plain" | "korean"
    explicit_krw: bool    # "원" suffix, or a caption saying the block is in KRW


def _context_unit(text: str, pos: int) -> float | None:
    """Unit of the closest caption above `pos` in the same block, if any."""
    block_start = text.rfind("\n\n", 0, pos)
    best = None
    for m in _CAPTION.finditer(text, max(block_start, 0), pos):
        best = CAPTION_UNITS[m.group(1).replace(" ", "")]
    return best


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def tokens(text: str) -> list[Span]:
    out: list[Span] = []
    taken: list[tuple[int, int]] = []
    for m in _KOREAN.finditer(text):
        parts = _KOREAN_PART.findall(m.group(0))
        value = sum(_num(n + d) * UNITS[u] for n, d, _, u in parts)
        out.append(Span(m.start(), m.end(), m.group(0), value, UNITS[parts[-1][3]],
                        "korean", True))
        taken.append((m.start(), m.end()))
    for m in _PLAIN.finditer(text):
        if any(a <= m.start() < b for a, b in taken):
            continue
        suffix = (m.group(2) or "").replace(" ", "")
        unit = CAPTION_UNITS[suffix] if suffix else _context_unit(text, m.start())
        out.append(Span(m.start(), m.end(), m.group(0), _num(m.group(1)) * (unit or 1.0),
                        unit or 1.0, "plain", unit == 1.0))
    return sorted(out, key=lambda s: s.start)


def _matches(span: Span, value: float) -> bool:
    return abs(span.value - value) <= 0.5 * span.granularity + 1e-9 * abs(value)


def find_amounts(text: str, value_krw: float) -> list[Span]:
    return [s for s in tokens(text) if _matches(s, value_krw)]


def find_prices(text: str, price_krw: float) -> list[Span]:
    """Per-share prices: plain numbers explicitly in KRW ("8,000원", or a KRW table)."""
    return [s for s in tokens(text)
            if s.kind == "plain" and s.explicit_krw and _matches(s, price_krw)]


def _fmt(n: int, comma: bool) -> str:
    return f"{n:,}" if comma else str(n)


def render_like(span: Span, value_krw: float) -> str:
    """Render `value_krw` in the format of an existing mention."""
    if span.kind == "plain":
        m = _PLAIN.fullmatch(span.text)
        assert m is not None
        digits = m.group(1)
        comma = "," in digits or len(digits) < 4
        return _fmt(round(value_krw / span.granularity), comma) + (m.group(2) or "")
    parts = _KOREAN_PART.findall(span.text)
    won = re.search(r"\s?원$", span.text)
    part_sep = re.search(r"[조억만](\s?)\d", span.text)
    comma = any("," in n for n, *_ in parts) or all(_num(n) < 1000 for n, *_ in parts)
    units = [u for *_, u in parts]
    total = round(value_krw / UNITS[units[-1]])
    pieces = []
    for u in units:
        size = round(UNITS[u] / UNITS[units[-1]])
        q, total = divmod(total, size)
        if q or (u == units[-1] and not pieces):
            pieces.append(f"{_fmt(int(q), comma)}{parts[0][2]}{u}")
    sep = part_sep.group(1) if part_sep else " "
    return sep.join(pieces) + (won.group(0) if won else "")


def _replace(text: str, spans: list[Span], new_krw: float) -> str:
    for s in sorted(spans, key=lambda x: x.start, reverse=True):
        text = text[:s.start] + render_like(s, new_krw) + text[s.end:]
    return text


def replace_amount(text: str, old_krw: float, new_krw: float) -> tuple[str, int]:
    """Replace every mention of `old_krw` in its own format; returns (text, n_replaced)."""
    spans = find_amounts(text, old_krw)
    return _replace(text, spans, new_krw), len(spans)


def replace_price(text: str, old_krw: float, new_krw: float) -> tuple[str, int]:
    spans = find_prices(text, old_krw)
    return _replace(text, spans, new_krw), len(spans)
