"""Fast versions of the Metropolis-Hastings audit (the full audit is mcsim/metropolis_audit.py)."""

import numpy as np

from mcsim.metropolis import anneal, banana_sampling, mh_step, r_hat, rosenbrock
from mcsim.metropolis_audit import PI, check_kernel, check_markov, discrete_run, exact_kernel, gamma_run


def test_minimum_of_rosenbrock():
    assert rosenbrock([1.0, 1.0]) == 0 and rosenbrock([0.0, 0.0]) == 1


def test_exact_kernel_has_detailed_balance():
    P = exact_kernel()
    assert np.allclose(P.sum(axis=1), 1) and (P >= 0).all()
    assert np.allclose(PI[:, None] * P, (PI[:, None] * P).T)
    assert np.allclose(PI @ P, PI)


def test_code_matches_kernel_and_is_markov():
    path = discrete_run(n_steps=20_000, m=40)
    assert check_kernel(path)[0]
    assert check_markov(path)[0]


def test_hastings_correction_matters():
    good, bad = gamma_run(True, n_steps=20_000), gamma_run(False, n_steps=20_000)
    assert abs(good.mean() - 2) < 0.1
    assert abs(bad.mean() - 1) < 0.1  # without the correction the chain targets Gamma(1), the wrong answer


def test_downhill_always_accepted_uphill_never_at_zero_temperature():
    rng = np.random.default_rng(0)
    x = np.array([[0.0, 0.0], [0.0, 0.0]])
    steps = iter([np.array([[0.5, 0.25], [-1.0, 1.0]])])  # first improves f, second makes it worse
    nx, ne, acc = mh_step(x, rosenbrock(x), rosenbrock, 1e-12, lambda z, r: next(steps), rng)
    assert acc.tolist() == [True, False] and np.allclose(nx[1], [0, 0])


def test_annealing_reaches_minimum_and_is_reproducible():
    a, b = anneal(), anneal()
    assert (np.hypot(*(a["x"] - 1).T) < 0.01).all()
    assert np.array_equal(a["path"], b["path"])


def test_banana_sampling_short_run():
    s = banana_sampling(n=200_000, burn=20_000)["samples"]
    assert abs(s[..., 0].mean() - 1) < 0.2 and abs(s[..., 0].var() - 0.5) < 0.2
    assert r_hat(s[..., 0]) < 1.1
