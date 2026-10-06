"""P10: every preregistered test, robustness check, table and figure in one command.

  python scripts/run_analysis.py [--reuse] [--n-boot 1000]

Builds a firm table per variant (results/firm_level_<variant>.parquet; `--reuse` loads
existing ones), runs RQ1–RQ3, H4 and the robustness list, writes results/tables/*.csv,
results/figures/*, results/hypothesis_table.md and results/summary.md.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.analysis import figures, h4, pooled, robustness, rq1, rq2, rq3  # noqa: E402
from src.analysis.common import (  # noqa: E402
    TRUTH,
    VARIANTS,
    load_runs,
    provenance,
    results_frame,
    select,
    write_table,
)
from src.analysis.summary import (  # noqa: E402
    apply_holm,
    hypothesis_table,
    md,
    robustness_table,
    verdict,
)
from src.conditions import pipeline as pl  # noqa: E402
from src.config import CONFIG_DIR, PROJECT_ROOT  # noqa: E402
from src.metrics.firm_table import build_firm_table  # noqa: E402
from src.runner.jobs import SampleStore  # noqa: E402

OUT = PROJECT_ROOT / "results"
EXT = yaml.safe_load((CONFIG_DIR / "extensions.yaml").read_text(encoding="utf-8"))
REFS = {"H1": "T2", "H1b": "T3", "nonlinearity": "T3", "H1c": "T4", "H2a": "T5", "H2b": "T6",
        "H2c": "T7", "H2d": "T8", "H3": "T9", "H3c": "T9", "specificity": "T9", "H3b": "T10",
        "H4": "T11"}


def firm_tables(runs: pd.DataFrame, sample: pd.DataFrame, reuse: bool, n_boot: int
                ) -> dict[str, pd.DataFrame]:
    quiz = pd.read_parquet(TRUTH / "quiz_truth.parquet")
    anchors = pd.read_parquet(TRUTH / "anchor_prices.parquet")
    ids = {f: pl.load_identifiers(f) for f in sample["firm_id"]}
    out = {}
    for name, v in VARIANTS.items():
        if name == "ext_e10":            # no E0 cell; analysed from runs (e10_result)
            continue
        path = OUT / f"firm_level_{name}.parquet"
        if reuse and path.exists():
            out[name] = pd.read_parquet(path)
            continue
        r = select(runs, v)
        if r.empty:
            continue
        t0 = time.time()
        t = build_firm_table(r, sample=sample, quiz_truth=quiz, identifiers=ids,
                             anchors=anchors, n_boot=n_boot if name == "main" else 200)
        t = supplement_dilution(t, r, sample)
        t.insert(0, "variant", name)
        t.to_parquet(path, index=False)
        out[name] = t
        print(f"firm table {name}: {len(t)} rows ({time.time() - t0:.0f} s)")
    if out:
        pd.concat(out.values(), ignore_index=True).to_parquet(OUT / "firm_level.parquet",
                                                              index=False)
    return out


def supplement_dilution(t: pd.DataFrame, runs: pd.DataFrame, sample: pd.DataFrame
                        ) -> pd.DataFrame:
    """Add E8-only firms. `build_firm_table` keeps firms with an E0 cell only, so in the
    extensions the 10 E8 firms outside the E2 subset would be dropped (frozen metric code;
    the supplement uses the same metric functions)."""
    from src.metrics.dilution import firm_dilution
    from src.metrics.failure_modes import classify_runs, stage_shares

    val = runs[runs["schema_name"].fillna("valuation") == "valuation"]
    missing = set(val.loc[val["experiment"] == "E8", "firm_id"]) - set(t["firm_id"])
    if not missing:
        return t
    sub = val[val["firm_id"].isin(missing)]
    dil = firm_dilution(sub, 200)
    if dil.empty:
        return t
    basic = dict(zip(dil["firm_id"], dil["N_v1"], strict=False))
    dil = dil.merge(stage_shares(classify_runs(sub, basic)), how="left")
    dil = sample[["firm_id", "group", "ksic2", "market_cap", "newsworthiness",
                  "cb_complex"]].merge(dil, on="firm_id", how="right")
    if "variant" in t:
        dil.insert(0, "variant", t["variant"].iloc[0])
    return pd.concat([t, dil], ignore_index=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--n-boot", type=int, default=1000)
    args = ap.parse_args()
    runs = load_runs()
    sample = pl.load_sample()
    store = SampleStore()
    ft = firm_tables(runs, sample, args.reuse, args.n_boot)
    main_ft = ft["main"]
    main_runs = select(runs, VARIANTS["main"])
    results, figs = [], []

    # RQ1
    results += rq1.h1(main_ft)
    r, t3 = rq1.h1b(main_runs, sample)
    results += [r, rq1.nonlinearity(main_ft)]
    results.append(rq1.h1c(ft.get("ext_P", pd.DataFrame())))
    write_table(main_ft[["firm_id", "group", "beta_C", "se_C", "beta_A", "beta_B", "beta_D"]],
                "T2_betas", "Firm elasticities (main)")
    write_table(t3, "T3_pooled", "Pooled model log V ~ firm FE + log k x group")

    # RQ2
    results += rq2.h2a(main_ft)
    dec = rq2.decomposition_table(main_ft)
    write_table(dec, "T5_decomposition", "Decomposition of attenuation")
    h2b_res, t6 = rq2.h2b(main_ft)
    results += h2b_res
    write_table(t6, "T6_h2b", f"H2b regressions; VIF {t6.attrs.get('vif')}")
    results += [rq2.h2c(main_ft), rq2.h2d(main_ft)]

    # RQ3
    results += rq3.h3(main_ft)
    results.append(rq3.h3c(main_ft))
    spec, t9 = rq3.specificity(main_ft)
    results.append(spec)
    write_table(t9, "T9_placebo", "Placebo equivalence (TOST +- sigma)")
    h3b, t10 = rq3.h3b(main_ft)
    results.append(h3b)
    write_table(t10, "T10_stages", "E9 stage shares, ITM small caps (main)")

    # H4
    h4_tables = {"T": main_ft, "P": ft.get("ext_P"), "R": ft.get("ext_R")}
    h4_tables = {k: v for k, v in h4_tables.items() if v is not None}
    h4_res, t11 = h4.h4(h4_tables, EXT["e2_firms"], EXT["e8_firms"])
    results += h4_res
    write_table(t11, "T11_structures", "Structures P / R / T on the extension firms")

    # robustness
    results += robustness.r1_identified(main_ft)
    r2, tiers = robustness.r2_tiers(main_runs, store)
    results.append(r2)
    write_table(tiers, "R2_tiers", "R by perturbation tier")
    results.append(robustness.r3_half_reps(main_runs, sample))
    results += robustness.r4_anomaly(main_runs, sample)
    if "ext_cmp" in ft:
        results += robustness.r5_comparison(ft["ext_cmp"], main_ft, EXT["e2_firms"])
    if "ext_P" in ft and "ext_instr" in ft:
        results.append(robustness.r6_instruction(ft["ext_P"], ft["ext_instr"]))
    results.append(robustness.r7_complex_cb(sample))
    results += robustness.r8_low_validity(main_runs, sample)
    results += robustness.r9_median_beta(main_ft)
    e10 = e10_result(ft.get("ext_e10"), runs)
    if e10 is not None:
        results.append(e10)

    # pooled response ratios (exploratory, added after the main results)
    cells = pooled.cell_responses(main_runs, store)
    write_table(cells.drop(columns=["agent_structure", "model_key"], errors="ignore"),
                "T13_cell_responses", "Firm-cell response ratios (main, D7.5 applied)")
    pool = pooled.pooled_table(cells, main_ft)
    write_table(pool, "T14_pooled_R", "Pooled response ratios (DL random effects)")
    results += pooled.pooled_results(pool)

    apply_holm(results)
    write_table(results_frame(results), "all_results", "Every test and estimate")

    # figures
    figs += figures.f2_beta_by_group(main_ft)
    figs += figures.f3_decomposition(dec)
    figs += figures.f4_memory_scatter(main_ft)
    figs += figures.f5_dose_response(main_ft[main_ft["group"] == "S"])
    if not t11.empty:
        figs += figures.f6_stages(t11)
    if not tiers.empty:
        figs += figures.f7_tiers(tiers)
    figs += figures.f8_pooled(pool)

    write_reports(results, main_ft, dec, t10, t11, tiers, runs, pool)
    print(f"results: {len(results)}; figures: {len(figs) // 2}")
    for r in results:
        if r.kind == "primary":
            print(f"  {r.id}: {r.estimate:.4f} p={r.p:.4g} holm={r.p_holm:.4g} -> {verdict(r)}")
    return 0


def e10_result(ft_e10: pd.DataFrame | None, runs: pd.DataFrame):
    """E10: R_dil-style observed V0 - V1 change, front vs middle, paired by firm."""
    from scipy import stats

    from src.analysis.common import Result

    r = runs[(runs["experiment"] == "E10") & runs["valid"].eq(True)].copy()
    if r.empty:
        return None
    r["pos"] = r["job_id"].str.extract(r"pos=(\w+)")[0]
    med = r.groupby(["firm_id", "pos", "perturbation_type"])["value_per_share"].median()
    rows = []
    for fid in r["firm_id"].unique():
        try:
            rows.append({"firm_id": fid,
                         "front": med.loc[(fid, "front", "cb_v0")]
                         - med.loc[(fid, "front", "cb_v1")],
                         "middle": med.loc[(fid, "middle", "cb_v0")]
                         - med.loc[(fid, "middle", "cb_v1")]})
        except KeyError:
            continue
    d = pd.DataFrame(rows).dropna()
    write_table(d, "T12_e10", "E10: V0 - V1 median change by CB position")
    if len(d) < 3:
        return Result("E10", "exploratory", "median |front| - |middle| change", float("nan"),
                      n=len(d))
    diff = d["front"].abs() - d["middle"].abs()
    p = stats.wilcoxon(diff).pvalue if (diff != 0).any() else float("nan")
    return Result("E10", "exploratory", "median paired |dV front| - |dV middle| (KRW)",
                  float(diff.median()), p=float(p), n=len(d),
                  note="positive = the CB block moves the value more at the front")


def write_reports(results, main_ft, dec, t10, t11, tiers, runs, pool=None) -> None:
    head = f"_Generated {datetime.now():%Y-%m-%d %H:%M} ({provenance()})_"
    (OUT / "hypothesis_table.md").write_text(
        "# Hypothesis table\n\n" + head + "\n\n" + hypothesis_table(results, REFS) + "\n",
        encoding="utf-8")
    counts = runs.groupby(["tag", "agent_structure", "model_key", "prompt_version"]).agg(
        runs=("job_id", "size"), valid=("valid", "mean")).reset_index()
    text = ["# Results summary (P10)", "", head, "",
            "## Hypotheses", "", hypothesis_table(results, REFS), "",
            "## Robustness", "", robustness_table(results), "",
            "## Decomposition (T5)", "", md(dec), "",
            "## E9 stages, ITM small caps (T10)", "", md(t10), "",
            "## Structures (T11)", "", md(t11), "",
            "## R by tier (R2)", "", md(tiers), "",
            "## Pooled response ratios (T14, exploratory)", "",
            md(pool[["label", "size", "group", "k", "mean", "ci_lo", "ci_hi", "p_vs_1",
                     "p_vs_0", "I2", "median_unweighted"]]) if pool is not None else "", "",
            "## Firm counts", "",
            md(main_ft.groupby("group").agg(firms=("firm_id", "nunique"),
                                            beta_C_median=("beta_C", "median")).reset_index()),
            "", "## Runs by variant", "", md(counts)]
    (OUT / "summary.md").write_text("\n".join(text) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
