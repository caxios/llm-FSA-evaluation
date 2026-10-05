"""Perturbation engine (P3). Importing the package registers every perturbation;
`perturb(pkg, name, **params)` is the public entry point."""

from src.perturb import cash_distribution, cb, non_operating, scale, shares  # noqa: F401
from src.perturb.base import (  # noqa: F401
    REGISTRY,
    PerturbationError,
    PerturbationInconsistent,
    PerturbationNotApplicable,
    PerturbationOutOfRange,
    PerturbMeta,
    perturb,
    without_cb,
)
