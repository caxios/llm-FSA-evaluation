"""Reproduce the P1 raw data layer.

Examples:
  python scripts/fetch_all.py --stage all
  python scripts/fetch_all.py --stage corpcodes,listing,company --limit 5     # smoke run
  python scripts/fetch_all.py --stage report

Stages run in the order given by --stage (default: all, in pipeline order). Re-running is
cheap: completed API calls are served from data/raw/.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import PROJECT_ROOT, load_config  # noqa: E402
from src.data.coverage import build_report  # noqa: E402
from src.data.dart_client import DartClient  # noqa: E402
from src.data.krx_client import KrxClient  # noqa: E402
from src.data.pipeline import OUT_DIR, STAGES, Context  # noqa: E402
from src.data.price_client import PriceClient  # noqa: E402
from src.data.rate_limit import QuotaExhausted  # noqa: E402
from src.utils.logging import setup_logging  # noqa: E402

log = logging.getLogger("fetch_all")
REPORT = PROJECT_ROOT / "docs" / "data_coverage_report.md"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--stage", default="all",
                    help=f"comma-separated: {','.join(STAGES)},report or 'all'")
    ap.add_argument("--limit", type=int, default=None, help="process only the first N firms")
    ap.add_argument("--refresh", action="store_true", help="ignore raw caches (re-download)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    stages = list(STAGES) + ["report"] if args.stage == "all" else args.stage.split(",")
    unknown = [s for s in stages if s not in STAGES and s != "report"]
    if unknown:
        ap.error(f"unknown stage(s): {unknown}")

    log_file = setup_logging("fetch_all")
    cfg = load_config()
    krx = KrxClient(refresh=args.refresh)
    ctx = Context(cfg=cfg, dart=DartClient(refresh=args.refresh), krx=krx,
                  prices=PriceClient(krx), out_dir=args.out_dir, limit=args.limit)
    log.info("stages=%s limit=%s t_post=%s log=%s", stages, args.limit, ctx.t_post, log_file)

    try:
        for stage in stages:
            if stage == "report":
                continue
            log.info("=== stage %s ===", stage)
            STAGES[stage](ctx)
    except QuotaExhausted:
        return 2
    finally:
        log.info("OpenDART calls used today: %d", ctx.dart.limiter.used_today())

    if "report" in stages:
        REPORT.write_text(build_report(args.out_dir, ctx.t_post, ctx.fiscal_year, ctx.notes),
                          encoding="utf-8")
        log.info("wrote %s", REPORT)
    for note in ctx.notes:
        log.warning("NOTE: %s", note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
