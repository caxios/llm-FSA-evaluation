"""P4 Step 8: manual redaction audit sheet for a stratified 10% sample (5 L, 5 M, 5 S).

A, B and D share the same redacted statements and differ only in the company block, so
the sheet shows the full condition-A prompt once per firm plus the B and D company blocks,
with a checklist for two review passes.

  python scripts/redaction_audit_sample.py   ->  docs/redaction_audit.md
"""

from __future__ import annotations

import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.conditions import pipeline as pl  # noqa: E402
from src.config import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "redaction_audit.md"
CHECKS = ["회사명·약칭", "종목코드", "브랜드·제품명", "계열사·관계회사명", "대표자명", "주소·지역",
          "사업부문명"]


def main() -> int:
    seed = load_config().sample.seed
    sample = pl.load_sample()
    rng = random.Random(seed)
    chosen = []
    for group in ("L", "M", "S"):
        ids = sorted(sample.loc[sample["group"] == group, "firm_id"])
        chosen += sorted(rng.sample(ids, 5))
    out = ["# Redaction Audit (P4 Step 8)", "",
           f"- Generated: {datetime.now():%Y-%m-%d %H:%M}; seed {seed}",
           f"- Firms: {', '.join(chosen)}",
           "- Two passes by a person. For each firm read the condition-A prompt and tick every "
           "item that is **absent**; note anything found. A, B and D share these statements; "
           "only the company block differs (shown below each prompt).", "",
           "| firm | pass 1 | pass 2 | findings |", "|---|---|---|---|"]
    out += [f"| {f} | [ ] | [ ] | |" for f in chosen]
    out.append("")
    for fid in chosen:
        a = pl.conditioned(fid, "A")
        out += [f"## {fid}", "",
                "Checklist (absent): " + " · ".join(f"[ ] {c}" for c in CHECKS), "",
                "Company blocks: "
                + " / ".join(f"**{c}** `{pl.conditioned(fid, c).company_block}`".replace("\n", "; ")
                             for c in ("B", "D")), "",
                f"Redactions applied: {len(a.redaction_log)}", "",
                "```text", a.render(include_cb=False), "```", ""]
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT} ({len(chosen)} firms)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
