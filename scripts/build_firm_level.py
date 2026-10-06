"""Rebuild results/firm_level.parquet from the main-run tables (P8 exit criterion).

  python scripts/build_firm_level.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.conditions import pipeline as pl  # noqa: E402
from src.config import CONFIG_DIR, PROJECT_ROOT  # noqa: E402
from src.metrics.firm_table import build_firm_table, load_runs, write_firm_table  # noqa: E402

MAIN = yaml.safe_load((CONFIG_DIR / "main_run.yaml").read_text(encoding="utf-8"))
TRUTH = PROJECT_ROOT / "data" / "ground_truth"


def main() -> int:
    runs = load_runs()
    runs = runs[(runs["tag"] == MAIN["tag"]) & (runs["model_key"] == MAIN["model"])]
    sample = pl.load_sample()
    ids = {f: pl.load_identifiers(f) for f in sample["firm_id"]}
    table = build_firm_table(runs.drop_duplicates("job_id"), sample=sample,
                             quiz_truth=pd.read_parquet(TRUTH / "quiz_truth.parquet"),
                             identifiers=ids,
                             anchors=pd.read_parquet(TRUTH / "anchor_prices.parquet"))
    print(f"wrote {write_firm_table(table)} ({len(table)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
