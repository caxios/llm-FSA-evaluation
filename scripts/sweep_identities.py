"""P3 Step 9: apply every applicable perturbation to every package and check identities.

Perturbations: scale over the k grid plus the E5 value (CB block removed, D3.4); shares
(m from config); cash distribution and non-operating assets at 2/5/10% of book equity (a
proxy until E0 provides equity values); CB V0-V4 for packages with a CB block.

Writes results/qa/perturbation_sweep.csv and results/qa/cb_variant_samples.md (V0/V2/V3
CB texts of 5 seeded small caps, for the human read required by the P3 exit criteria).

  python scripts/sweep_identities.py [--packages data/processed/packages]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.config import load_config  # noqa: E402
from src.data.package_schema import InputPackage  # noqa: E402
from src.perturb import (  # noqa: E402
    PerturbationInconsistent,
    PerturbationNotApplicable,
    PerturbationOutOfRange,
    perturb,
    without_cb,
)
from src.perturb.base import book_equity  # noqa: E402
from src.perturb.cb import PLACEBOS, cb_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results" / "qa"
STATUS = {PerturbationOutOfRange: "out_of_range", PerturbationNotApplicable: "not_applicable",
          PerturbationInconsistent: "inconsistent"}


def plan(pkg: InputPackage, cfg) -> list[tuple[str, dict, bool]]:
    """(name, params, strip_cb) for every perturbation applicable to the package."""
    exp = cfg.experiments
    ks = sorted({*exp.k_grid, *exp.k_identification} - {1.0})
    out = [("scale", {"k": k}, True) for k in ks]
    out.append(("shares", {"m": exp.share_multiplier}, False))
    eq = book_equity(pkg)
    for tier in exp.tiers:
        for name in ("cash", "non_operating"):
            out.append((name, {"x_mn": tier * eq if eq and eq > 0 else None,
                               "tier": tier}, False))
    if pkg.cb is not None:
        out += [(v, {}, False) for v in ("cb_v0", "cb_v1", "cb_v2", "cb_v3")]
        out += [("cb_v4", {"placebo": p}, False) for p in PLACEBOS]
    return out


def run_one(pkg: InputPackage, name: str, params: dict, strip_cb: bool) -> dict:
    row = {"firm_id": pkg.meta.firm_id, "group": pkg.meta.group, "perturbation": name,
           "params": json.dumps(params, ensure_ascii=False), "status": "ok", "detail": ""}
    call = {k: v for k, v in params.items() if k != "tier"}
    if "x_mn" in call and call["x_mn"] is None:
        row.update(status="not_applicable", detail="non-positive book equity")
        return row
    try:
        _, meta = perturb(without_cb(pkg) if strip_cb else pkg, name, **call)
        if name == "cb_v3":
            ratios = [d["ratio"] for d in meta.instruments]
            assumed = sum(d["floor_assumed"] == "yes" for d in meta.instruments)
            row["detail"] = f"ratios={ratios}; floor_assumed={assumed}/{len(ratios)}"
    except tuple(STATUS) as e:
        row.update(status=STATUS[type(e)], detail=str(e))
    except Exception as e:  # unexpected: reported, never hidden
        row.update(status="error", detail=f"{type(e).__name__}: {e}")
    return row


def cb_samples(pkgs: list[InputPackage], n: int = 5, seed: int = 20261019) -> str:
    small = sorted((p for p in pkgs if p.cb is not None), key=lambda p: p.meta.firm_id)
    chosen = random.Random(seed).sample(small, min(n, len(small)))
    out = ["# CB variant samples (P3 exit check: read V2 and V3 against V0)", ""]
    for pkg in sorted(chosen, key=lambda p: p.meta.firm_id):
        out.append(f"## {pkg.meta.firm_id}")
        for name in ("cb_v0", "cb_v2", "cb_v3"):
            try:
                text = cb_text(perturb(pkg, name)[0])
            except Exception as e:
                text = f"({type(e).__name__}: {e})"
            out += [f"### {name}", "```text", text, "```", ""]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--packages", type=Path, default=ROOT / "data/processed/packages")
    args = ap.parse_args()
    cfg = load_config()
    paths = sorted(args.packages.glob("*.json"))
    if not paths:
        print(f"no packages in {args.packages}")
        return 1
    pkgs = [InputPackage.from_json(p.read_text(encoding="utf-8")) for p in paths]
    rows = [run_one(pkg, name, params, strip)
            for pkg in pkgs for name, params, strip in plan(pkg, cfg)]
    df = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "perturbation_sweep.csv", index=False, encoding="utf-8-sig")
    (OUT_DIR / "cb_variant_samples.md").write_text(cb_samples(pkgs), encoding="utf-8")

    print(f"packages: {len(pkgs)}, perturbations: {len(df)}")
    print(df.pivot_table(index="perturbation", columns="status", values="firm_id",
                         aggfunc="count", fill_value=0).to_string())
    for status in ("inconsistent", "error", "out_of_range", "not_applicable"):
        sub = df[df.status == status]
        if not sub.empty:
            print(f"\n[{status}] {len(sub)}")
            reasons = Counter(d.split(":")[0][:80] for d in sub.detail)
            for reason, count in reasons.most_common(10):
                print(f"  {count:4d}  {reason}")
    bad = int(df.status.isin(["inconsistent", "error"]).sum())
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
