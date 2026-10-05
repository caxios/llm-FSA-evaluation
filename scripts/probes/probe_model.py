"""Probe: candidate LLMs on one realistic valuation prompt (P0 Step 0.6).

Builds a Korean valuation prompt from the Samsung FY2024 CFS fixture (research plan Appendix B
system prompt, Appendix A schema), sends it N times to an OpenAI-compatible endpoint, and
reports JSON parse success, schema validity, populated intermediate values, tokens, latency.

Usage:
  python probe_model.py --dry-run                      # print the prompt only, no API call
  python probe_model.py --base-url https://api.deepinfra.com/v1/openai \
      --model meta-llama/Llama-4-Scout-17B-16E-Instruct --api-key-env PRIMARY_API_KEY -n 5
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time

import requests
from _common import FIXTURES, require_env, save_fixture, section
from pydantic import BaseModel, ValidationError, conlist

SYSTEM = """당신은 기업 가치평가를 수행하는 주식 애널리스트입니다.
아래에 제공되는 재무 자료를 사용해 5개년 FCFF 할인현금흐름(DCF)과 영구가치로
주당 적정가치를 산출하십시오.

규칙:
1. 결과는 지정된 JSON 스키마로만 출력하십시오.
2. 모든 중간 계산값(연도별 FCFF, 영구가치, 기업가치, 순차입금, 주주가치, 주식 수)을
   빠짐없이 기재하십시오.
3. 할인율과 성장률 등 가정의 근거를 assumption_rationale에 요약하십시오.
4. 제공된 자료에서 이상한 점을 발견하면 data_anomaly_flag를 true로 하고 내용을 기재하되,
   평가는 계속 수행하십시오.
5. 교차 확인을 위해 EV/EBITDA 배수 기준 주당가치도 함께 기재하십시오.
6. 주주가치 = 기업가치 - 순차입금 + 비영업자산, 주당가치 = 주주가치 / 사용 주식 수 로
   계산하고, 할인은 연말 기준(end_of_year)으로 하십시오.
7. 금액 단위는 백만 원, 주당가치는 원 단위로 기재하십시오. 비율은 소수(예: 0.08)로 기재하십시오.

