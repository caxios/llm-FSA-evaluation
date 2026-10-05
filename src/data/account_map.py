"""Map DART accounts to canonical IDs and categories (config/account_map.yaml)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from src.config import CONFIG_DIR

UNMAPPED_ID = "-표준계정코드 미사용-"
_STRIP = re.compile(r"[\s()（）\[\]·ㆍ,]")
# Outline numbering some filers put before labels: "V. 영업이익", "ⅩIII. 총포괄손실", "1. 판매비"
_NUMBERING = re.compile(r"^(?:[IVXLⅠ-Ⅻⅰ-ⅻ]+|\d+|[가-하])\.")


def normalize_label(label: str) -> str:
    """'이익잉여금(결손금)' -> '이익잉여금결손금'; 'V. 영업이익' -> '영업이익'."""
    return _NUMBERING.sub("", _STRIP.sub("", label or ""))


@dataclass(frozen=True)
class CategoryRule:
    name: str
    sections: tuple[str, ...]
    id_pattern: re.Pattern
    label_pattern: re.Pattern


class AccountMap:
    def __init__(self, spec: dict):
        self.unique: dict[str, dict[str, tuple[set[str], set[str]]]] = {}
        for code, entries in spec["unique"].items():
            self.unique[code] = {
                canonical: (set(e.get("ids") or []),
                            {normalize_label(x) for x in e.get("labels") or []})
                for canonical, e in entries.items()
            }
        self.rules = [
            CategoryRule(r["name"], tuple(r["sections"]), re.compile(r["id"]),
                         re.compile(r["label"]))
            for r in spec["categories"]
        ]

    def unique_candidates(self, code: str, account_id: str, label: str) -> list[str]:
        """Canonical IDs this line could be; an ID match beats a label match."""
        entries = self.unique.get(code, {})
        by_id = [c for c, (ids, _) in entries.items() if account_id in ids]
        if by_id:
            return by_id
        norm = normalize_label(label)
        return [c for c, (_, labels) in entries.items() if norm in labels]

    def category(self, account_id: str, label: str, section: str | None) -> str | None:
        if section is None:
            return None
        norm = normalize_label(label)
        has_id = account_id and account_id != UNMAPPED_ID
        for rule in self.rules:
            if section not in rule.sections:
                continue
            if has_id and rule.id_pattern.search(account_id):
                return rule.name
            if rule.label_pattern.search(norm):
                return rule.name
        return None


@lru_cache(maxsize=4)
def load_account_map(path: Path = CONFIG_DIR / "account_map.yaml") -> AccountMap:
    return AccountMap(yaml.safe_load(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=4)
def load_ancestry(path: Path = CONFIG_DIR / "ancestry.yaml") -> dict[str, dict[str, str]]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def load_industry_labels(path: Path = CONFIG_DIR / "industry_labels.yaml") -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {str(k).zfill(2): v for k, v in data["divisions"].items()}
