"""Draft Q5 (main business) keywords for human review.

For each sample firm: the FY2025 annual report's "II. 사업의 내용" (OpenDART document cache;
downloaded if missing), first 6,000 characters, is given to an LLM that returns 3-6 keywords
taken from the report text. The quiz answers of the main run are added for reference only;
they are NOT shown to the LLM (no answer leakage into the truth).

Writes data/ground_truth/q5_keywords.csv (UTF-8 with BOM for Excel). A person reviews and
edits the `main_business` column; scripts/apply_q5_keywords.py then writes it into
quiz_truth.parquet.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.agents.llm_client import make_client  # noqa: E402
from src.conditions import pipeline as pl  # noqa: E402
from src.config import PROJECT_ROOT, load_config  # noqa: E402
from src.data.dart_client import DartClient  # noqa: E402
from src.data.filler import section_texts  # noqa: E402
from src.parse.validate import extract_json  # noqa: E402

OUT = PROJECT_ROOT / "data" / "ground_truth" / "q5_keywords.csv"
PROMPT = """다음은 한국 상장회사 {name}의 사업보고서 'II. 사업의 내용' 앞부분입니다.

{text}

이 회사의 주력 사업 또는 주력 제품을 나타내는 한국어 키워드를 3~6개 고르십시오.
- 보고서에 나온 표현을 쓰고, 흔히 쓰는 동의어나 상위 개념(예: 'D램' → '메모리', '반도체')을 1~2개 포함하십시오.
- '사업', '제품', '서비스', '제조' 같은 일반적인 단어만으로 된 키워드는 쓰지 마십시오.
- 회사명, 브랜드명은 쓰지 마십시오.
JSON 하나로만 답하십시오: {{"keywords": ["...", "..."]}}"""


def quiz_answers() -> dict[str, str]:
    path = PROJECT_ROOT / "results" / "runs" / "E6.parquet"
    if not path.exists():
        return {}
    r = pd.read_parquet(path)
    r = r[(r["tag"] == "main") & r["valid"].eq(True)]
    out: dict[str, list[str]] = {}
    for _, row in r.iterrows():
        a = json.loads(row["output_json"]).get("q5_main_business")
        if a:
            out.setdefault(row["firm_id"], []).append(str(a))
    return {k: " / ".join(v) for k, v in out.items()}


def main() -> int:
    cfg = load_config()
    mcfg = cfg.require_model("primary")
    client = make_client(mcfg)
    dart = DartClient()
    sample = pl.load_sample()
    answers = quiz_answers()

    def one(row) -> dict:
        pkg = pl.load_package(row.firm_id)
        rcept = pkg.meta.source_rcept_no
        out = {"firm_id": row.firm_id, "group": row.group, "corp_name": pkg.meta.real_name,
               "industry": pl.industry_label((pkg.meta.ksic or "")[:2] or None),
               "keywords_draft": "", "main_business": "",
               "quiz_answers_reference": answers.get(row.firm_id, ""), "source_rcept_no": rcept,
               "note": ""}
        try:
            text = section_texts(dart.document(rcept), rcept).get("II.", "")[:6000]
        except Exception as e:  # noqa: BLE001 - recorded for the reviewer
            out["note"] = f"no section II: {e}"[:200]
            return out
        if not text:
            out["note"] = "section II empty"
            return out
        raw = client.complete([{"role": "user", "content": PROMPT.format(
            name=pkg.meta.real_name, text=text)}], mcfg)
        try:
            kws = [k.strip() for k in extract_json(raw.text)["keywords"] if k.strip()]
        except (ValueError, KeyError, TypeError):
            out["note"] = "could not parse LLM keywords"
            return out
        out["keywords_draft"] = out["main_business"] = "|".join(kws)
        return out

    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(one, sample.itertuples(index=False)))
    df = pd.DataFrame(rows).sort_values("firm_id")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"wrote {OUT}: {len(df)} firms; drafts {int((df['keywords_draft'] != '').sum())}; "
          f"notes {int((df['note'] != '').sum())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
