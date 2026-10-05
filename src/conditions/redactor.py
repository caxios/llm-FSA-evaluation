"""Redaction of direct identifiers from text fields (P4 §5.4).

Replacements (one pass, longest match first; ties go to the earlier rule):
  1 investee / affiliate names  -> "관계회사" ("종속회사" when the text is about subsidiaries)
  2 firm names and group names  -> "당사"
  3 brands                      -> "주요 제품"
  4 ticker, homepage, CEO, address tokens -> removed
  5 segment names               -> "부문1", "부문2", ... in first-seen order
Matching is NFC-normalized and case-insensitive. Terms of two characters or fewer, and
Latin-letter terms, match only as whole tokens (not inside a longer word); Korean terms of
three or more characters also match with spaces between their characters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel

from src.conditions.identifiers import FirmIdentifiers, nfc

SUBSIDIARY_CONTEXT = re.compile(r"종속")
_WORD = r"0-9A-Za-z가-힣"


class Redaction(BaseModel):
    field: str
    original: str
    replacement: str
    rule: str


@dataclass(frozen=True)
class _Term:
    text: str
    rule: str
    priority: int


def _terms(ids: FirmIdentifiers) -> list[_Term]:
    spec = [("investee", 1, ids.investees), ("name", 2, ids.names),
            ("group", 2, ids.group_names), ("brand", 3, ids.brands),
            ("ticker", 4, [ids.ticker] if ids.ticker else []),
            ("homepage", 4, [ids.homepage] if ids.homepage else []),
            ("ceo", 4, ids.ceo), ("address", 4, ids.address_tokens),
            ("segment", 5, ids.segments)]
    seen: dict[str, _Term] = {}
    for rule, prio, items in spec:
        for t in items:
            t = nfc(t).strip()
            if not re.search(r"[0-9A-Za-z가-힣]", t):  # placeholders such as "-"
                continue
            if t.casefold() not in seen:
                seen[t.casefold()] = _Term(t, rule, prio)
    return sorted(seen.values(), key=lambda t: (-len(t.text), t.priority))


def _pattern(term: str) -> str:
    chars = [re.escape(c) for c in term]
    body = r"\s*".join(chars) if len(term) >= 3 and re.search("[가-힣]", term) else "".join(chars)
    whole = len(term) <= 2 or re.fullmatch(r"[0-9A-Za-z.&\- ]+", term)
    if whole:
        return rf"(?<![{_WORD}]){body}(?![{_WORD}])"
    return body


def find_identifiers(text: str, ids: FirmIdentifiers,
                     rules: tuple[str, ...] = ("investee", "name", "group", "brand", "ticker",
                                               "homepage", "ceo")) -> list[tuple[str, str]]:
    """(rule, matched text) for every identifier left in `text` (automated leak check).
    Address tokens are excluded by default: city names are common words in labels."""
    text = nfc(text)
    out = []
    for term in _terms(ids):
        if term.rule not in rules:
            continue
        for m in re.finditer(_pattern(term.text), text, re.IGNORECASE):
            out.append((term.rule, m.group(0)))
    return out


def redact_text(text: str, ids: FirmIdentifiers, field: str = "text",
                segment_map: dict[str, str] | None = None) -> tuple[str, list[Redaction]]:
    """Return the redacted text and the log of replacements.

    `segment_map` carries segment numbering across the fields of one package, so the same
    segment gets the same placeholder everywhere.
    """
    text = nfc(text)
    terms = _terms(ids)
    if not terms:
        return text, []
    segments = segment_map if segment_map is not None else {}
    by_group = {f"t{i}": t for i, t in enumerate(terms)}
    regex = re.compile("|".join(f"(?P<{g}>{_pattern(t.text)})" for g, t in by_group.items()),
                       re.IGNORECASE)
    log: list[Redaction] = []

    def repl(m: re.Match) -> str:
        term = by_group[m.lastgroup or ""]
        if term.rule == "investee":
            new = "종속회사" if SUBSIDIARY_CONTEXT.search(text) else "관계회사"
        elif term.rule in ("name", "group"):
            new = "당사"
        elif term.rule == "brand":
            new = "주요 제품"
        elif term.rule == "segment":
            key = term.text.casefold()
            segments.setdefault(key, f"부문{len(segments) + 1}")
            new = segments[key]
        else:
            new = ""
        log.append(Redaction(field=field, original=m.group(0), replacement=new, rule=term.rule))
        return new

    out = regex.sub(repl, text)
    if log:
        out = re.sub(r"\s{2,}", " ", out).strip()
        out = re.sub(r"\(\s*\)", "", out).strip()
    return out, log
