"""Fake company names for condition D (P4 §5.6, D4.3).

Each sample firm gets one plausible Korean company name, fixed for all experiments and
unique within the sample. A candidate is rejected when it matches any DART-registered name
exactly, or when its normalized Levenshtein similarity to any listed company name (legal
forms and spaces removed) reaches the threshold.
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

from src.conditions.identifiers import strip_legal
from src.config import CONFIG_DIR

THRESHOLD = 0.6


@lru_cache(maxsize=2)
def load_parts(path: Path = CONFIG_DIR / "fake_name_parts.yaml") -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", "", strip_legal(name)).casefold()


def similarity(a: str, b: str, threshold: float = 0.0) -> float:
    """1 - Levenshtein distance / longer length; returns 0.0 early when it cannot reach
    `threshold` (the length gap alone bounds the distance from below)."""
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    longer = max(la, lb)
    if longer == 0 or 1 - abs(la - lb) / longer < threshold:
        return 0.0
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return 1 - prev[lb] / longer


def suffix_set(industry_label: str | None) -> str:
    for pattern, key in load_parts()["industry_map"]:
        if industry_label and re.search(pattern, industry_label):
            return key
    return "general"


def generate_candidates(industry_label: str | None, rng: random.Random, n: int = 50
                        ) -> list[str]:
    parts = load_parts()
    suffixes = parts["suffixes"][suffix_set(industry_label)]
    out: list[str] = []
    for _ in range(n * 4):
        prefix, suffix = rng.choice(parts["prefixes"]), rng.choice(suffixes)
        use_core = suffix in parts.get("core_ok", []) and rng.random() < 0.2
        name = f"{prefix}{rng.choice(parts['cores']) if use_core else ''}{suffix}"
        if name not in out:
            out.append(name)
        if len(out) >= n:
            break
    return out


def nearest(name: str, listed: Iterable[str], threshold: float = THRESHOLD
            ) -> tuple[float, str | None]:
    """(highest similarity, that listed name); stops early once `threshold` is reached."""
    key = normalize_name(name)
    best, best_name = 0.0, None
    for real in listed:
        s = similarity(key, real, best)
        if s > best:
            best, best_name = s, real
            if best >= threshold:
                break
    return best, best_name


def is_acceptable(name: str, listed_names: Iterable[str], all_corp_names: set[str],
                  threshold: float = THRESHOLD) -> bool:
    if normalize_name(name) in all_corp_names:
        return False
    return nearest(name, listed_names, threshold)[0] < threshold


def assign_fake_names(sample: pd.DataFrame, seed: int, listed_names: Iterable[str],
                      all_corp_names: Iterable[str], threshold: float = THRESHOLD
                      ) -> pd.DataFrame:
    """One fake name per firm. `sample` needs firm_id and industry_label columns.

    Returns firm_id, fake_name, industry_label, max_similarity, nearest_real_name.
    """
    listed = sorted({normalize_name(n) for n in listed_names if n})
    every = {normalize_name(n) for n in all_corp_names if n}
    rng = random.Random(seed)
    used: set[str] = set()
    rows = []
    for row in sample.sort_values("firm_id").to_dict("records"):
        chosen = None
        for _ in range(20):
            for cand in generate_candidates(row.get("industry_label"), rng, n=20):
                if cand in used or normalize_name(cand) in every:
                    continue
                sim, near = nearest(cand, listed, threshold)
                if sim < threshold:
                    chosen = (cand, sim, near)
                    break
            if chosen:
                break
        if chosen is None:
            raise RuntimeError(f"no acceptable fake name for {row['firm_id']}")
        used.add(chosen[0])
        rows.append({"firm_id": row["firm_id"], "fake_name": chosen[0],
                     "industry_label": row.get("industry_label"),
                     "max_similarity": chosen[1], "nearest_real_name": chosen[2]})
    return pd.DataFrame(rows)
