"""Checks against answers that can be worked out by hand."""

import numpy as np
import pytest

from mcsim.core import MONTH, TD, block_bootstrap, fv_lump_and_monthly, history_stats, simulate_asset, summarise


def constant(annual: float, T: int = 600) -> np.ndarray:
    return np.full(T, (1 + annual) ** (1 / TD) - 1)


@pytest.mark.parametrize("g", [0.0, 0.05, 0.10])
def test_lump_sum_with_no_randomness_equals_compound_growth(g):
    sim = simulate_asset(constant(g), 10_000, 0, 10, n_paths=20, block=20, seed=1)
    assert sim["end"] == pytest.approx(10_000 * (1 + g) ** 10, rel=1e-9)
    assert sim["growth"] == pytest.approx(g, abs=1e-12)
    assert sim["mdd"].max() == pytest.approx(0, abs=1e-12)


@pytest.mark.parametrize("g", [0.0, 0.07])
def test_monthly_contributions_match_the_closed_form(g):
    sim = simulate_asset(constant(g), 5_000, 200, 3, n_paths=10, block=20, seed=1)
    assert sim["end"] == pytest.approx(fv_lump_and_monthly(5_000, 200, g, 3), rel=1e-9)
    n_months = (3 * TD - 1) // MONTH
    assert sim["invested"] == 5_000 + 200 * n_months


def test_haircut_lowers_growth_by_roughly_that_amount():
    base = simulate_asset(constant(0.08), 1, 0, 5, 10, 20, 1)["growth"][0]
    cut = simulate_asset(constant(0.08), 1, 0, 5, 10, 20, 1, haircut=0.03)["growth"][0]
    assert base - cut == pytest.approx(0.03, abs=0.005)   # subtracted from daily returns, so close to 3 points


def test_known_crash_is_caught():
    n = 5 * TD
    r = np.zeros(n + 1)
    r[300] = -0.40
    sim = simulate_asset(r, 1_000, 0, 5, n_paths=5, block=n, seed=0)   # one block = whole path keeps the order
    assert sim["mdd"].min() == pytest.approx(-0.40, abs=1e-12)
    s = summarise(sim)
    assert s["p_fall_30"] == 1.0 and s["p_fall_40"] == 0.0   # exactly -40% is not "worse than -40%"
    assert s["p_loss"] == 1.0


def test_regime_counts_follow_the_rule():
    # steady +0.2% a day: every 20-day return is about +4%, so every labelled day is Bull
    sim = simulate_asset(np.full(600, 0.002), 1, 0, 2, 5, 20, 1)
    assert (sim["regime"][:, 2] == sim["regime"].sum(axis=1)).all()
    assert history_stats(np.full(600, -0.002))["regime_now"] == "Bear"


def test_same_seed_same_result():
    rng = np.random.default_rng(0)
    r = rng.normal(0.0004, 0.01, 1500)
    a = simulate_asset(r, 1, 0, 5, 300, 20, 9)["end"]
    b = simulate_asset(r, 1, 0, 5, 300, 20, 9)["end"]
    c = simulate_asset(r, 1, 0, 5, 300, 20, 10)["end"]
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_bootstrap_keeps_mean_and_cross_correlation():
    rng = np.random.default_rng(3)
    common = rng.normal(0, 0.01, 3000)
    R = np.column_stack([common + rng.normal(0.0004, 0.004, 3000), 0.8 * common + rng.normal(0.0002, 0.005, 3000)])
    sample = np.concatenate(list(block_bootstrap(R, 2000, 20, 400, np.random.default_rng(1))), axis=0).reshape(-1, 2)
    assert np.corrcoef(sample.T)[0, 1] == pytest.approx(np.corrcoef(R.T)[0, 1], abs=0.01)
    assert sample.mean(axis=0) == pytest.approx(R.mean(axis=0), abs=2e-4)


def test_summary_probabilities_are_consistent():
    rng = np.random.default_rng(4)
    s = summarise(simulate_asset(rng.normal(0.0003, 0.012, 2000), 10_000, 0, 10, 2000, 20, 2))
    p = s["end_pcts"]
    assert p[5] <= p[25] <= p[50] <= p[75] <= p[95]
    assert 0 <= s["p_fall_40"] <= s["p_fall_30"] <= s["p_fall_20"] <= 1
    assert sum(s["regime_share"]) == pytest.approx(1, abs=0.02)
