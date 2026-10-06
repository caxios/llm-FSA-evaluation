"""Experiment runner (P5 §5.7).

  python -m src.runner.run --experiment E2 --groups L,M,S --conditions A,B,D,C \
      --model primary --agent P [--firms L001,L002] [--reps 10] [--limit 50] \
      [--dry-run] [--tag pilot]

Flow: build job specs -> expand to rendered requests -> split into cached / to run ->
on --dry-run print counts and a cost estimate and exit (no client calls) -> otherwise run
concurrently, cache and log each new record -> refresh results/runs/{experiment}.parquet
(one row per request of this invocation, replacing earlier rows with the same job_id).
`--agent` is P (plain), T (tool) or SYN:<name> (synthetic: oracle, no_dilution,
calc_error); synthetic agents go through exactly the same path.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.agents.base import Agent, RunRecord, RunRequest, cache_key
from src.agents.llm_client import TransientError, max_concurrency
from src.config import Config, load_config
from src.data.package_schema import InputPackage
from src.runner.cache import CallCache
from src.runner.cost import CostLine, estimate, mean_tokens
from src.runner.jobs import ExpandStats, JobSpec, PackageStore, expand
from src.runner.logger import RUNS_DIR, log_record

log = logging.getLogger("runner")
BATCH = 256


class ModelChanged(RuntimeError):
    """The provider reported a different model id in the middle of a batch."""


@dataclass
class RunSummary:
    records: list[RunRecord] = field(default_factory=list)
    cached: int = 0
    executed: int = 0
    pending: int = 0              # to run but not run (dry run or --limit)
    failed: int = 0               # infrastructure failures after retries; not cached, rerun
    stats: ExpandStats = field(default_factory=ExpandStats)
    calls_by_schema: Counter = field(default_factory=Counter)
    cost: list[CostLine] = field(default_factory=list)


class Runner:
    def __init__(self, agent: Agent, cache: CallCache, *, runs_dir: Path | None = None,
                 max_workers: int = 4, log_runs: bool = True):
        self.agent, self.cache = agent, cache
        self.runs_dir = runs_dir if runs_dir is not None else RUNS_DIR
        self.max_workers, self.log_runs = max_workers, log_runs
        self.model_seen: str | None = None

    def _execute(self, batch: list[tuple[RunRequest, InputPackage | None, str]]
                 ) -> list[RunRecord]:
        def one(item):
            req, pkg, _ = item
            try:
                return self.agent.run(req, pkg)
            except TransientError as e:   # network/provider outage: leave for the next run
                log.warning("job %s failed after retries: %s", req.job_id, str(e)[:120])
                return None

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            out = list(ex.map(one, batch))
        done = []
        for rec, (_, _, key) in zip(out, batch, strict=True):
            if rec is None:
                continue
            if rec.cache_key != key:
                raise RuntimeError("agent produced a different cache key than the runner")
            if rec.model_reported and rec.raw:
                if self.model_seen is None:
                    self.model_seen = rec.model_reported
                elif rec.model_reported != self.model_seen:
                    raise ModelChanged(f"model changed: {self.model_seen} -> "
                                       f"{rec.model_reported}")
            self.cache.put(rec)
            if self.log_runs:
                log_record(rec, self.runs_dir)
            done.append(rec)
        return done

    def _collect(self, s: RunSummary, batch: list) -> None:
        recs = self._execute(batch)
        s.records += recs
        s.executed += len(recs)
        s.failed += len(batch) - len(recs)

    def run(self, specs: list[JobSpec], store: PackageStore, *, dry_run: bool = False,
            limit: int | None = None, cfg=None) -> RunSummary:
        s = RunSummary()
        identity = self.agent.identity()
        batch: list[tuple[RunRequest, InputPackage | None, str]] = []
        for spec in specs:
            for req, pkg in expand(spec, store, s.stats):
                key = cache_key(req, identity)
                hit = self.cache.get(key)
                if hit is not None:
                    s.cached += 1
                    s.records.append(hit.model_copy(update={"request": req}))
                    continue
                if dry_run or (limit is not None and s.executed + len(batch) >= limit):
                    s.pending += 1
                    s.calls_by_schema[req.schema_name] += 1
                    continue
                batch.append((req, pkg, key))
                if len(batch) >= BATCH:
                    self._collect(s, batch)
                    batch = []
        if batch:
            self._collect(s, batch)
        if dry_run:
            s.cost = estimate(dict(s.calls_by_schema), cfg,
                              mean_tokens(self.cache.records(specs[0].model_key))
                              if specs else None)
        return s


# ---------------------------------------------------------------- run-level table

COLUMNS = ["job_id", "cache_key", "experiment", "tag", "firm_id", "group", "condition",
           "perturbation_type", "perturbation_params", "schema_name", "agent_structure",
           "model_key",
           "model_reported", "prompt_version", "prompt_sha", "rep", "valid", "error",
           "attempts", "value_per_share", "equity_value", "shares_used", "net_debt",
           "enterprise_value", "wacc", "terminal_growth", "dilution_applied",
           "convertible_shares", "anomaly_flag", "tokens_in", "tokens_out", "latency_s",
           "code_version", "finished_at", "output_json"]


def flatten(rec: RunRecord) -> dict:
    r, o = rec.request, rec.output or {}
    calc, res = o.get("calculation") or {}, o.get("result") or {}
    a, d, m = o.get("assumptions") or {}, o.get("dilution") or {}, o.get("meta") or {}
    return {
        "job_id": r.job_id, "cache_key": rec.cache_key, "experiment": r.experiment,
        "tag": r.tag, "firm_id": r.firm_id, "group": r.group, "condition": r.condition,
        "perturbation_type": r.perturbation.type,
        "perturbation_params": json.dumps(r.perturbation.params, ensure_ascii=False,
                                          sort_keys=True),
        "schema_name": r.schema_name, "agent_structure": r.agent_structure,
        "model_key": r.model_key,
        "model_reported": rec.model_reported, "prompt_version": r.prompt_version,
        "prompt_sha": r.prompt_sha, "rep": r.rep, "valid": rec.valid, "error": rec.error,
        "attempts": rec.attempts, "value_per_share": res.get("value_per_share"),
        "equity_value": calc.get("equity_value"), "shares_used": calc.get("shares_used"),
        "net_debt": calc.get("net_debt"), "enterprise_value": calc.get("enterprise_value"),
        "wacc": a.get("wacc"), "terminal_growth": a.get("terminal_growth"),
        "dilution_applied": d.get("dilution_applied"),
        "convertible_shares": d.get("convertible_shares"),
        "anomaly_flag": m.get("data_anomaly_flag"),
        "tokens_in": sum(x.tokens_in for x in rec.raw),
        "tokens_out": sum(x.tokens_out for x in rec.raw),
        "latency_s": sum(x.latency_s for x in rec.raw),
        "code_version": rec.code_version, "finished_at": rec.finished_at.isoformat(),
        "output_json": json.dumps(rec.output, ensure_ascii=False) if rec.output else None,
    }


def write_table(records: list[RunRecord], experiment: str, runs_dir: Path | None = None
                ) -> Path:
    path = (runs_dir if runs_dir is not None else RUNS_DIR) / f"{experiment}.parquet"
    new = pd.DataFrame([flatten(r) for r in records], columns=COLUMNS)
    if path.exists():
        old = pd.read_parquet(path)
        new = pd.concat([old[~old["job_id"].isin(new["job_id"])], new], ignore_index=True)
    new = new.sort_values("job_id", kind="stable").reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    new.to_parquet(path, index=False)
    return path


# ---------------------------------------------------------------- CLI


def make_agent(agent: str, model_key: str, cfg: Config) -> tuple[Agent, str, str]:
    """(agent, agent_structure, model_key used in requests)."""
    if agent.upper().startswith("SYN"):
        from src.agents.synthetic import SYNTHETIC

        name = agent.split(":", 1)[1] if ":" in agent else "oracle"
        return SYNTHETIC[name](), "SYN", f"syn_{name}"
    from src.agents.llm_client import make_client

    mcfg = cfg.require_model(model_key)
    client = make_client(mcfg)
    if agent.upper() == "T":
        from src.agents.tool import ToolAgent

        return ToolAgent(client, mcfg), "T", model_key
    from src.agents.plain import PlainAgent

    return PlainAgent(client, mcfg), "P", model_key


def _parse(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--experiment", required=True, help="E0, E2, E3, E5, E6, E7, E8")
    ap.add_argument("--groups", default="L,M,S")
    ap.add_argument("--conditions", default=None, help="override the builder's conditions")
    ap.add_argument("--model", default="primary")
    ap.add_argument("--agent", default="P", help="P | T | SYN:<name>")
    ap.add_argument("--firms", default=None)
    ap.add_argument("--reps", type=int, default=None)
    ap.add_argument("--k", default=None, help="E2 only: comma-separated k values to keep")
    ap.add_argument("--limit", type=int, default=None, help="max new calls")
    ap.add_argument("--prompt-version", default="v1")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tag", default="")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--sizes", type=Path, default=None,
                    help="E3 only: size_decisions parquet (cash and non-operating sizes, n)")
    ap.add_argument("--tiers", action="store_true", help="E3 only: add the tier sizes")
    return ap.parse_args(argv)


def load_sizes(path: Path) -> list:
    from src.perturb.sizing import SizeDecision

    return [SizeDecision(**{k: (None if pd.isna(v) else v) for k, v in r.items()})
            for r in pd.read_parquet(path).to_dict("records")]


def main(argv: list[str] | None = None, store: PackageStore | None = None,
         cache: CallCache | None = None) -> RunSummary:
    from src.experiments.builders import BUILDERS
    from src.runner.jobs import SampleStore

    args = _parse(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config()
    store = store if store is not None else SampleStore()
    exp = args.experiment.upper()
    if exp not in BUILDERS:
        raise SystemExit(f"unknown experiment {exp}; known: {sorted(BUILDERS)}")
    if args.firms:
        firms = args.firms.split(",")
    else:
        groups = set(args.groups.split(","))
        firms = sorted(f for f in store.sample.index  # type: ignore[attr-defined]
                       if store.group(f) in groups)
    # dry runs build the agent only for its identity (cache keys); no call is made
    agent, agent_structure, model_key = make_agent(args.agent, args.model, cfg)
    common = {"agent_structure": agent_structure, "model_key": model_key,
              "prompt_version": args.prompt_version, "tag": args.tag}
    extra = {}
    if exp == "E3":
        extra = {"sizes": load_sizes(args.sizes) if args.sizes else None, "tiers": args.tiers}
    specs = BUILDERS[exp](cfg, store, firms, reps=args.reps, **common, **extra)
    for spec in specs:
        if args.conditions and exp != "E6":
            spec.conditions = args.conditions.split(",")
        if args.k and exp == "E2":
            keep = {float(k) for k in args.k.split(",")}
            spec.perturbations = [(n, p) for n, p in spec.perturbations  # type: ignore[misc]
                                  if (n == "none" and 1.0 in keep)
                                  or (n == "scale" and p["k"] in keep)]
    cache = cache if cache is not None else CallCache()
    mcfg = cfg.models.get(model_key)
    workers = args.workers or (max_concurrency(mcfg) if mcfg else 8)
    runner = Runner(agent, cache, max_workers=workers)
    summary = runner.run(specs, store, dry_run=args.dry_run, limit=args.limit, cfg=mcfg)
    total = summary.cached + summary.executed + summary.pending
    print(f"{exp}: requests {total} (cells {summary.stats.cells}); cached {summary.cached}; "
          f"executed {summary.executed}; pending {summary.pending}; "
          f"skipped perturbations {len(summary.stats.skipped)}")
    for firm, pert, reason in summary.stats.skipped[:20]:
        print(f"  skipped {firm} {pert}: {reason[:80]}")
    if args.dry_run:
        for c in summary.cost:
            print(f"  {c.schema}: {c.calls} calls x ({c.tokens_in:,.0f} in / "
                  f"{c.tokens_out:,.0f} out tokens, {c.source}) = ${c.usd:,.2f}")
        print(f"  estimated cost: ${sum(c.usd for c in summary.cost):,.2f}")
        return summary
    if summary.records:
        path = write_table(summary.records, exp)
        valid = sum(r.valid for r in summary.records)
        print(f"valid {valid}/{len(summary.records)}; table: {path}")
    if summary.failed:
        print(f"failed {summary.failed} (network/provider errors after retries; re-run to "
              f"complete)")
    return summary


if __name__ == "__main__":
    try:
        if main().failed:
            sys.exit(4)
    except ModelChanged as e:
        print(f"halted: {e}", file=sys.stderr)
        sys.exit(2)
