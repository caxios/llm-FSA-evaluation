"""P4 Step 6: identifier dictionaries, fake names and the automated redaction check.

  python scripts/build_conditions.py                 # keeps existing fake names
  python scripts/build_conditions.py --regenerate-fake-names

Writes data/processed/identifiers/{firm_id}.json, data/processed/fake_names.parquet
(fixed once written: every experiment uses the same fake name), and
docs/redaction_report.md (automated leak check, redactions applied, industry labels,
fake-name list for human review). Exit code 1 if any identifier leaks into A/B/D.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.conditions import pipeline as pl  # noqa: E402
from src.conditions.fake_names import THRESHOLD, assign_fake_names  # noqa: E402
from src.conditions.industry import division_labels  # noqa: E402
from src.conditions.redactor import find_identifiers  # noqa: E402
from src.config import load_config  # noqa: E402
from src.data.dart_client import DartClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "redaction_report.md"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--regenerate-fake-names", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    sample = pl.load_sample()
    overrides = pl.load_overrides()

    # identifiers and industry labels
    rows = sample.to_dict("records")
    ids_by_firm = {}
    for row in rows:
        ids = pl.identifiers_for(row, overrides)
        pl.save_identifiers(ids)
        ids_by_firm[row["firm_id"]] = ids
    sample = sample.assign(industry_label=sample["ksic2"].map(pl.industry_label))

    # fake names (fixed once written)
    if args.regenerate_fake_names or not pl.FAKE_NAMES.exists():
        corp = DartClient().corp_codes()
        listed = corp.loc[corp["stock_code"].str.strip() != "", "corp_name"]
        fakes = assign_fake_names(sample, cfg.sample.seed, listed, corp["corp_name"])
        fakes.to_parquet(pl.FAKE_NAMES, index=False)
        pl.fake_names.cache_clear()
    fakes = pd.read_parquet(pl.FAKE_NAMES)
    missing = set(sample["firm_id"]) - set(fakes["firm_id"])
    if missing:
        raise SystemExit(f"fake names missing for {sorted(missing)}; use --regenerate-fake-names")

    # automated leak check on rendered A/B/D prompts
    leaks, redactions = [], []
    for row in rows:
        fid = row["firm_id"]
        for cond in ("A", "B", "D"):
            cp = pl.conditioned(fid, cond)
            text = cp.render(include_cb=False)
            for rule, hit in find_identifiers(text, ids_by_firm[fid]):
                leaks.append({"firm_id": fid, "condition": cond, "rule": rule, "text": hit})
            if cond == "A":
                redactions += [{"firm_id": fid, **r.model_dump()} for r in cp.redaction_log]
    write_report(sample, fakes, ids_by_firm, leaks, redactions)
    print(f"firms: {len(rows)}; redactions: {len(redactions)}; leaks: {len(leaks)}; "
          f"fake names: {len(fakes)} (max similarity {fakes['max_similarity'].max():.2f})")
    print(f"report: {REPORT}")
    return 1 if leaks else 0


def write_report(sample: pd.DataFrame, fakes: pd.DataFrame, ids_by_firm: dict,
                 leaks: list[dict], redactions: list[dict]) -> None:
    div = division_labels()
    out = ["# Redaction Report (P4)", "",
           f"- Generated: {datetime.now():%Y-%m-%d %H:%M}",
           f"- Firms: {len(sample)}", ""]

    out += ["## Automated leak check (conditions A, B, D)", "",
            "Searches each rendered prompt for every firm name variant, group name, investee, "
            "brand, ticker, homepage and CEO name in the firm's identifier dictionary.", ""]
    if leaks:
        out += ["| firm | condition | rule | text |", "|---|---|---|---|"]
        out += [f"| {r['firm_id']} | {r['condition']} | {r['rule']} | {r['text']} |"
                for r in leaks]
    else:
        out.append("**No identifier found in any A/B/D prompt.**")
    out.append("")

    out += ["## Redactions applied (labels and notes)", ""]
    if redactions:
        out += ["| firm | field | original | replacement | rule |", "|---|---|---|---|---|"]
        out += [f"| {r['firm_id']} | {r['field']} | {r['original']} | {r['replacement']} | "
                f"{r['rule']} |" for r in redactions]
    else:
        out.append("None: no statement or notes label in the sample contains an identifier.")
    out.append("")

    sizes = Counter(len(ids.investees) for ids in ids_by_firm.values())
    out += ["## Identifier dictionaries", "",
            f"- Investee names per firm: median "
            f"{pd.Series([len(i.investees) for i in ids_by_firm.values()]).median():.0f}, "
            f"firms with none: {sizes.get(0, 0)}",
            f"- Firms with a business-group prefix: "
            f"{sum(bool(i.group_names) for i in ids_by_firm.values())}", ""]

    coarse = sample[sample.apply(lambda r: r["industry_label"] != div.get(r["ksic2"]), axis=1)]
    out += ["## Industry labels", "",
            f"Divisions with fewer than the configured minimum of peers in the universe use "
            f"the KSIC section label ({len(coarse)} firms):", "",
            "| firm | KSIC | division label | label used |", "|---|---|---|---|"]
    out += [f"| {r.firm_id} | {r.ksic2} | {div.get(r.ksic2)} | {r.industry_label} |"
            for r in coarse.itertuples()]
    out.append("")

    merged = fakes.merge(sample[["firm_id", "corp_name"]], on="firm_id")
    out += ["## Fake names (review: plausible, not comical, not suggestive of a real firm)", "",
            f"Threshold: similarity < {THRESHOLD} to every listed name; no exact match to any "
            f"DART-registered name.", "",
            "| firm | real name | fake name | industry label | max sim. | nearest listed |",
            "|---|---|---|---|---|---|"]
    out += [f"| {r.firm_id} | {r.corp_name} | {r.fake_name} | {r.industry_label} | "
            f"{r.max_similarity:.2f} | {r.nearest_real_name} |" for r in merged.itertuples()]
    REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
