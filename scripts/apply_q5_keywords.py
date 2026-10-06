"""Write the reviewed Q5 keywords (data/ground_truth/q5_keywords.csv, column
`main_business`, "|"-separated) into data/ground_truth/quiz_truth.parquet.

  python scripts/apply_q5_keywords.py
  python scripts/run_analysis.py --reuse   # firm tables must be rebuilt: run without --reuse

The P2 truth stage applies the same file when it rebuilds quiz_truth, so a rebuild keeps the
reviewed keywords.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.data.ground_truth import Q5_KEYWORDS, apply_q5_keywords  # noqa: E402
from src.data.p2_pipeline import TRUTH_DIR  # noqa: E402


def main() -> int:
    if not Q5_KEYWORDS.exists():
        print(f"{Q5_KEYWORDS} missing: run scripts/draft_q5_keywords.py and review it first")
        return 1
    path = TRUTH_DIR / "quiz_truth.parquet"
    q = apply_q5_keywords(pd.read_parquet(path))
    q.to_parquet(path, index=False)
    filled = int(q["main_business"].fillna("").str.strip().ne("").sum())
    print(f"main_business filled for {filled}/{len(q)} firms -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
