"""Fast checks of the Metropolis-Hastings engine and the ETF model (the full audit is mcsim/mh_audit.py)."""

import math

import numpy as np

from mcsim.mh_audit import PI, check_kernel, check_markov, discrete_run, exact_kernel, gamma_run
from mcsim.mh_etfs import derived, fit_fund, make_energy, moments, predict, sample_skew_t, unpack

TH = np.array([[0.0005, math.log(0.01), math.log(2.0), math.log(0.92)]])


def test_exact_kernel_has_detailed_balance():
    P = exact_kernel()
    assert np.allclose(P.sum(axis=1), 1) and (P >= 0).all()
    assert np.allclose(PI[:, None] * P, (PI[:, None] * P).T) and np.allclose(PI @ P, PI)


def test_engine_matches_kernel_and_is_markov():
    path = discrete_run(n_steps=20_000, m=40)
    assert check_kernel(path)[0] and check_markov(path)[0]


def test_hastings_correction_matters():
    assert abs(gamma_run(True, n_steps=20_000).mean() - 2) < 0.1
    assert abs(gamma_run(False, n_steps=20_000).mean() - 1) < 0.1  # without it the chain targets the wrong answer


def test_moment_formulas_match_simulation():
    mu, sig, nu, g = unpack(TH)
    x = mu + sig * sample_skew_t(np.random.default_rng(0), nu, g, 3_000_000)
    m, v = moments(TH)
    assert abs(x.mean() - m[0]) < 2e-5 and abs(x.var() / v[0] - 1) < 0.02


def test_energy_rejects_impossible_parameters():
    r = np.random.default_rng(1).normal(0, 0.01, 500)
    e = make_energy(r)(np.array([[0.0, math.log(0.01), 0.0, 0.0], [0.0, math.log(0.01), 800.0, 0.0]]))
    assert np.isfinite(e[0]) and np.isinf(e[1])


def test_fit_recovers_parameters_and_converges():
    mu, sig, nu, g = unpack(TH)
    r = mu + sig * sample_skew_t(np.random.default_rng(2), nu, g, 2520)
    fit = fit_fund(r, seed=3, steps=8_000, pilot=2_000, burn=2_000)
    d, truth = fit["derived"], derived(TH)
    assert fit["diag"]["rhat"] < 1.02 and 0.1 < fit["diag"]["accept"] < 0.6
    assert np.percentile(d["vol"], 1) < truth["vol"][0] < np.percentile(d["vol"], 99)
    assert abs(np.median(d["mean"]) - r.mean()) < 3 * d["mean"].std()


def test_parameter_uncertainty_widens_prediction():
    rng = np.random.default_rng(4)
    spread = TH + rng.normal(0, [0.0002, 0.02, 0.1, 0.02], size=(500, 4))
    u, f = predict(spread, 10_000, 5, 3000, seed=1), predict(TH, 10_000, 5, 3000, seed=1)
    wu, wf = np.subtract(*np.percentile(u["end"], [95, 5])), np.subtract(*np.percentile(f["end"], [95, 5]))
    assert u["values"].shape == (3000, 61) and (u["values"][:, 0] == 10_000).all() and wu > wf
