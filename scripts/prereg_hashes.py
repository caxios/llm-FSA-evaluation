"""Hashes for the preregistration (P7 §6.2): sample, size decisions, prompts, configs.

  python scripts/prereg_hashes.py            # print the markdown block
  python scripts/prereg_hashes.py --pin      # also write registry.FROZEN for the main prompts

`--pin` is the freeze step: the prompts used by the main run (config/main_run.yaml) get
their sha256 written into src/agents/prompts/registry.py, so any later edit fails the
prompt-hash test and scripts/check_frozen.py.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from src.agents.prompts import registry  # noqa: E402
from src.config import CONFIG_DIR, PROJECT_ROOT  # noqa: E402

MAIN = yaml.safe_load((CONFIG_DIR / "main_run.yaml").read_text(encoding="utf-8"))
FILES = ["data/processed/sample.parquet", "data/processed/size_decisions.parquet",
         "data/processed/fake_names.parquet", "data/ground_truth/cb_truth.parquet",
         "config/experiments.yaml", "config/models.yaml", "config/main_run.yaml",
         "config/pilot.yaml"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main_prompts() -> list[str]:
    v = MAIN["prompt_version"]
    return [registry.TOOL_FOR_VERSION[v], registry.SYSTEM_FOR_VERSION[v],
            registry.SYSTEM_FOR_VERSION[f"{v}_instr"], "valuation_user_v1",
            "identification_v1", "memory_quiz_v1"]


def pin(keys: list[str]) -> None:
    path = Path(registry.__file__)
    text = path.read_text(encoding="utf-8")
    body = "".join(f'    "{k}": "{registry.get_prompt(k)[1]}",\n' for k in keys)
    new, n = re.subn(r"FROZEN: dict\[str, str\] = \{.*?\}\n",
                     "FROZEN: dict[str, str] = {\n" + body + "}\n", text, flags=re.S)
    if n != 1:
        raise SystemExit("FROZEN block not found in registry.py")
    path.write_text(new, encoding="utf-8")
    print(f"pinned {len(keys)} prompts in {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--pin", action="store_true")
    args = ap.parse_args()
    print("| File | sha256 |\n|---|---|")
    for f in FILES:
        p = PROJECT_ROOT / f
        print(f"| `{f}` | {sha(p) if p.exists() else '(missing)'} |")
    print("\n| Prompt | File | sha256 |\n|---|---|---|")
    for k in main_prompts():
        print(f"| {k} | `{registry.PROMPTS[k]}` | {registry.get_prompt(k)[1]} |")
    if args.pin:
        pin(main_prompts())
    return 0


if __name__ == "__main__":
    sys.exit(main())
