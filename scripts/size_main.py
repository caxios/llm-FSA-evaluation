"""P8 module 3: E3 sizes for all firms.

Non-pilot firms: `decide_size` from the main-run E0 cell (condition C, k = 1 of E0/E2).
Pilot firms keep their preregistered pilot sizes (config/main_run.yaml `pilot_sizes`).
Writes `main_sizes` and prints a status summary.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.analysis.pilot_report import size_table  # noqa: E402
from src.config import CONFIG_DIR, PROJECT_ROOT, load_config  # noqa: E402
from src.metrics.synthetic_validation import sizes_from  # noqa: E402
from src.runner.jobs import SampleStore  # noqa: E402
from src.runner.logger import RUNS_DIR  # noqa: E402

MAIN = yaml.safe_load((CONFIG_DIR / "main_run.yaml").read_text(encoding="utf-8"))


def main() -> int:
    cfg, store = load_config(), SampleStore()
    frames = [pd.read_parquet(RUNS_DIR / f"{m}.parquet") for m in ("E0", "E2")
              if (RUNS_DIR / f"{m}.parquet").exists()]
    runs = pd.concat(frames, ignore_index=True).drop_duplicates("job_id")
    runs = runs[(runs["tag"] == MAIN["tag"])
                & (runs["prompt_version"] == MAIN["prompt_version"])
                & (runs["agent_structure"] == MAIN["agent"])]
    pilot = pd.read_parquet(PROJECT_ROOT / MAIN["pilot_sizes"])
    new = size_table(sizes_from(runs[~runs["firm_id"].isin(set(pilot["firm_id"]))],
                                store, cfg))
    out = pd.concat([pilot, new], ignore_index=True).sort_values(["firm_id", "perturbation"])
    path = PROJECT_ROOT / MAIN["main_sizes"]
    out.to_parquet(path, index=False)
    print(out.groupby(["perturbation", "status"]).size().to_string())
    missing = sorted(set(store.sample.index) - set(out["firm_id"]))
    print(f"wrote {path} ({out['firm_id'].nunique()} firms; no E0 cell: {missing})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
