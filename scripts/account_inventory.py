"""Inventory of DART account IDs and labels across the P1 universe (P2 Step 2.2).

Writes data/processed/p2/account_inventory.parquet with one row per
(sj_div, account_id, account_nm) and the number of firms using it, and prints the most
common IDs per statement. Used to draft config/account_map.yaml.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

FS_ROOT = ROOT / "data" / "raw" / "dart" / "fs"
P1 = ROOT / "data" / "processed" / "p1"
OUT = ROOT / "data" / "processed" / "p2" / "account_inventory.parquet"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    status = pd.read_parquet(P1 / "fs_status.parquet").dropna(subset=["fs_div"])
    counts: Counter = Counter()
    n_firms = 0
    for row in status.itertuples(index=False):
        path = FS_ROOT / row.corp_code / f"{row.fiscal_year}_11011_{row.fs_div}.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        n_firms += 1
        seen = set()
        for r in body.get("list", []):
            sj = "IS" if r["sj_div"] == "CIS" else r["sj_div"]
            if sj not in ("BS", "IS", "CF"):
                continue
            key = (sj, r["account_id"], r["account_nm"].strip())
            if key not in seen:
                seen.add(key)
                counts[key] += 1
    df = pd.DataFrame([(*k, v) for k, v in counts.items()],
                      columns=["sj_div", "account_id", "account_nm", "n_firms"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"firms={n_firms} distinct (sj, id, label)={len(df)}")
    by_id = df.groupby(["sj_div", "account_id"])["n_firms"].sum().reset_index()
    for sj in ("BS", "IS", "CF"):
        top = by_id[by_id["sj_div"] == sj].sort_values("n_firms", ascending=False).head(70)
        print(f"\n== {sj}")
        for r in top.itertuples(index=False):
            label = (df[(df.sj_div == sj) & (df.account_id == r.account_id)]
                     .sort_values("n_firms", ascending=False)["account_nm"].iloc[0])
            print(f"{r.n_firms:5d}  {r.account_id[:70]:70s} {label}")


if __name__ == "__main__":
    main()
