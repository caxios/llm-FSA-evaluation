"""P8 entry check: prompts, perturbations and metrics unchanged since `prereg-v1`.

  python scripts/check_frozen.py [--tag prereg-v1]

Also checks that every prompt pinned in `registry.FROZEN` still has its registered sha256.
Exit code 0 = frozen, 1 = changed (files listed), 2 = tag missing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.prompts.registry import FROZEN, get_prompt  # noqa: E402
from src.runner.frozen import TAG, changed_since, tag_exists  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--tag", default=TAG)
    args = ap.parse_args()
    if not tag_exists(args.tag):
        print(f"tag {args.tag} does not exist: freeze the preregistration first (P7 step 9)")
        return 2
    changed = changed_since(args.tag)
    bad_hash = [k for k, sha in FROZEN.items() if get_prompt(k)[1] != sha]
    for f in changed:
        print(f"changed since {args.tag}: {f}")
    for k in bad_hash:
        print(f"prompt hash differs from the registered one: {k}")
    if not FROZEN:
        print("warning: registry.FROZEN is empty (no prompt hashes pinned)")
    if changed or bad_hash:
        return 1
    print(f"frozen: no changes under the frozen paths since {args.tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
