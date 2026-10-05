"""P3: perturbation size rule (§6.8 v0.2, D3.5)."""

import math

import pytest

from src.config import ExperimentsConfig
from src.perturb.sizing import decide_size, lower_bound_per_share, tier_sizes

CFG = ExperimentsConfig()      # n 10..40 step 5, s* 0.1, floor 5%, cap 10%
EQ = 100_000.0                 # equity value, KRW million
SHARES = 1e6


def test_lower_bound():
    assert lower_bound_per_share(1000, 10, 0.1) == pytest.approx(1000 * math.sqrt(0.2) / 0.1)


@pytest.mark.parametrize("sigma,status,n,x", [
    (1000, "ok", 10, 5_000.0),                                  # lb 4,472 -> 5% floor binds
    (1500, "ok", 10, 1500 * math.sqrt(0.2) / 0.1),              # lb 6,708 binds
    (2500, "increased_n", 15, 2500 * math.sqrt(2 / 15) / 0.1),  # lb@10 11,180 > cap 10,000
    (10_000, "excluded", 40, None),                             # lb@40 22,361 > cap
])
def test_non_operating_cases(sigma, status, n, x):
    d = decide_size("M001", "non_operating", 50_000, sigma, SHARES, EQ, None, CFG)
    assert (d.status, d.n) == (status, n)
    if x is None:
        assert d.x_mn is None and "exceeds" in d.reason
    else:
        assert d.x_mn == pytest.approx(x) and d.fraction == pytest.approx(x / EQ)


def test_cash_is_capped_by_cash_balance():
    # lb: n=10 4,472; 15 3,651; 20 3,162; 25 2,828 <= cash 3,000 -> X = cash
    d = decide_size("S001", "cash", 50_000, 1000, SHARES, EQ, 3_000.0, CFG)
    assert (d.status, d.n, d.x_mn) == ("increased_n", 25, 3_000.0)
    assert decide_size("S001", "cash", 50_000, 1000, SHARES, EQ, 0.0, CFG).status == "excluded"


def test_non_positive_equity_excluded():
    d = decide_size("S001", "non_operating", 50_000, 1000, SHARES, -5.0, None, CFG)
    assert d.status == "excluded"


def test_scale_and_shares_check_only():
    # smallest scale change: |0.8 - 1| = 0.2 -> 2,000 per share at v0 = 10,000
    assert decide_size("L001", "scale", 10_000, 400, SHARES, EQ, None, CFG).status == "ok"
    d = decide_size("L001", "scale", 10_000, 1000, SHARES, EQ, None, CFG)
    assert d.status == "excluded" and d.x_mn is None   # needs n >= 50
    d = decide_size("L001", "shares", 10_000, 1000, SHARES, EQ, None, CFG)
    assert (d.status, d.n) == ("ok", 10)                # change 5,000 >= 4,472


def test_unknown_perturbation():
    with pytest.raises(ValueError):
        decide_size("L001", "cb_v2", 1, 1, 1, 1, 1, CFG)


def test_tier_sizes():
    assert tier_sizes(EQ) == pytest.approx([2_000.0, 5_000.0, 10_000.0])
    assert tier_sizes(EQ, CFG.tiers) == pytest.approx([2_000.0, 5_000.0, 10_000.0])
