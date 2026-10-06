"""Replication package for the paper: release/replication_data.zip.

Contains the run-level tables (parsed model outputs), firm-level tables, the sample, input
packages (derived from OpenDART public filings), identifiers, fake names, the reviewed Q5
keywords and quiz truth without KRX-derived prices. Excludes raw DART/KRX data, KRX-derived
price files and the call cache (it holds full prompts and responses; available on request).

  python scripts/build_release.py
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.config import PROJECT_ROOT  # noqa: E402

OUT = PROJECT_ROOT / "release" / "replication_data.zip"
PRICE_COLUMNS = ["price", "price_source", "market_cap_krw", "market_cap_source"]


def files() -> list[Path]:
    root = PROJECT_ROOT
    out = sorted((root / "results" / "runs").glob("E*.parquet"))
    out += sorted((root / "results").glob("firm_level*.parquet"))
    out += [root / "data" / "processed" / "sample.parquet",
            root / "data" / "processed" / "fake_names.parquet",
            root / "data" / "processed" / "size_decisions.parquet",
            root / "data" / "processed" / "size_decisions_main.parquet",
            root / "data" / "ground_truth" / "q5_keywords.csv"]
    out += sorted((root / "data" / "processed" / "packages").glob("*.json"))
    out += sorted((root / "data" / "processed" / "identifiers").glob("*.json"))
    out += sorted((root / "data" / "processed" / "e10_filler").glob("*.txt"))
    return [p for p in out if p.exists()]


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    manifest = []
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in files():
            arc = p.relative_to(PROJECT_ROOT).as_posix()
            zf.write(p, arc)
            manifest.append((arc, hashlib.sha256(p.read_bytes()).hexdigest()))
        quiz = pd.read_parquet(PROJECT_ROOT / "data" / "ground_truth" / "quiz_truth.parquet")
        buf = BytesIO()
        quiz.drop(columns=[c for c in PRICE_COLUMNS if c in quiz]).to_parquet(buf, index=False)
        zf.writestr("data/ground_truth/quiz_truth_no_prices.parquet", buf.getvalue())
        zf.writestr("MANIFEST.sha256", "".join(f"{h}  {a}\n" for a, h in manifest))
        zf.writestr("README.txt",
                    "Replication data for 'Do LLM Valuation Agents Read the Filing?' "
                    "(Dong Gyu Park, 2026).\nUnzip at the repository root and follow "
                    "docs/reproduce.md. Input packages are derived from OpenDART public "
                    "filings (source: Financial Supervisory Service, OpenDART).\n"
                    "Licenses: see DATA_LICENSE.md in the repository.\n")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {len(manifest)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
