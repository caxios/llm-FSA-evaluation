"""P10: analysis helpers and hypothesis tests on synthetic firm tables with known answers."""

import math

import numpy as np
import pandas as pd
import pytest

from src.analysis.common import Result, dl_weighted_mean, holm, wilson
from src.analysis.rq1 import h1
from src.analysis.rq2 import decomposition_table, h2a, h2b
from src.analysis.rq3 import h3, h3b
from src.analysis.summary import apply_holm, verdict


def test_holm_matches_definition():
    assert holm([0.01, 0.04, 0.03, 0.2]) == pytest.approx([0.04, 0.09, 0.09, 0.2])
    assert math.isnan(holm([0.01, float("nan")])[1])


def test_dl_mean_reduces_to_fixed_effect_without_heterogeneity():
    est = np.array([1.0, 1.0, 1.0])
    mu, se, tau2 = dl_weighted_mean(est, np.array([0.1, 0.2, 0.1]))
    assert mu == pytest.approx(1.0) and tau2 == 0.0 and se < 0.1


def test_wilson_bounds():
    lo, hi = wilson(5, 10)
    assert lo < 0.5 < hi and 0 < lo and hi < 1


def firm_table(n=40, beta_l=0.7, e_mean=0.1, gamma=0.2, rdil=0.4, seed=0):
    rng = np.random.default_rng(seed)
    groups = np.repeat(["L", "M", "S"], [n, n, n])
    m = rng.uniform(0, 1, 3 * n)
    e = e_mean + gamma * (m - 0.5) + rng.normal(0, 0.02, 3 * n)
    beta_c = np.where(groups == "L", beta_l, 1.0) + rng.normal(0, 0.03, 3 * n)
    return pd.DataFrame({
        "firm_id": [f"{g}{i:03d}" for i, g in enumerate(groups)], "group": groups,
        "ksic2": rng.choice(["20", "26", "29", "46"], 3 * n),
        "market_cap": rng.lognormal(25, 1, 3 * n), "beta_C": beta_c,
        "se_C": np.full(3 * n, 0.05), "memory_eff": e, "memory_eff_se": np.full(3 * n, 0.02),
        "M_i": m, "id_rate_D": rng.uniform(0, 0.2, 3 * n),
        "industry_eff": rng.normal(0.02, 0.02, 3 * n), "name_eff": rng.normal(0, 0.02, 3 * n),
        "total_atten": e + 0.02, "itm_agent": groups == "S",
        "R_dil_V0": rdil + rng.normal(0, 0.05, 3 * n),
        "R_dil_V0_lo": rdil - 0.1, "R_dil_V0_hi": rdil + 0.1,
        "extraction_failure": 0.1, "reflection_failure": rng.uniform(0.3, 0.6, 3 * n),
        "computation_failure": 0.0, "success": 0.3})


def test_primary_tests_recover_built_in_effects():
    ft = firm_table()
    r1 = h1(ft)[0]
    assert r1.estimate == pytest.approx(0.7, abs=0.02) and r1.p < 1e-6
    r2 = h2a(ft)[0]
    assert r2.estimate > 0.05 and r2.p < 1e-6
    r3 = h2b(ft)[0][0]
    assert r3.estimate == pytest.approx(0.2, abs=0.03) and r3.p < 1e-6
    r4 = h3(ft)[0]
    assert r4.estimate == pytest.approx(0.4, abs=0.05) and r4.p < 1e-6
    res = [r1, r2, r3, r4]
    apply_holm(res)
    assert all(verdict(r) == "supported" for r in res)


def test_null_effects_are_not_supported():
    ft = firm_table(beta_l=1.0, e_mean=0.0, gamma=0.0, rdil=1.0)
    r1, r4 = h1(ft)[0], h3(ft)[0]
    apply_holm([r1, r4])
    assert verdict(r1) == "not supported" and verdict(r4) == "not supported"


def test_decomposition_and_stages():
    ft = firm_table()
    dec = decomposition_table(ft, n_boot=200)
    mem = dec[(dec["group"] == "all") & (dec["component"] == "memory_eff")].iloc[0]
    assert mem["ci_lo"] < mem["mean"] < mem["ci_hi"]
    res, tab = h3b(ft)
    assert res.estimate > 0 and res.p < 0.01 and set(tab["stage"]) >= {"success"}


def test_exploratory_verdicts():
    r = Result("H2c", "exploratory", "b2", 0.3, p=0.01)
    assert verdict(r).startswith("consistent")


def test_pooled_dl_recovers_mean_and_reports_heterogeneity():
    from src.analysis.pooled import dl_pool

    rng = np.random.default_rng(1)
    r = 0.8 + rng.normal(0, 0.05, 50)
    out = dl_pool(r, np.full(50, 0.05))
    assert out["mean"] == pytest.approx(0.8, abs=0.03) and out["p_vs_1"] < 1e-6
    assert out["p_vs_0"] < 1e-6 and 0 <= out["I2"] < 0.5 and out["k"] == 50
    wide = dl_pool(np.array([1.0, 5.0, -3.0]), np.array([0.1, 0.1, 0.1]))
    assert wide["I2"] > 0.9 and wide["tau2"] > 1
