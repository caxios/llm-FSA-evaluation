"""Title-free figures for the paper (paper/figures), from the saved analysis outputs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.analysis import figures  # noqa: E402
from src.config import PROJECT_ROOT  # noqa: E402

T = PROJECT_ROOT / "results" / "tables"


def main() -> int:
    figures.TITLES = False
    figures.OUT_DIR = PROJECT_ROOT / "paper" / "figures"
    ft = pd.read_parquet(PROJECT_ROOT / "results" / "firm_level_main.parquet")
    figures.f2_beta_by_group(ft)
    figures.f3_decomposition(pd.read_csv(T / "T5_decomposition.csv", comment="#"))
    figures.f4_memory_scatter(ft)
    figures.f6_stages(pd.read_csv(T / "T11_structures.csv", comment="#"))
    figures.f8_pooled(pd.read_csv(T / "T14_pooled_R.csv", comment="#"))
    print(sorted(p.name for p in figures.OUT_DIR.glob("*.pdf")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