JSON 스키마:
{"extracted": {"base_year": 0, "unit": "KRW_million", "revenue": 0, "operating_income": 0,
  "depreciation_amortization": 0, "capex": 0, "change_in_working_capital": 0,
  "cash_and_equivalents": 0, "total_borrowings": 0, "non_operating_assets": 0,
  "shares_outstanding": 0, "convertible_bonds_outstanding": null, "conversion_price": null},
 "assumptions": {"revenue_growth": [0,0,0,0,0], "operating_margin": [0,0,0,0,0],
  "tax_rate": 0, "wacc": 0, "terminal_growth": 0, "assumption_rationale": ""},
 "calculation": {"fcff": [0,0,0,0,0], "terminal_value": 0, "enterprise_value": 0,
  "net_debt": 0, "non_operating_assets_added": 0, "equity_value": 0, "shares_used": 0,
  "discounting_convention": "end_of_year"},
 "dilution": {"dilution_applied": false, "convertible_shares": null, "diluted_shares": null},
 "result": {"value_per_share": 0, "ev_ebitda_crosscheck_per_share": 0},
 "meta": {"data_anomaly_flag": false, "data_anomaly_note": "", "sources_used": ""}}"""


class Calc(BaseModel):
    fcff: conlist(float, min_length=5, max_length=5)
    terminal_value: float
    enterprise_value: float
    net_debt: float
    equity_value: float
    shares_used: float


class Result(BaseModel):
    value_per_share: float


class ProbeOutput(BaseModel):
    extracted: dict
    assumptions: dict
    calculation: Calc
    dilution: dict
    result: Result
    meta: dict


def render_statements() -> str:
    """Render the Samsung FY2025 CFS fixture (KRW million, 3 years).

    Lines are shown in DART `ord` order, which is not the display order of the filing; the
    real renderer (P2) restores the statement hierarchy. Good enough for a compliance probe.
    """
    data = json.loads((FIXTURES / "dart" / "fs_samsung_2025_CFS.json").read_text(encoding="utf-8"))
    rows = [r for r in data["list"] if r["sj_div"] in ("BS", "IS", "CF")]
    names = {"BS": "재무상태표", "IS": "손익계산서", "CF": "현금흐름표"}
    out = []
    header = f"{'계정':<28}{'FY2023':>14}{'FY2024':>14}{'FY2025':>14}"
    for sj in ("BS", "IS", "CF"):
        out.append(f"\n[{names[sj]}] (단위: 백만 원)\n{header}")
        for r in sorted((r for r in rows if r["sj_div"] == sj), key=lambda r: int(r["ord"])):
            vals = []
            for col in ("bfefrmtrm_amount", "frmtrm_amount", "thstrm_amount"):
                raw = (r.get(col) or "").replace(",", "").strip()
                if "PerShare" in r["account_id"]:
                    vals.append(f"{raw or '-':>14}")
                else:
                    vals.append(f"{round(float(raw) / 1e6):>14,}" if raw not in ("", "-") else
                                f"{'-':>14}")
            out.append(f"{r['account_nm'][:26]:<28}{''.join(vals)}")
    return "\n".join(out)


def render_shares() -> str:
    """Share counts from the stockTotqySttus fixture (FY2025 annual report)."""
    data = json.loads((FIXTURES / "dart" / "shares_samsung_2025.json").read_text(encoding="utf-8"))
    lines = []
    for r in data["list"]:
        if r["se"] in ("보통주", "우선주"):
            lines.append(f"{r['se']}: 발행주식 {r['istc_totqy']}주, 자기주식 {r['tesstk_co']}주, "
                         f"유통주식 {r['distb_stock_co']}주 (기준일 {r['stlm_dt']})")
    return "\n".join(lines)


def user_prompt() -> str:
    return (
        "[기업 정보]\n기업명: 삼성전자\n업종: 국내 전자부품·컴퓨터·통신장비 제조 기업\n\n"
        "[재무제표]" + render_statements() + "\n\n"
        "[주식 정보]\n" + render_shares() + "\n\n"
        "[주석 요약]\n(프로브용 생략)\n"
    )


def extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def call(base_url: str, model: str, key: str, temperature: float, json_mode: bool) -> dict:
    body = {"model": model, "temperature": temperature, "max_tokens": 4096,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": user_prompt()}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    t0 = time.perf_counter()
    resp = requests.post(f"{base_url.rstrip('/')}/chat/completions", json=body,
                         headers={"Authorization": f"Bearer {key}"}, timeout=300)
    latency = time.perf_counter() - t0
    resp.raise_for_status()
    data = resp.json()
    return {"text": data["choices"][0]["message"]["content"], "usage": data.get("usage", {}),
            "model_reported": data.get("model"), "latency": latency}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url")
    ap.add_argument("--model")
    ap.add_argument("--api-key-env", default="PRIMARY_API_KEY")
    ap.add_argument("-n", type=int, default=5)
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--json-mode", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    prompt = user_prompt()
    if args.dry_run:
        section("System prompt")
        print(SYSTEM)
        section("User prompt")
        print(prompt)
        print(f"\n(approx. characters: system={len(SYSTEM)}, user={len(prompt)})")
        return

    key = require_env(args.api_key_env)
    results = []
    for i in range(args.n):
        rec = {"rep": i}
        try:
            r = call(args.base_url, args.model, key, args.temperature, args.json_mode)
            rec.update(latency=r["latency"], usage=r["usage"], model_reported=r["model_reported"])
            parsed = extract_json(r["text"])
            rec["json_ok"] = True
            out = ProbeOutput.model_validate(parsed)
            rec["schema_ok"] = True
            rec["value_per_share"] = out.result.value_per_share
            rec["intermediates_populated"] = all(v != 0 for v in out.calculation.fcff)
        except ValidationError as exc:
            rec["schema_ok"] = False
            rec["error"] = str(exc)[:300]
        except Exception as exc:  # noqa: BLE001
            rec.setdefault("json_ok", False)
            rec["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        print(rec)
        results.append(rec)

    section("Summary")
    n = len(results)
    vals = [r["value_per_share"] for r in results if "value_per_share" in r]
    print(f"model={args.model} json_ok={sum(r.get('json_ok', False) for r in results)}/{n} "
          f"schema_ok={sum(r.get('schema_ok', False) for r in results)}/{n}")
    if vals:
        print(f"value_per_share median={statistics.median(vals):,.0f} "
              f"min={min(vals):,.0f} max={max(vals):,.0f}")
    lat = [r["latency"] for r in results if "latency" in r]
    if lat:
        print(f"latency median={statistics.median(lat):.1f}s")
    safe = args.model.replace("/", "_")
    save_fixture("models", f"probe_{safe}.json", results)


if __name__ == "__main__":
    main()
