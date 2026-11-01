"""Checks against answers that can be worked out by hand."""

import numpy as np
import pytest

from mcsim.core import (SLEEVES, adjust_returns, block_bootstrap, contribution_metrics, fv_contributions,
                        pv_annuity_due, simulate)

START, END = 2027, 2033
CONTRIBS = {2027: 300_000.0, 2028: 150_000.0}
GLIDE = {y: [0.5, 0.3, 0.2] for y in range(START, END)}


def constant_returns(annual: float, T: int = 600) -> np.ndarray:
    d = (1 + annual) ** (1 / 252) - 1
    return np.full((T, 3), d)


def test_pv_annuity_due_matches_the_case_study_table():
    # Study pack section 3.1 table
    expected = {0.0: 500_000, 0.02: 458_112, 0.03: 439_305, 0.04: 421_767, 0.05: 405_391, 0.06: 390_085}
    for r, v in expected.items():
        assert pv_annuity_due(50_000, 10, r) == pytest.approx(v, abs=1)


def test_contributions_without_growth_are_450k():
    assert fv_contributions(CONTRIBS, 0.0, END) == 450_000
    # Study pack section 3.2: 4% gives $562,094
    assert fv_contributions(CONTRIBS, 0.04, END) == pytest.approx(562_094, abs=1)


@pytest.mark.parametrize("g", [0.0, 0.04, 0.07])
def test_simulation_with_no_randomness_equals_closed_form(g):
    sim = simulate(constant_returns(g), CONTRIBS, GLIDE, START, END, n_paths=50, block=20, seed=1)
    assert sim["v_final"] == pytest.approx(fv_contributions(CONTRIBS, g, END), rel=1e-9)
    assert sim["values"][:, 0] == pytest.approx(300_000)  # value right after the first contribution
    assert sim["mdd"].max() == pytest.approx(0, abs=1e-12)  # a steadily rising path has no fall


def test_sleeves_with_different_returns_are_weighted_by_the_glide_path():
    # one year only: weights 0.5 / 0.3 / 0.2, sleeves earning 10%, 5%, 0%
    d = np.array([1.10, 1.05, 1.00]) ** (1 / 252) - 1
    S = np.tile(d, (400, 1))
    sim = simulate(S, {2027: 100_000.0}, {2027: [0.5, 0.3, 0.2]}, 2027, 2028, n_paths=10, block=20, seed=1)
    assert sim["v_final"][0] == pytest.approx(100_000 * (0.5 * 1.10 + 0.3 * 1.05 + 0.2 * 1.00), rel=1e-9)


def test_same_seed_gives_same_result_and_different_seed_differs():
    rng = np.random.default_rng(0)
    S = rng.normal(0.0004, 0.01, (800, 3))
    a = simulate(S, CONTRIBS, GLIDE, START, END, 200, 20, seed=5)["v_final"]
    b = simulate(S, CONTRIBS, GLIDE, START, END, 200, 20, seed=5)["v_final"]
    c = simulate(S, CONTRIBS, GLIDE, START, END, 200, 20, seed=6)["v_final"]
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_bootstrap_keeps_correlation_and_mean():
    rng = np.random.default_rng(3)
    common = rng.normal(0, 0.01, 3000)
    R = np.column_stack([common + rng.normal(0.0004, 0.004, 3000), 0.8 * common + rng.normal(0.0002, 0.005, 3000)])
    sample = np.concatenate(list(block_bootstrap(R, 2000, 20, 400, np.random.default_rng(1))), axis=0).reshape(-1, 2)
    assert np.corrcoef(sample.T)[0, 1] == pytest.approx(np.corrcoef(R.T)[0, 1], abs=0.01)
    assert sample.mean(axis=0) == pytest.approx(R.mean(axis=0), abs=2e-4)


def test_adjust_returns_moves_the_average_and_applies_haircuts():
    rng = np.random.default_rng(2)
    S = rng.normal(0.0005, 0.01, (500, 3))
    A = adjust_returns(S, expected={"growth": 0.06}, haircuts={"matching": 0.02})
    assert A[:, 0].mean() * 252 == pytest.approx(0.06)
    assert (A[:, 1].mean() - S[:, 1].mean()) * 252 == pytest.approx(-0.02)
    assert np.array_equal(A[:, 2], S[:, 2])
    assert A[:, 0].std() == pytest.approx(S[:, 0].std())  # shape kept, only the centre moves


def test_drawdown_window_catches_a_crash():
    # flat, then one -40% day inside 2031, then flat. All sleeves identical so weights don't matter.
    sim_days = (END - START) * 252
    # one block as long as the whole path keeps the order; one spare day lets the bootstrap start at day 0 or 1,
    # and in both cases the crash day still falls inside 2031
    S = np.zeros((sim_days + 1, 3))
    S[4 * 252 + 100, :] = -0.40
    out = simulate(S, CONTRIBS, GLIDE, START, END, n_paths=5, block=sim_days, seed=0, window_years=(2031, 2032))
    assert out["dd_window"].min() == pytest.approx(-0.40, abs=1e-9)
    assert out["mdd"].min() == pytest.approx(-0.40, abs=1e-9)


def test_funding_metrics_are_consistent():
    v = np.array([400_000.0, 439_400.0, 500_000.0, 600_000.0])
    m = contribution_metrics(v, 50_000, 10, [0.03], flex_amount=10_000)[0.03]
    assert m["reserve"] == pytest.approx(439_305, abs=1)
    assert m["shortfall"] == pytest.approx(0.25)  # only 400,000 is below the reserve of about 439,305
    assert m["contrib_pcts"][50] == pytest.approx(np.median(v) - 439_305.0 - 10_000, abs=1)


def test_glide_weights_are_validated():
    bad = dict(GLIDE)
    bad[2030] = [0.5, 0.3, 0.3]
    with pytest.raises(ValueError):
        simulate(constant_returns(0.04), CONTRIBS, bad, START, END, 5, 20, 1)
    missing = {y: w for y, w in GLIDE.items() if y != 2029}
    with pytest.raises(ValueError):
        simulate(constant_returns(0.04), CONTRIBS, missing, START, END, 5, 20, 1)


def test_sleeve_order_constant():
    assert SLEEVES == ("growth", "matching", "flex")
