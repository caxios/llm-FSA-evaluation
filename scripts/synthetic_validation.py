"""P6 Step 9: synthetic validation on the 150 sample packages (no API calls).

  python scripts/synthetic_validation.py [--reps 10] [--noise 0.05] [--firms L001,...]

Runs every synthetic agent through the job builders, the runner and the metrics, checks the
pass bands of P6 §5.3 and the bootstrap CI coverage, and writes
docs/synthetic_validation.md. Exit code 1 if any check fails.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import load_config  # noqa: E402
from src.metrics.synthetic_validation import ci_coverage, report, validate  # noqa: E402
from src.runner.jobs import SampleStore  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "synthetic_validation.md"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--noise", type=float, default=0.05)
    ap.add_argument("--n-boot", type=int, default=200)
    ap.add_argument("--firms", default=None)
    args = ap.parse_args()
    t0 = time.time()
    store = SampleStore()
    firms = args.firms.split(",") if args.firms else sorted(store.sample.index)
    res = validate(load_config(), store, firms, reps=args.reps, noise=args.noise,
                   n_boot=args.n_boot)
    cov = ci_coverage(n_firms=200, n=args.reps)
    text = report(res, cov, f"Synthetic Validation (P6) — {len(firms)} sample firms")
    text += f"\nRuntime: {time.time() - t0:.0f} s\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0 if res.passed and 0.93 <= cov <= 0.97 else 1


if __name__ == "__main__":
    sys.exit(main())
