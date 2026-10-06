"""Frozen-code check for the main run (P8 §2): prompts, perturbations and metrics must be
unchanged since the preregistration tag, both in commits and in the working tree."""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.config import PROJECT_ROOT

TAG = "prereg-v1"
FROZEN_PATHS = ("src/agents/prompts", "src/perturb", "src/metrics")


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                         encoding="utf-8")
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {out.stderr.strip()}")
    return out.stdout


def tag_exists(tag: str = TAG, repo: Path = PROJECT_ROOT) -> bool:
    return bool(_git(repo, "tag", "--list", tag).strip())


def changed_since(tag: str = TAG, paths: tuple[str, ...] = FROZEN_PATHS,
                  repo: Path = PROJECT_ROOT) -> list[str]:
    """Files under `paths` that differ from `tag`: committed or uncommitted edits, deletions,
    and new untracked files (ignored files such as __pycache__ do not count)."""
    if not tag_exists(tag, repo):
        raise RuntimeError(f"tag {tag} does not exist")
    changed = _git(repo, "diff", "--name-only", tag, "--", *paths).split()
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "--", *paths).split()
    return sorted(set(changed) | set(untracked))
