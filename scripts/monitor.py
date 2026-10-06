"""P8 batch monitor (P8 §5.3, §5.5).

  python scripts/monitor.py --batch E2-L        # module E2, group L
  python scripts/monitor.py --batch E6          # whole module

Reads results/runs/{module}.parquet (main-run tag and prompt from config/main_run.yaml),
prints the stop-threshold checks, appends a dated line to docs/run_journal.md and rewrites
results/qa/main_run_qa.md for every module with main-run records. Exit code 3 when a
pause/halt threshold is hit.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.analysis.pilot_report import md_table  # noqa: E402
from src.config import CONFIG_DIR, PROJECT_ROOT, load_config  # noqa: E402
from src.runner.logger import RUNS_DIR  # noqa: E402
from src.runner.monitor import (  # noqa: E402
    anomaly_rate,
    batch_checks,
    cell_completeness,
    extreme_values,
    spend_usd,
)

MAIN = yaml.safe_load((CONFIG_DIR / "main_run.yaml").read_text(encoding="utf-8"))
QA = PROJECT_ROOT / "results" / "qa" / "main_run_qa.md"
JOURNAL = PROJECT_ROOT / "docs" / "run_journal.md"
MODULES = ("E6", "E0", "E2", "E5", "E3", "E7", "E8")


def runs_for(module: str, tag: str) -> pd.DataFrame:
    path = RUNS_DIR / f"{module}.parquet"
    if not path.exists():
        return pd.DataFrame()
    r = pd.read_parquet(path)
    keep = (r["tag"] == tag) & (r["model_key"] == MAIN["model"])
    if module not in ("E5", "E6"):   # quiz/identification prompts have no valuation version
        keep &= (r["prompt_version"] == MAIN["prompt_version"]) \
            & (r["agent_structure"] == MAIN["agent"])
    return r[keep]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--batch", required=True, help="MODULE or MODULE-GROUP, e.g. E2-L")
    args = ap.parse_args()
    module, _, group = args.batch.upper().partition("-")
    mcfg = load_config().require_model(MAIN["model"])
    runs = runs_for(module, MAIN["tag"])
    if group and len(runs):
        runs = runs[runs["group"] == group]
    if runs.empty:
        print(f"no main-run records for {args.batch}")
        return 1
    pilot = runs_for(module, "pilot")
    spent = 0.0
    for m in MODULES:
        r = runs_for(m, MAIN["tag"])
        spent += spend_usd(r, mcfg) if len(r) else 0.0
    alerts = batch_checks(runs, pilot_anomaly=anomaly_rate(pilot) if len(pilot) else None,
                          spent=spent, budget=MAIN.get("budget_usd"), before_e8=module != "E8")
    stop = False
    for a in alerts:
        flag = f"TRIGGERED ({a.action})" if a.triggered else "ok"
        print(f"{a.metric:22s} {a.value!s:>24.24s}  {a.threshold:28s} {flag}")
        stop |= a.triggered and a.action in ("pause", "halt")
    print(f"cumulative spend ${spent:,.2f}")

    if not JOURNAL.exists():
        JOURNAL.write_text("# Run Journal (P8)\n\nDated notes: batches, incidents, spend.\n\n",
                           encoding="utf-8")
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(f"- {datetime.now():%Y-%m-%d %H:%M} monitor {args.batch}: {len(runs)} runs, "
                f"valid {runs['valid'].mean():.1%}, cumulative spend ${spent:,.2f}"
                f"{'; STOP THRESHOLD HIT' if stop else ''}\n")
    write_qa()
    return 3 if stop else 0


def write_qa() -> None:
    out = ["# Main-run QA (P8 §5.5)", "", f"- Generated: {datetime.now():%Y-%m-%d %H:%M}", ""]
    for m in MODULES:
        r = runs_for(m, MAIN["tag"])
        if r.empty:
            continue
        cells = cell_completeness(r)
        low = cells[cells["validity"] < 0.7]
        val = r[r["schema_name"].fillna("valuation") == "valuation"]
        ext = extreme_values(val) if len(val) else pd.DataFrame()
        ok = val[val["valid"].eq(True)]
        nonpos = float((ok["value_per_share"] <= 0).mean()) if len(ok) else float("nan")
        out += [f"## {m}", "", f"- runs {len(r)}; valid {r['valid'].mean():.1%}; cells "
                f"{len(cells)}; low-validity cells {len(low)}; non-positive share "
                f"{nonpos:.1%}; extreme values {len(ext)}", ""]
        if len(low):
            out += ["Low-validity cells:", "", md_table(low), ""]
        if len(ext):
            out += ["Extreme values (> 10x the cell median; review, do not remove):", "",
                    md_table(ext, ["job_id", "firm_id", "condition", "perturbation_type",
                                   "value_per_share"]), ""]
    QA.parent.mkdir(parents=True, exist_ok=True)
    QA.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
