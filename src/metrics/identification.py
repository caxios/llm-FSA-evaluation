"""Identification rate (E5): share of guesses that name the firm.

A guess is correct when the ticker matches, or when a normalized variant of the guessed
name equals a normalized variant of the firm's names (P4 identifier dictionary).
"""

from __future__ import annotations

import re

import pandas as pd

from src.conditions.identifiers import FirmIdentifiers, name_variants
from src.metrics.cells import AGENT_KEYS, output


def _norm(s: str) -> str:
    return re.sub(r"[\s()（）.,·]", "", s).casefold()


def is_correct(guess: dict, ids: FirmIdentifiers) -> bool:
    ticker = re.sub(r"\D", "", str(guess.get("guess_ticker") or ""))
    if ticker and ids.ticker and ticker.zfill(6) == ids.ticker.zfill(6):
        return True
    name = guess.get("guess_name")
    if not name:
        return False
    targets = {_norm(n) for n in name_variants(*ids.names)} | {_norm(n) for n in ids.names}
    return bool({_norm(n) for n in name_variants(name)} & targets)


def identification_rate(responses: pd.DataFrame, identifiers: dict[str, FirmIdentifiers]
                        ) -> pd.DataFrame:
    rows = []
    for _, r in responses[responses["valid"].eq(True)].iterrows():
        ids = identifiers.get(r["firm_id"])
        if ids is None:
            continue
        rows.append({"firm_id": r["firm_id"], "condition": r["condition"],
                     **{k: r[k] for k in AGENT_KEYS}, "correct": is_correct(output(r), ids)})
    if not rows:
        return pd.DataFrame(columns=["firm_id", "condition", *AGENT_KEYS, "id_rate", "n"])
    df = pd.DataFrame(rows)
    g = df.groupby(["firm_id", "condition", *AGENT_KEYS])["correct"]
    return pd.DataFrame({"id_rate": g.mean(), "n": g.size()}).reset_index()
