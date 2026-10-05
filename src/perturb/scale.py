"""Scale perturbation (E2, E5): every monetary amount x k (P3 §5.2).

Share counts are unchanged, so per-share amounts (EPS, DPS) scale by k as well and the
theoretical value is V* = V0 k. Packages with a CB block are refused (D3.4): scaling the
face amounts at a fixed conversion price would change the dilution ratio.
"""

from __future__ import annotations

from src.data.package_schema import InputPackage
from src.perturb.base import PerturbationNotApplicable, PerturbMeta, register


def _scale_values(values: dict[int, float | None], k: float) -> None:
    for y, v in values.items():
        if v is not None:
            values[y] = v * k


@register("scale")
def scale(pkg: InputPackage, k: float) -> PerturbMeta:
    if k <= 0:
        raise ValueError("k must be positive")
    if pkg.cb is not None:
        raise PerturbationNotApplicable("scale packages exclude the CB block (D3.4)")
    for st in pkg.statements():
        for line in st.lines:
            if line.kind in ("monetary", "per_share"):
                _scale_values(line.values, k)
    _scale_values(pkg.per_share.eps, k)
    _scale_values(pkg.per_share.dps_common, k)
    for item in pkg.notes.borrowings + pkg.notes.non_operating_assets:
        item.amount *= k
    return PerturbMeta(type="scale", params={"k": k})
