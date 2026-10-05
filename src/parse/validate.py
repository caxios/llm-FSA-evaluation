"""JSON extraction, schema validation and retries (P5 §5.5, D5.4).

Missing-data rules (copied into the preregistration):
- invalid runs are excluded from all medians and regressions;
- a firm x condition x perturbation cell with < 70% valid runs is flagged `low_validity`
  (kept in primary analyses, dropped in a robustness analysis);
- value_per_share <= 0 is valid output but excluded from log-based metrics (count reported).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from src.agents.llm_client import LLMClient, RawResponse
    from src.config import ModelConfig

RETRY_MESSAGE = ("출력이 스키마에 맞지 않습니다: {error}. 같은 평가 결과를 스키마에 맞는 "
                 "JSON으로만 다시 출력하세요.")
LOW_VALIDITY = 0.7


class NoJSON(ValueError):
    pass


def extract_json(text: str) -> dict:
    """Outermost JSON object in `text`: code fences stripped, surrounding prose ignored."""
    text = re.sub(r"```(?:json|JSON)?", "", text)
    start = text.find("{")
    if start < 0:
        raise NoJSON("no JSON object in the response")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                except json.JSONDecodeError as e:
                    raise NoJSON(f"invalid JSON: {e.msg} at {e.pos}") from e
                if not isinstance(obj, dict):
                    raise NoJSON("top-level JSON is not an object")
                return obj
    raise NoJSON("unterminated JSON object")


def _short(err: ValidationError, limit: int = 5) -> str:
    parts = []
    for e in err.errors()[:limit]:
        loc = ".".join(str(x) for x in e["loc"])
        parts.append(f"{loc}: {e['msg']}")
    more = len(err.errors()) - limit
    return "; ".join(parts) + (f"; (+{more} more)" if more > 0 else "")


def validate_output(text: str, schema: type[BaseModel]) -> tuple[BaseModel | None, str | None]:
    try:
        data = extract_json(text)
    except NoJSON as e:
        return None, str(e)
    try:
        return schema.model_validate(data), None
    except ValidationError as e:
        return None, _short(e)


def run_with_retries(client: LLMClient, messages: list[dict], cfg: ModelConfig,
                     schema: type[BaseModel], max_retries: int = 2
                     ) -> tuple[BaseModel | None, list[RawResponse], str | None]:
    """Call, validate, and on failure ask again within the same conversation (same rep)."""
    convo = list(messages)
    raws: list[RawResponse] = []
    error: str | None = None
    for _ in range(max_retries + 1):
        raw = client.complete(convo, cfg)
        raws.append(raw)
        if raw.refusal:
            error = "refusal"
        else:
            out, error = validate_output(raw.text, schema)
            if out is not None:
                return out, raws, None
        convo = [*convo, {"role": "assistant", "content": raw.text},
                 {"role": "user", "content": RETRY_MESSAGE.format(error=error)}]
    return None, raws, error
