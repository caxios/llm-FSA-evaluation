"""Sample selection (P2 Step 2.5, research plan §6.2, decisions D8 / D2.5).

Inputs are plain DataFrames so the rules can be tested without data files:
  eligible: one row per firm with corp_code, market, market_cap, and exclusion flags
  newsworthiness: corp_code -> DART filing count over the 12 months before T_post
  small_candidates: KOSDAQ firms with in-the-money CBs and their dilution potential
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EXCLUSION_COLUMNS = ["excl_financial", "excl_halted", "excl_build", "excl_no_3y",
                     "excl_impairment", "excl_not_filed"]


def apply_exclusions(df: pd.DataFrame) -> pd.DataFrame:
    """Add `eligible` = no exclusion flag set (missing flags count as not excluded)."""
    out = df.copy()
    flags = out.reindex(columns=EXCLUSION_COLUMNS).eq(True)  # None / NaN count as False
    out["eligible"] = ~flags.any(axis=1)
    return out


def select_large(df: pd.DataFrame, n: int = 50) -> pd.DataFrame:
    kospi = df[(df["market"] == "KOSPI") & df["eligible"]]
    top = kospi.sort_values("market_cap", ascending=False).head(n).copy()
    top["group"] = "L"
    top["selection_reason"] = "KOSPI market-cap rank " + (np.arange(len(top)) + 1).astype(str)
    return top


def mid_band(df: pd.DataFrame, band: tuple[int, int]) -> pd.DataFrame:
    """Eligible KOSPI firms with market-cap rank in [low, high] (1 = largest)."""
    kospi = df[(df["market"] == "KOSPI") & df["eligible"]].sort_values("market_cap",
                                                                       ascending=False)
    kospi = kospi.assign(cap_rank=np.arange(1, len(kospi) + 1))
    lo, hi = band
    return kospi[(kospi["cap_rank"] >= lo) & (kospi["cap_rank"] <= hi)].copy()


def select_mid(band_df: pd.DataFrame, newsworthiness: pd.Series, n: int = 50,
               n_quintiles: int = 5, seed: int = 0) -> pd.DataFrame:
    """Cap-matched contrast in newsworthiness (D8): within each market-cap quintile, draw
    half of the firms from the top and half from the bottom newsworthiness tercile."""
    rng = np.random.default_rng(seed)
    df = band_df.copy()
    df["newsworthiness"] = df["corp_code"].map(newsworthiness)
    df = df.dropna(subset=["newsworthiness"])
    df["cap_quintile"] = pd.qcut(df["cap_rank"], n_quintiles, labels=False)
    per_q = n // n_quintiles
    picks = []
    for q, g in df.groupby("cap_quintile"):
        g = g.copy()
        g["news_tercile"] = pd.qcut(g["newsworthiness"].rank(method="first"), 3, labels=False)
        for tercile, tag in ((2, "high"), (0, "low")):
            pool = g[g["news_tercile"] == tercile]
            k = min(per_q // 2 + (per_q % 2 if tag == "high" else 0), len(pool))
            chosen = pool.iloc[rng.choice(len(pool), size=k, replace=False)] if k else pool[:0]
            chosen = chosen.assign(news_group=tag,
                                   selection_reason=f"mid quintile {q}, {tag} newsworthiness")
            picks.append(chosen)
    out = pd.concat(picks).sort_values(["cap_quintile", "news_group", "cap_rank"])
    out["group"] = "M"
    return out


MAX_DILUTION = 1.0   # ITM convertible shares above 100% of common shares: implausible / distressed


def select_small(candidates: pd.DataFrame, n: int = 50,
                 max_dilution: float = MAX_DILUTION) -> pd.DataFrame:
    """KOSDAQ firms with at least one in-the-money CB, ranked by plain-CB status (unknown
    terms rank with plain ones) and then dilution potential (§6.2). Firms whose ITM
    convertible shares exceed `max_dilution` of common shares are left out."""
    df = candidates[candidates["eligible"] & candidates["itm"]
                    & (candidates["dilution"] <= max_dilution)].copy()
    df["_complex"] = df["cb_complex"].eq(True)
    df = df.sort_values(["_complex", "dilution"], ascending=[True, False]).head(n)
    df["group"] = "S"
    df["selection_reason"] = ("ITM CB, dilution " + (df["dilution"] * 100).round(1).astype(str)
                              + "% of common shares")
    return df.drop(columns="_complex")


def assign_firm_ids(selected: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for group in ("L", "M", "S"):
        g = selected[selected["group"] == group].copy()
        g["firm_id"] = [f"{group}{i:03d}" for i in range(1, len(g) + 1)]
        parts.append(g)
    return pd.concat(parts, ignore_index=True)
