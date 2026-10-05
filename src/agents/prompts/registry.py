"""Prompt registry: version -> file and sha256 (P5 §5.2).

The sha256 of every prompt goes into each run record and the preregistration. Line
endings are normalized to LF before hashing so checkouts on different systems agree.
`FROZEN` pins hashes once the preregistration is tagged (`prereg-v1`); a test fails if a
frozen prompt changes.
"""

from __future__ import annotations

import hashlib
from functools import cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent

PROMPTS: dict[str, str] = {
    "valuation_system_v1": "valuation_system_v1.txt",
    "valuation_system_v1_instr": "valuation_system_v1_instr.txt",
    "valuation_user_v1": "valuation_user_v1.txt",
    "tool_system_v1": "tool_system_v1.txt",
    "identification_v1": "identification_v1.txt",
    "memory_quiz_v1": "memory_quiz_v1.txt",
}

# prompt_version (as used in run records) -> system prompt key
SYSTEM_FOR_VERSION = {"v1": "valuation_system_v1", "v1_instr": "valuation_system_v1_instr"}

# Filled when the preregistration is tagged (P7): {key: sha256}.
FROZEN: dict[str, str] = {}


@cache
def get_prompt(key: str) -> tuple[str, str]:
    """(text, sha256) of a registered prompt."""
    if key not in PROMPTS:
        raise KeyError(f"unknown prompt '{key}'; known: {sorted(PROMPTS)}")
    text = (PROMPT_DIR / PROMPTS[key]).read_text(encoding="utf-8").replace("\r\n", "\n")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def prompt_hashes() -> dict[str, str]:
    return {k: get_prompt(k)[1] for k in PROMPTS}
