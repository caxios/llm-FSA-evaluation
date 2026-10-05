"""P4 Step 7: LLM residual check of the redacted prompts (conditions A and B).

The comparison model (D4.4) lists every word that could identify a company, group, brand,
person or place. Only tokens that literally occur in the prompt are candidates; a firm
name the model *infers* from the numbers is not a redaction failure (E5 measures that).

  python scripts/redaction_llm_check.py --round 1 [--limit 5] [--dry-run]

Responses are cached in data/processed/redaction_llm/round{N}/. The review list goes to
docs/redaction_llm_review.md: confirmed identifiers are added to
config/redaction_overrides.yaml (then re-run build_conditions.py and the next round);
generic tokens go to its `ignore` list.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402
from tenacity import retry, stop_after_attempt, wait_exponential  # noqa: E402

from src.conditions import pipeline as pl  # noqa: E402
from src.config import load_config, require_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "processed" / "redaction_llm"
REVIEW = ROOT / "docs" / "redaction_llm_review.md"
INSTRUCTION = (
    "아래 재무 자료에서 특정 회사, 그룹, 브랜드, 인물, 지역을 식별할 수 있는 단어나 표현을 "
    "모두 나열하세요. 자료에 실제로 적혀 있는 표현만 원문 그대로 적고, 숫자로부터 추측한 "
    "회사명은 적지 마세요. 표준적인 회계 계정명(예: 매출액, 관계기업투자)은 제외하세요. "
    '결과는 JSON 객체 {"tokens": ["...", ...]} 하나로만 답하고, 없으면 {"tokens": []}로 '
    "답하세요.\n\n---\n"
)


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30), reraise=True)
def call_model(model, key: str, prompt: str) -> dict:
    body = {"model": model.model_id, "temperature": 0.0,
            "max_tokens": model.max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}}
    resp = requests.post(f"{model.base_url.rstrip('/')}/chat/completions", json=body,
                         headers={"Authorization": f"Bearer {key}"}, timeout=180)
    if resp.status_code >= 500 or resp.status_code == 429:
        resp.raise_for_status()
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    return {"text": data["choices"][0]["message"]["content"] or "",
            "usage": data.get("usage", {}), "model": data.get("model", model.model_id)}


def parse_tokens(text: str) -> list[str] | None:
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        start, end = text.index("{"), text.rindex("}")
        tokens = json.loads(text[start:end + 1]).get("tokens", [])
    except (ValueError, json.JSONDecodeError, AttributeError):
        return None
    return [str(t).strip() for t in tokens if str(t).strip()]


def run_one(model, key: str, round_dir: Path, firm_id: str, cond: str,
            dry_run: bool) -> dict:
    path = round_dir / f"{firm_id}_{cond}.json"
    prompt_text = pl.conditioned(firm_id, cond).render(include_cb=False)
    if path.exists():
        rec = json.loads(path.read_text(encoding="utf-8"))
    elif dry_run:
        return {"firm_id": firm_id, "condition": cond, "tokens": [], "dry_run": True,
                "prompt_chars": len(prompt_text)}
    else:
        t0 = time.time()
        out = call_model(model, key, INSTRUCTION + prompt_text)
        rec = {"firm_id": firm_id, "condition": cond, "model": out["model"],
               "raw": out["text"], "usage": out["usage"], "latency_s": time.time() - t0,
               "at": datetime.now().isoformat(timespec="seconds")}
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    tokens = parse_tokens(rec.get("raw", ""))
    norm = re.sub(r"\s+", "", prompt_text)
    rec["tokens"] = tokens or []
    rec["parse_ok"] = tokens is not None
    rec["present"] = [t for t in rec["tokens"] if re.sub(r"\s+", "", t) in norm]
    return rec


def write_review(records: list[dict], round_no: int, ignore: set[str], cost: float) -> int:
    by_token: dict[str, dict] = defaultdict(lambda: {"firms": set(), "conds": set()})
    inferred: dict[str, set] = defaultdict(set)
    for r in records:
        for t in r["tokens"]:
            if t in ignore:
                continue
            if t in r["present"]:
                by_token[t]["firms"].add(r["firm_id"])
                by_token[t]["conds"].add(r["condition"])
            else:
                inferred[t].add(r["firm_id"])
    rows = sorted(by_token.items(), key=lambda kv: (len(kv[1]["firms"]), kv[0]))
    failed = [f"{r['firm_id']}_{r['condition']}" for r in records if not r["parse_ok"]]
    out = [f"# Redaction LLM Review (P4, round {round_no})", "",
           f"- Generated: {datetime.now():%Y-%m-%d %H:%M}",
           f"- Prompts checked: {len(records)} (conditions A, B); unparsable responses: "
           f"{len(failed)} {', '.join(failed[:10])}",
           f"- Estimated cost this run: ${cost:.2f}", "",
           "## Tokens present in the prompt text (review these)", "",
           "Mark each: an identifier → add to `config/redaction_overrides.yaml` under the "
           "firm (names / investees / brands / group_names / segments); generic → add to "
           "`ignore`. Tokens flagged for many firms are usually generic account terms.", "",
           "| token | firms | conditions | example firms |", "|---|---|---|---|"]
    for tok, info in rows:
        firms = sorted(info["firms"])
        out.append(f"| {tok} | {len(firms)} | {','.join(sorted(info['conds']))} | "
                   f"{', '.join(firms[:6])}{' …' if len(firms) > 6 else ''} |")
    if not rows:
        out.append("| (none) | | | |")
    out += ["", "## Tokens not in the prompt text (inferred by the model; not a leak)", "",
            "| token | firms |", "|---|---|"]
    for tok, firms in sorted(inferred.items(), key=lambda kv: -len(kv[1]))[:80]:
        out.append(f"| {tok} | {', '.join(sorted(firms)[:6])} |")
    REVIEW.write_text("\n".join(out) + "\n", encoding="utf-8")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--conditions", default="A,B")
    ap.add_argument("--limit", type=int, default=None, help="first N firms only")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    model = cfg.require_model("comparison")
    key = "" if args.dry_run else require_env(model.api_key_env)
    round_dir = CACHE / f"round{args.round}"
    round_dir.mkdir(parents=True, exist_ok=True)
    firms = sorted(pl.load_sample()["firm_id"])[: args.limit]
    jobs = [(f, c) for f in firms for c in args.conditions.split(",")]
    with ThreadPoolExecutor(max_workers=model.max_concurrency) as ex:
        records = list(ex.map(lambda j: run_one(model, key, round_dir, *j, args.dry_run), jobs))
    if args.dry_run:
        chars = sum(r["prompt_chars"] for r in records)
        print(f"dry run: {len(records)} prompts, {chars:,} characters")
        return 0
    tin = sum(r.get("usage", {}).get("prompt_tokens", 0) for r in records)
    # thinking tokens are billed as output but may be missing from completion_tokens
    tout = sum(max(r.get("usage", {}).get("total_tokens", 0)
                   - r.get("usage", {}).get("prompt_tokens", 0),
                   r.get("usage", {}).get("completion_tokens", 0)) for r in records)
    cost = (tin * model.price_in_per_mtok + tout * model.price_out_per_mtok) / 1e6
    n = write_review(records, args.round, set(pl.load_overrides()["ignore"]), cost)
    print(f"prompts: {len(records)}; tokens in/out: {tin:,}/{tout:,}; cost ≈ ${cost:.2f}; "
          f"candidate tokens present in text: {n}")
    print(f"review: {REVIEW}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
