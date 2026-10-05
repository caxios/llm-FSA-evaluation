"""Cost estimates for dry runs (P5 §5.7): mean token counts from cached records of the
same model and schema when available, else configured defaults."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from src.agents.base import RunRecord
from src.config import ModelConfig

# (input, output) tokens per call before any measurement; output includes thinking tokens.
DEFAULT_TOKENS = {"valuation": (6000, 1500), "identification": (6000, 150),
                  "quiz": (300, 200)}


@dataclass
class CostLine:
    schema: str
    calls: int
    tokens_in: float
    tokens_out: float
    source: str
    usd: float


def mean_tokens(records: list[RunRecord]) -> dict[str, tuple[float, float]]:
    acc: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for r in records:
        if r.raw:
            acc[r.request.schema_name].append((sum(x.tokens_in for x in r.raw),
                                               sum(x.tokens_out for x in r.raw)))
    return {k: (sum(a for a, _ in v) / len(v), sum(b for _, b in v) / len(v))
            for k, v in acc.items() if v}


def estimate(calls_by_schema: dict[str, int], cfg: ModelConfig | None,
             measured: dict[str, tuple[float, float]] | None = None) -> list[CostLine]:
    out = []
    for schema, calls in sorted(calls_by_schema.items()):
        if measured and schema in measured:
            tin, tout = measured[schema]
            source = "cache"
        else:
            tin, tout = DEFAULT_TOKENS.get(schema, DEFAULT_TOKENS["valuation"])
            source = "default"
        usd = 0.0 if cfg is None else calls * (tin * cfg.price_in_per_mtok
                                               + tout * cfg.price_out_per_mtok) / 1e6
        out.append(CostLine(schema, calls, tin, tout, source, usd))
    return out
