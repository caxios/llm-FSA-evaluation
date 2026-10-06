"""Filler text for E10 (information position, P9 §5.5).

The filler is the firm's own annual-report text from sections that do not affect value:
V (external auditor), VI (board and other bodies), VIII (executives and employees), then
VII (shareholders) if more text is needed. Lines that mention convertible bonds or other
securities that could carry dilution information are removed, so that the CB block is the
only dilution information in the prompt. Every firm's filler is cut to the same length.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.data.cb_parser import load_soup, main_document

SECTIONS = ("V.", "VI.", "VIII.", "VII.")
FILLER_CHARS = 13_000         # the shortest of the 20 E10 firms has 13,173
DROP = re.compile(r"전환사채|사채|신주인수권|전환가액|전환청구|교환사채|희석|CB\b|BW\b")


def section_texts(doc_dir: Path, rcept_no: str) -> dict[str, str]:
    soup = load_soup(main_document(doc_dir, rcept_no))
    out = {}
    for sec in soup.find_all("section-1"):
        title = sec.find("title")
        if title is None:
            continue
        name = title.get_text(" ", strip=True)
        key = name.split(" ", 1)[0]
        lines = [re.sub(r"\s+", " ", ln).strip() for ln in sec.get_text("\n").split("\n")]
        out[key] = "\n".join(ln for ln in lines if ln and not DROP.search(ln))
    return out


def build_filler(doc_dir: Path, rcept_no: str, n_chars: int = FILLER_CHARS) -> str:
    """Filler of exactly `n_chars` characters (cut at the last line break before the limit
    and padded with spaces), or shorter when the report has too little text (raises)."""
    texts = section_texts(doc_dir, rcept_no)
    body = "\n".join(texts[k] for k in SECTIONS if k in texts)
    if len(body) < n_chars:
        raise ValueError(f"only {len(body)} filler characters (< {n_chars})")
    cut = body[:n_chars]
    cut = cut[:cut.rfind("\n")] if "\n" in cut else cut
    return cut + " " * (n_chars - len(cut))
