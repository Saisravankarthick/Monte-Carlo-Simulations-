"""Metropolis-Hastings engine (Markov chain Monte Carlo), used by mcsim/mh_etfs.py.

Each step:  propose y from q(y | x);  accept with probability
            min(1, [p(y) q(x | y)] / [p(x) q(y | x)])   (the Hastings ratio);  otherwise stay at x.
Only the current state x enters a step, never the earlier path, so every chain is a Markov chain.
Proposals are fixed before a chain starts (never adapted from its own path), which keeps that property.
"""

from __future__ import annotations

import numpy as np


def mh_step(x, e_x, energy, T, propose, rng, log_q=None):
    """One Metropolis-Hastings step for m chains at once.

    x: (m, d) current states, e_x: (m,) their energies. Target density ∝ exp(-energy / T).
    propose(x, rng) -> (m, d) candidates. log_q(a, b) = log density of proposing a when at b;
    None means the proposal is symmetric, so the q terms cancel (plain Metropolis).
    Returns the new states, their energies and which chains accepted.
    """
    y = propose(x, rng)
    e_y = energy(y)
    log_alpha = (e_x - e_y) / T
    if log_q is not None:
        log_alpha = log_alpha + log_q(x, y) - log_q(y, x)  # Hastings correction: q(x | y) / q(y | x)
    log_alpha = np.where(np.isfinite(e_y), log_alpha, -np.inf)  # outside the support: always reject
    acc = np.log(rng.random(len(x))) < log_alpha
    return np.where(acc[:, None], y, x), np.where(acc, e_y, e_x), acc


def run_chains(energy, x0, n_steps, propose, rng, temps=1.0, log_q=None, keep_every=1) -> dict:
    """Run m chains for n_steps. propose(x, rng, t) may depend on the step number t (a fixed schedule)."""
    x = np.array(x0, dtype=float)
    temps = np.broadcast_to(np.asarray(temps, dtype=float), (n_steps,))
    e = energy(x)
    n_keep = n_steps // keep_every + 1
    path, epath = np.empty((n_keep, *x.shape)), np.empty((n_keep, len(x)))
    path[0], epath[0] = x, e
    accepted = np.zeros(len(x))
    for t in range(n_steps):
        x, e, acc = mh_step(x, e, energy, temps[t], lambda z, r: propose(z, r, t), rng, log_q)
        accepted += acc
        if (t + 1) % keep_every == 0:
            path[(t + 1) // keep_every], epath[(t + 1) // keep_every] = x, e
    return {"path": path, "energy": epath, "accept": accepted / n_steps, "x": x, "e": e}


def gaussian_walk(scale):
    """Symmetric random-walk proposal with independent coordinates; scale is a number or one per coordinate."""
    sc = np.asarray(scale, dtype=float)
    return lambda x, rng, t: x + rng.normal(size=x.shape) * sc


def correlated_walk(cov):
    """Symmetric random-walk proposal with a fixed covariance matrix."""
    L = np.linalg.cholesky(np.asarray(cov, dtype=float))
    return lambda x, rng, t: x + rng.standard_normal(x.shape) @ L.T


# ----------------------------------------------------------------------------- diagnostics
def r_hat(chains: np.ndarray) -> float:
    """Gelman-Rubin statistic for (n, m) draws; close to 1 when the chains agree."""
    n = chains.shape[0]
    W = chains.var(axis=0, ddof=1).mean()
    Bn = n * chains.mean(axis=0).var(ddof=1)
    return float(np.sqrt(((n - 1) / n * W + Bn / n) / W))


def batch_se(chains: np.ndarray, n_batches: int = 50) -> float:
    """Monte Carlo standard error of the mean of (n, m) draws by batch means (allows for autocorrelation)."""
    n = chains.shape[0] // n_batches * n_batches
    bm = chains[:n].reshape(n_batches, -1, chains.shape[1]).mean(axis=1).ravel()
    return float(bm.std(ddof=1) / np.sqrt(len(bm)))


def ess(chains: np.ndarray) -> float:
    """Effective sample size: how many independent draws the correlated chains are worth."""
    return float(chains.var(ddof=1) / batch_se(chains) ** 2)
