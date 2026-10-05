"""Common perturbation interface (P3 §5.1).

Every perturbation is registered by name and reached through `perturb()`, which deep-copies
the package, applies the edit, and runs the accounting identity checks. The registered
functions edit the copy they are given; callers never see a partially edited package.

`apply_delta` changes one line and every subtotal above it: first the line's own `parent`
(set per package by the builder), then the chain in config/ancestry.yaml. Subtotals a firm
does not report are skipped, so the chain is resolved per package.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.data.account_map import load_ancestry
from src.data.package_schema import InputPackage, LineItem, NoteItem, Statement
from src.perturb.consistency import SOFT_CHECKS, check_identities

PerturbType = Literal["none", "scale", "cash", "shares", "non_operating",
                      "cb_v0", "cb_v1", "cb_v2", "cb_v3", "cb_v4"]
Param = float | str | None


class PerturbationError(Exception):
    """Base class for expected perturbation failures."""


class PerturbationInconsistent(PerturbationError):
    """The perturbed package violates an accounting identity."""


class PerturbationOutOfRange(PerturbationError):
    """The requested size is infeasible for this firm (e.g. more cash than the firm holds)."""


class PerturbationNotApplicable(PerturbationError):
    """The perturbation does not apply to this package (e.g. no CB, CB already at floor)."""


class PerturbMeta(BaseModel):
    type: PerturbType
    params: dict[str, Param] = Field(default_factory=dict)
    year: int | None = None
    instruments: list[dict[str, Param]] = Field(default_factory=list)  # CB variants
    notes: str = ""


PerturbFn = Callable[..., PerturbMeta]
REGISTRY: dict[str, PerturbFn] = {}


def register(name: str) -> Callable[[PerturbFn], PerturbFn]:
    def deco(fn: PerturbFn) -> PerturbFn:
        REGISTRY[name] = fn
        return fn
    return deco


# ---------------------------------------------------------------- line helpers


def outflow_sign(pkg: InputPackage) -> int:
    """+1 if the firm reports cash-flow outflows as positive numbers (builder flag)."""
    for flag in pkg.meta.flags:
        if flag.startswith("cf_outflow_sign="):
            return int(flag.split("=", 1)[1])
    return 1


def chain(st: Statement, line: LineItem) -> list[LineItem]:
    """Subtotals above `line`, nearest first, skipping subtotals the firm does not report."""
    ancestry = load_ancestry().get(st.code, {})
    key = line.parent if line.parent else ancestry.get(line.canonical or "")
    out: list[LineItem] = []
    seen: set[str] = set()
    while key and key not in seen:
        seen.add(key)
        found = st.find(key)
        if found is not None:
            out.append(found)
        key = ancestry.get(key)
    return out


def _add(line: LineItem, year: int, delta: float) -> None:
    line.values[year] = (line.values.get(year) or 0.0) + delta


def apply_delta(pkg: InputPackage, statement: str, target: str | LineItem, year: int,
                delta: float, leaf_delta: float | None = None) -> list[str]:
    """Add `delta` to the target line and to every subtotal above it, in place.

    `leaf_delta` overrides the change on the target line itself; it is used for cash-flow
    lines reported with the outflow-positive convention (a dividend of X is shown as +X
    while it lowers the financing subtotal by X). Ancestors whose value is not reported for
    `year` stay unreported. Returns the line_ids changed.
    """
    st = pkg.statement(statement)  # type: ignore[arg-type]
    line = st.get(target) if isinstance(target, str) else target
    _add(line, year, delta if leaf_delta is None else leaf_delta)
    touched = [line.line_id]
    for anc in chain(st, line):
        if anc.values.get(year) is None:
            continue
        _add(anc, year, delta)
        touched.append(anc.line_id)
    return touched


def add_line(st: Statement, label: str, parent: str | None, years: list[int], *,
             canonical: str | None = None, category: str | None = None) -> LineItem:
    """Create a derived line (all years unreported) placed after its siblings."""
    n = sum(1 for ln in st.lines if ln.derived)
    line = LineItem(line_id=f"{st.code.lower()}_p{n:02d}", label=label,
                    account_id="-표준계정코드 미사용-", canonical=canonical, category=category,
                    parent=parent, kind="monetary", values={y: None for y in years},
                    order=0, indent=1 if parent else 0, derived=True)
    ordered = sorted(st.lines, key=lambda x: x.order)
    pos = len(ordered)
    for i, ln in enumerate(ordered):
        if ln.parent == parent or (parent is not None and ln.canonical == parent
                                   and pos == len(ordered)):
            pos = i + 1
    ordered.insert(pos, line)
    for i, ln in enumerate(ordered):
        ln.order = i
    st.lines = ordered
    return line


def update_note(items: list[NoteItem], line: LineItem, year: int) -> None:
    """Keep the derived notes summary (D2.2) in step with a changed balance-sheet line."""
    value = line.values.get(year)
    for it in items:
        if it.line_id == line.line_id:
            it.amount = value or 0.0
            return
    if value and line.category:
        items.append(NoteItem(label=line.label, amount=value, line_id=line.line_id,
                              category=line.category))


def book_equity(pkg: InputPackage, year: int | None = None) -> float | None:
    y = year or pkg.latest_year
    for canonical in ("equity_owners", "total_equity"):
        line = pkg.bs.find(canonical)
        if line is not None and line.values.get(y) is not None:
            return line.values[y]
    return None


def without_cb(pkg: InputPackage) -> InputPackage:
    """Copy without the CB block (E2/E3 packages exclude CB information, D3.4)."""
    out = pkg.model_copy(deep=True)
    out.cb = None
    return out


# ---------------------------------------------------------------- entry point


def perturb(pkg: InputPackage, name: str, **params: Any) -> tuple[InputPackage, PerturbMeta]:
    """Apply a registered perturbation to a copy of `pkg` and verify accounting identities.

    Hard identity violations raise `PerturbationInconsistent`. Soft checks (ending cash vs.
    BS cash) must not newly fail: a package that passed them before must pass them after.
    """
    import src.perturb  # noqa: F401  (populates the registry)

    if name not in REGISTRY:
        raise KeyError(f"unknown perturbation '{name}'; known: {sorted(REGISTRY)}")
    out = pkg.model_copy(deep=True)
    meta = REGISTRY[name](out, **params)
    hard = check_identities(out)
    if hard:
        raise PerturbationInconsistent(f"{pkg.meta.firm_id} {name}{params}: {hard}")
    before = {(v.check, v.year) for v in check_identities(pkg, include_soft=True)
              if v.check in SOFT_CHECKS}
    after = [v for v in check_identities(out, include_soft=True)
             if v.check in SOFT_CHECKS and (v.check, v.year) not in before]
    if after:
        raise PerturbationInconsistent(f"{pkg.meta.firm_id} {name}{params}: {after}")
    return out, meta
