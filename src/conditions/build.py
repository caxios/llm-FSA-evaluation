"""Information conditions A/B/D/C from one package (P4 §5.3).

| Condition | Company name | Industry |
| A         | (비공개)      | (비공개)  |
| B         | (비공개)      | label    |
| D         | fake name    | label    |
| C         | real name    | label    |

A, B and D share one redacted package: every line label, the notes summary labels and (if
present) the CB text go through the redactor. C keeps the labels as reported. The company
block keeps the same two-line structure in every condition (D4.1).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from src.conditions.identifiers import FirmIdentifiers
from src.conditions.redactor import Redaction, redact_text
from src.data.package_schema import InputPackage
from src.data.render import HIDDEN, render_company_block, render_user_prompt

ConditionCode = Literal["A", "B", "D", "C"]
CONDITIONS: tuple[ConditionCode, ...] = ("A", "B", "D", "C")


class ConditionedPackage(BaseModel):
    condition: ConditionCode
    package: InputPackage
    company_block: str
    fake_name: str | None = None
    redaction_log: list[Redaction]

    def render(self, include_cb: bool = False) -> str:
        return render_user_prompt(self.package, self.condition, fake_name=self.fake_name,
                                  include_cb=include_cb)


def redact_package(pkg: InputPackage, ids: FirmIdentifiers
                   ) -> tuple[InputPackage, list[Redaction]]:
    """Copy of `pkg` with identifiers removed from every free-text field."""
    out = pkg.model_copy(deep=True)
    log: list[Redaction] = []
    segments: dict[str, str] = {}
    for st in out.statements():
        for line in st.lines:
            line.label, entries = redact_text(line.label, ids, f"{st.code}.{line.line_id}",
                                              segments)
            log += entries
    for kind in ("borrowings", "non_operating_assets"):
        for item in getattr(out.notes, kind):
            item.label, entries = redact_text(item.label, ids, f"notes.{item.line_id}", segments)
            log += entries
    if out.cb is not None:
        out.cb.filing_text, entries = redact_text(out.cb.filing_text, ids, "cb.filing_text",
                                                  segments)
        log += entries
        out.cb.outstanding_table_text, entries = redact_text(
            out.cb.outstanding_table_text, ids, "cb.table", segments)
        log += entries
    return out, log


def make_condition(pkg: InputPackage, condition: ConditionCode, ids: FirmIdentifiers,
                   fake_name: str | None = None, industry_label: str | None = None
                   ) -> ConditionedPackage:
    """`industry_label` overrides the label stored in the package meta (P4 §5.7)."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition}")
    if condition == "D" and not fake_name:
        raise ValueError("condition D needs a fake name")
    if condition == "C":
        out, log = pkg.model_copy(deep=True), []
    else:
        out, log = redact_package(pkg, ids)
    if industry_label is not None:
        out.meta.industry_label = industry_label
    if out.meta.industry_label is None:
        out.meta.industry_label = HIDDEN
    name = fake_name if condition == "D" else None
    return ConditionedPackage(condition=condition, package=out,
                              company_block=render_company_block(out, condition, name),
                              fake_name=name, redaction_log=log)
