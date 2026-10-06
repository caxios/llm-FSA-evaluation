"""E10 filler texts for the extension E8 firms (config/extensions.yaml `e8_firms`).

Reads each firm's FY2025 annual report from the OpenDART document cache (fetched in P1
for KOSDAQ firms; downloaded if missing) and writes data/processed/e10_filler/{firm}.txt.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from src.conditions import pipeline as pl  # noqa: E402
from src.config import CONFIG_DIR  # noqa: E402
from src.data.dart_client import DartClient  # noqa: E402
from src.data.filler import FILLER_CHARS, build_filler  # noqa: E402

EXT = yaml.safe_load((CONFIG_DIR / "extensions.yaml").read_text(encoding="utf-8"))


def main() -> int:
    out = pl.PROCESSED / "e10_filler"
    out.mkdir(parents=True, exist_ok=True)
    dart, failed = DartClient(), []
    for fid in EXT["e8_firms"]:
        rcept = pl.load_package(fid).meta.source_rcept_no
        try:
            text = build_filler(dart.document(rcept), rcept)
        except (ValueError, FileNotFoundError) as e:
            failed.append(f"{fid}: {e}")
            continue
        (out / f"{fid}.txt").write_text(text, encoding="utf-8")
        print(f"{fid}: {len(text)} chars")
    for f in failed:
        print("FAILED", f)
    print(f"filler length {FILLER_CHARS}; written {len(EXT['e8_firms']) - len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
