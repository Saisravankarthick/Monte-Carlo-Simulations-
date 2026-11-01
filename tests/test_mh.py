"""Fast checks of the Metropolis-Hastings engine and the ETF model (the full audit is mcsim/mh_audit.py)."""

import math

import numpy as np
from scipy.special import gammaln

from mcsim.mh_audit import PI, check_kernel, check_markov, discrete_run, exact_kernel, gamma_run
from mcsim.mh_etfs import (derived, fit_fund, log_lik, make_energy, predict, sample_skew_t, sample_z, simulate_returns,
                            skew_t_cdf, skew_t_std, unpack)

TH = np.array([[0.0005, math.log(0.97 / 0.03), math.log(0.1 / 0.9), math.log(4.0), math.log(0.92)]])
V = 0.011 ** 2


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


def test_shocks_have_mean_zero_and_variance_one():
    z = sample_z(np.random.default_rng(0), 4.5, 0.85, 3_000_000)
    assert abs(z.mean()) < 0.003 and abs(z.var() - 1) < 0.02


def test_skew_t_cdf_matches_simulation():
    x = sample_skew_t(np.random.default_rng(6), 4.5, 0.85, 1_000_000)
    for c in (-3.0, -1.0, 0.0, 0.7, 2.5):
        assert abs((x < c).mean() - skew_t_cdf(c, 4.5, 0.85)) < 0.002


def test_likelihood_matches_a_plain_loop():
    r = simulate_returns(TH, 400, np.random.default_rng(5), V)
    e_all = r - r.mean()
    q = unpack(TH, e_all.var())
    M, S = skew_t_std(q["nu"], q["gamma"])
    nu, g = q["nu"][0], q["gamma"][0]
    h, ll, hs = q["v"][0], 0.0, 0.0
    for e in e_all:
        hs += h
        z = e / math.sqrt(h)
        w = M[0] + S[0] * z
        w = w / g if w >= 0 else w * g
        ll += (math.log(2) - math.log(g + 1 / g) + gammaln((nu + 1) / 2) - gammaln(nu / 2) - 0.5 * math.log(nu * math.pi)
               - (nu + 1) / 2 * math.log1p(w * w / nu) + math.log(S[0]) - 0.5 * math.log(h))
        h = q["omega"][0] + q["alpha"][0] * e ** 2 + q["beta"][0] * h
    vm = hs / len(r) ** 2  # variance of the sample mean
    ll += -0.5 * (r.mean() - q["mu"][0]) ** 2 / vm - 0.5 * math.log(2 * math.pi * vm)
    assert abs(log_lik(TH, r)[0] - ll) < 1e-6 * abs(ll)


def test_energy_rejects_impossible_parameters():
    r = np.random.default_rng(1).normal(0, 0.01, 500)
    bad = TH.copy()
    bad[0, 3] = 800.0
    e = make_energy(r)(np.vstack([TH, bad]))
    assert np.isfinite(e[0]) and np.isinf(e[1])


def test_fit_recovers_parameters_and_converges():
    r = simulate_returns(TH, 2520, np.random.default_rng(2), V)
    fit = fit_fund(r, seed=3, steps=8_000, pilot=2_000, burn=2_000)
    d, truth = fit["derived"], derived(TH, V)
    assert fit["diag"]["rhat"] < 1.05 and 0.1 < fit["diag"]["accept"] < 0.6
    assert abs(np.median(d["mean"]) - r.mean()) < 0.3 * d["mean"].std()  # anchored to the actual average
    assert np.percentile(d["mean"], 1) < truth["mean"][0] < np.percentile(d["mean"], 99)
    assert np.percentile(d["persistence"], 1) < truth["persistence"][0] < np.percentile(d["persistence"], 99)


def test_parameter_uncertainty_widens_prediction():
    rng = np.random.default_rng(4)
    r = simulate_returns(TH, 1000, rng, V)
    spread = TH + rng.normal(0, [0.0002, 0.1, 0.1, 0.1, 0.02], size=(300, 5))
    u, f = predict(spread, r, 10_000, 5, 3000, seed=1), predict(TH, r, 10_000, 5, 3000, seed=1)
    wu, wf = np.subtract(*np.percentile(u["end"], [95, 5])), np.subtract(*np.percentile(f["end"], [95, 5]))
    assert u["values"].shape == (3000, 61) and (u["values"][:, 0] == 10_000).all() and wu > wf
