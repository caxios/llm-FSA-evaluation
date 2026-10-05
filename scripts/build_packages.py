"""Reproduce P2: packages, sample, ground truth.

Examples:
  python scripts/build_packages.py --stage all
  python scripts/build_packages.py --stage select,packages,truth,report
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import load_config  # noqa: E402
from src.data.dart_client import DartClient  # noqa: E402
from src.data.p2_inputs import P1Data  # noqa: E402
from src.data.p2_pipeline import STAGES, P2Context  # noqa: E402
from src.utils.logging import setup_logging  # noqa: E402

log = logging.getLogger("build_packages")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--stage", default="all", help=f"comma-separated: {','.join(STAGES)} or all")
    args = ap.parse_args()
    stages = list(STAGES) if args.stage == "all" else args.stage.split(",")
    unknown = [s for s in stages if s not in STAGES]
    if unknown:
        ap.error(f"unknown stage(s): {unknown}")
    setup_logging("build_packages")
    ctx = P2Context(cfg=load_config(), dart=DartClient(), data=P1Data.load())
    for stage in stages:
        log.info("=== stage %s ===", stage)
        STAGES[stage](ctx)
    log.info("OpenDART calls used today: %d", ctx.dart.limiter.used_today())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
