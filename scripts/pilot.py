"""P7 pilot runner (KOSDAQ-independent part: dev set and pilot L).

  python scripts/pilot.py dev [--prompt v1] [--dry-run]   # prompt iteration on the dev set
  python scripts/pilot.py e0|e2|e6 [--dry-run]            # pilot L modules (tag "pilot")
  python scripts/pilot.py size                             # E0 -> size_decisions.parquet
  python scripts/pilot.py e3 [--dry-run]                   # cash at the rule size + tiers
  python scripts/pilot.py report                           # docs/pilot_report.md

Settings come from config/pilot.yaml. All calls go through the cached runner, so reruns
are free and identical requests across stages (E0 vs E2 k = 1, condition C) are one call.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.analysis.pilot_report import (  # noqa: E402
    cost_estimate,
    evaluate,
    md_table,
    render,
    size_table,
)
from src.config import CONFIG_DIR, PROJECT_ROOT, load_config  # noqa: E402
from src.experiments import builders as b  # noqa: E402
from src.perturb.base import book_equity  # noqa: E402
from src.perturb.sizing import SizeDecision, decide_size  # noqa: E402
from src.runner.cache import CallCache  # noqa: E402
from src.runner.jobs import JobSpec, SampleStore  # noqa: E402
from src.runner.logger import RUNS_DIR  # noqa: E402
from src.runner.run import Runner, make_agent, write_table  # noqa: E402

PILOT = yaml.safe_load((CONFIG_DIR / "pilot.yaml").read_text(encoding="utf-8"))
SIZES = PROJECT_ROOT / "data" / "processed" / "size_decisions.parquet"
REPORT = PROJECT_ROOT / "docs" / "pilot_report.md"


def run(specs: list[JobSpec], store, dry: bool, table: str):
    cfg = load_config()
    agent, _, _ = make_agent(PILOT["agent"], PILOT["model"], cfg)
    mcfg = cfg.require_model(PILOT["model"])
    s = Runner(agent, CallCache(), max_workers=mcfg.max_concurrency).run(
        specs, store, dry_run=dry, cfg=mcfg)
    total = s.cached + s.executed + s.pending
    print(f"{table}: requests {total}; cached {s.cached}; executed {s.executed}; "
          f"pending {s.pending}; skipped {len(s.stats.skipped)}")
    if dry:
        print(f"  estimated ${sum(c.usd for c in s.cost):.2f}")
    elif s.records:
        write_table(s.records, table)
        print(f"  valid {sum(r.valid for r in s.records)}/{len(s.records)}")
    return s


def common(prompt: str) -> dict:
    return {"agent_structure": PILOT["agent"], "model_key": PILOT["model"],
            "prompt_version": prompt, "tag": "pilot"}


def stage_dev(args) -> None:
    cfg, store = load_config(), SampleStore(dev=True)
    firms, reps = PILOT["dev"]["firms"], PILOT["dev"]["reps"]
    c = common(args.prompt) | {"tag": f"dev-{args.prompt}"}
    specs = b.e0_e2(cfg, store, firms, reps=reps, conditions=["C"], **c)
    e8 = b.e8(cfg, store, firms, reps=reps, **c)
    for s in e8:
        s.perturbations = [("cb_v0", {})]
    for s in specs + e8:
        s.experiment = f"DEV_{s.experiment}"
    run(specs + e8, store, args.dry_run, "DEV")
    if not args.dry_run:
        runs = pd.read_parquet(RUNS_DIR / "DEV.parquet")
        runs = runs[runs["prompt_version"] == args.prompt]
        pkgs = {f: store.package(f) for f in firms}
        res = evaluate(runs, cfg, packages=pkgs, n_boot=200)
        print(f"  compliance {runs['valid'].mean():.1%}; "
              f"unit slips {res.numbers.get('unit_slip_share', float('nan')):.1%}; "
              f"korean rationale {res.numbers.get('korean_rationale_share', float('nan')):.1%}")
        ex = res.tables.get("extraction")
        if ex is not None and len(ex):
            print(ex.groupby("firm_id")[["revenue_ratio", "shares_outstanding_ratio",
                                          "unit_slip"]].mean().to_string())


def stage_e0(args) -> None:
    cfg, store = load_config(), SampleStore()
    run(b.e0(cfg, store, PILOT["pilot_L"]["firms"], reps=PILOT["scope"]["e0_reps"],
             **common(PILOT["prompt_version"])), store, args.dry_run, "E0")


def stage_e2(args) -> None:
    cfg, store = load_config(), SampleStore()
    run(b.e0_e2(cfg, store, PILOT["pilot_L"]["firms"], reps=PILOT["scope"]["e2_reps"],
                conditions=PILOT["scope"]["e2_conditions"], **common(PILOT["prompt_version"])),
        store, args.dry_run, "E2")


def stage_e6(args) -> None:
    cfg, store = load_config(), SampleStore()
    run(b.e6(cfg, store, PILOT["pilot_L"]["firms"], reps=PILOT["scope"]["e6_reps"],
             **common(PILOT["prompt_version"])), store, args.dry_run, "E6")


def stage_size(args) -> None:
    from src.metrics.baseline import baseline

    cfg, store = load_config(), SampleStore()
    e0 = pd.read_parquet(RUNS_DIR / "E0.parquet")
    e0 = e0[e0["firm_id"].isin(PILOT["pilot_L"]["firms"])
            & (e0["prompt_version"] == PILOT["prompt_version"])]
    out = []
    for r in baseline(e0).query("condition == 'C'").itertuples():
        pkg = store.package(r.firm_id)
        cash = pkg.bs.find("cash")
        for kind in ("cash", "non_operating"):
            out.append(decide_size(r.firm_id, kind, r.v0, r.sigma, r.shares_agent,
                                   r.equity_agent, cash.values.get(pkg.latest_year)
                                   if cash else None, cfg.experiments))
    SIZES.parent.mkdir(parents=True, exist_ok=True)
    size_table(out).to_parquet(SIZES, index=False)
    print(md_table(size_table(out)))


def load_sizes() -> list[SizeDecision]:
    if not SIZES.exists():
        return []
    return [SizeDecision(**{k: (None if pd.isna(v) else v) for k, v in r.items()})
            for r in pd.read_parquet(SIZES).to_dict("records")]


def stage_e3(args) -> None:
    store = SampleStore()
    sizes = {s.firm_id: s for s in load_sizes() if s.perturbation == "cash"}
    perts, reps = {}, {}
    for fid in PILOT["pilot_L"]["firms"]:
        eq = book_equity(store.package(fid))
        p = [("cash", {"x_mn": t * eq}) for t in PILOT["scope"]["e3_tiers"]] if eq and eq > 0 \
            else []
        s = sizes.get(fid)
        if s and s.status != "excluded" and s.x_mn:
            p = [("cash", {"x_mn": s.x_mn})] + p
        if p:
            perts[fid], reps[fid] = p, PILOT["scope"]["e3_reps"]
    spec = JobSpec(experiment="E3", firm_ids=sorted(perts), conditions=["C"],
                   perturbations=perts, reps=reps, **common(PILOT["prompt_version"]))
    run([spec], store, args.dry_run, "E3")


def stage_report(args) -> None:
    cfg, store = load_config(), SampleStore()
    firms = PILOT["pilot_L"]["firms"]
    tables = [pd.read_parquet(RUNS_DIR / f"{e}.parquet").dropna(axis=1, how="all")
              for e in ("E0", "E2", "E3", "E6") if (RUNS_DIR / f"{e}.parquet").exists()]
    runs = pd.concat(tables, ignore_index=True)
    runs = runs[runs["firm_id"].isin(firms) & (runs["tag"] == "pilot")
                & (runs["prompt_version"] == PILOT["prompt_version"])]
    runs = runs.drop_duplicates("job_id")
    sizes = load_sizes()
    res = evaluate(runs, cfg, sizes=sizes, packages={f: store.package(f) for f in firms})
    cost = cost_estimate(runs, cfg.require_model(PILOT["model"]))
    text = render(res, "Pilot Report (P7) — KOSDAQ-independent part", cost=cost,
                  sizes=size_table(sizes) if sizes else None)
    REPORT.write_text(text, encoding="utf-8")
    print(text[:3000])


STAGES = {"dev": stage_dev, "e0": stage_e0, "e2": stage_e2, "e6": stage_e6,
          "size": stage_size, "e3": stage_e3, "report": stage_report}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("stage", choices=list(STAGES))
    ap.add_argument("--prompt", default=PILOT["prompt_version"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    STAGES[args.stage](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
