"""Generic industry labels for conditions B/D/C (P4 §5.7, D4.2).

The label is the KSIC division (2-digit) label from config/industry_labels.yaml. When a
division has fewer than `min_peers` firms in the universe, the broader KSIC section label is
used instead: a label that fits only a handful of listed firms (tobacco, air transport,
petroleum refining) would nearly identify the firm.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import yaml

from src.config import CONFIG_DIR


@lru_cache(maxsize=4)
def _load(path: Path = CONFIG_DIR / "industry_labels.yaml") -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def division_labels() -> dict[str, str]:
    return {str(k).zfill(2): v for k, v in _load()["divisions"].items()}


def section_label(ksic2: str) -> str | None:
    for spec in _load()["sections"].values():
        lo, hi = spec["range"]
        if lo <= ksic2 <= hi:
            return spec["label"]
    return None


def label_for(ksic2: str | None, peer_counts: Mapping[str, int] | None = None) -> str | None:
    """Industry label for a KSIC division; `peer_counts` = universe firms per division."""
    if not ksic2:
        return None
    ksic2 = str(ksic2).zfill(2)[:2]
    label = division_labels().get(ksic2)
    min_peers = int(_load().get("min_peers", 0))
    if peer_counts is not None and peer_counts.get(ksic2, 0) < min_peers:
        return section_label(ksic2) or label
    return label
