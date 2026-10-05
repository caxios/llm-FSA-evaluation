"""Memory strength M_i (E6; research plan Appendix C).

Numeric items (Q1-Q4) score 1 when within ±20% of the truth (Q3 also needs the right sign);
"모른다" (None) scores 0. Units follow the quiz prompt: Q1-Q3 in KRW 100 million (억 원),
Q4 in KRW. Q5 matches keywords from `quiz_truth.main_business` ("|"- or ","-separated);
without keywords, or when the answer is ambiguous, the item goes to a review list and is
left out of M_i until a person scores it. Q6 compares the market.
M_i = mean over items of the mean over reps; p_mem = median Q4 answer (used in E7).
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from src.metrics.cells import output

EOK_KRW = 1e8      # 억 원
EOK_MN = 100.0     # 억 원 in KRW million
TOL = 0.20
NUMERIC = {"q1_market_cap": ("market_cap_krw", EOK_KRW),
           "q2_revenue": ("revenue_prev_mn", EOK_MN),
           "q3_operating_income": ("op_income_prev_mn", EOK_MN),
           "q4_share_price": ("price", 1.0)}


def market_of(answer: str | None) -> str | None:
    if not answer:
        return None
    a = answer.replace(" ", "").upper()
    if "코스닥" in a or "KOSDAQ" in a:
        return "KOSDAQ"
    if any(t in a for t in ("유가증권", "코스피", "KOSPI", "거래소")):
        return "KOSPI"
    return None


def keywords(main_business: str | None) -> list[str]:
    if not main_business or not str(main_business).strip():
        return []
    return [k.strip() for k in re.split(r"[|,/]", str(main_business)) if k.strip()]


def score_numeric(answer, truth, unit: float, sign: bool = False) -> float:
    if answer is None or (isinstance(answer, float) and np.isnan(answer)) or truth is None \
            or (isinstance(truth, float) and np.isnan(truth)) or truth == 0:
        return 0.0
    value = float(answer) * unit
    if sign and np.sign(value) != np.sign(truth):
        return 0.0
    return 1.0 if abs(value / truth - 1) <= TOL else 0.0


def score_item_q5(answer: str | None, kws: list[str]) -> float | None:
    """1/0, or None when a person must decide (no keywords, or no match on a real answer)."""
    if not answer:
        return 0.0
    if not kws:
        return None
    norm = answer.replace(" ", "").lower()
    return 1.0 if any(k.replace(" ", "").lower() in norm for k in kws) else None


def score_quiz(responses: pd.DataFrame, truth: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(scores: firm x rep x item, review: answers that need a person)."""
    t = truth.set_index("firm_id")
    rows, review = [], []
    for _, r in responses[responses["valid"].eq(True)].iterrows():
        fid = r["firm_id"]
        if fid not in t.index:
            continue
        tr, ans = t.loc[fid], output(r)
        for item, (col, unit) in NUMERIC.items():
            rows.append({"firm_id": fid, "rep": r["rep"], "item": item,
                         "score": score_numeric(ans.get(item), tr[col], unit,
                                                sign=item == "q3_operating_income")})
        q5 = score_item_q5(ans.get("q5_main_business"), keywords(tr.get("main_business")))
        if q5 is None:
            review.append({"firm_id": fid, "rep": r["rep"], "answer": ans.get("q5_main_business"),
                           "keywords": tr.get("main_business")})
        rows.append({"firm_id": fid, "rep": r["rep"], "item": "q5_main_business", "score": q5})
        rows.append({"firm_id": fid, "rep": r["rep"], "item": "q6_market",
                     "score": 1.0 if market_of(ans.get("q6_market")) == tr["market"] else 0.0})
    return pd.DataFrame(rows), pd.DataFrame(review)


def memory_strength(scores: pd.DataFrame, responses: pd.DataFrame | None = None
                    ) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame(columns=["firm_id", "M_i"])
    item_means = scores.dropna(subset=["score"]).groupby(["firm_id", "item"])["score"].mean()
    out = item_means.groupby("firm_id").mean().rename("M_i").to_frame()
    out["n_items"] = item_means.groupby("firm_id").size()
    if responses is not None and not responses.empty:
        q4 = {}
        for _, r in responses[responses["valid"].eq(True)].iterrows():
            v = output(r).get("q4_share_price")
            if v is not None:
                q4.setdefault(r["firm_id"], []).append(float(v))
        out["p_mem"] = pd.Series({k: float(np.median(v)) for k, v in q4.items()})
    return out.reset_index()
