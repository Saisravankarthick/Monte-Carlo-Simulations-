"""Audit of the Metropolis-Hastings code in mcsim/metropolis.py.

    uv run python -m mcsim.metropolis_audit --out results_metropolis

Every check compares the code against an answer known in advance:

  1. Exact kernel: on a 5-state target with a lopsided proposal, the transition probabilities the code produces
     match the Metropolis-Hastings formula, and that kernel satisfies detailed balance and leaves the target unchanged.
  2. Markov property: the next state's distribution given the current state does not change when the previous
     state is also known.
  3. Hastings correction: with a lopsided proposal the chains hit the right distribution (Gamma(2, 1)), and
     dropping the correction (a deliberate negative control) gives the wrong one.
  4. Banana at T = 1: means and variances match the exact values within Monte Carlo error.
  5. Chains agree: Gelman-Rubin R-hat below 1.05 and a reasonable acceptance rate.
  6. Annealing reaches the minimum [1, 1, 0] from all three starts.
  7. Reproducible: the same seed gives exactly the same chains.
Exits with status 1 if any check fails.
"""

from __future__ import annotations

import argparse
import datetime as dt
import inspect
import sys
from pathlib import Path

import numpy as np

from .metropolis import EXACT, anneal, banana_sampling, batch_se, ess, mh_step, r_hat, run_chains

K = 5
PI = np.arange(1, K + 1) / np.arange(1, K + 1).sum()  # target 1:2:3:4:5
UP = 0.7  # proposal: one step up the ring with prob 0.7, down with 0.3 (not symmetric)


# ----------------------------------------------------------------------------- 1-2. discrete target
def _q(to: np.ndarray, frm: np.ndarray) -> np.ndarray:
    to, frm = np.asarray(to).astype(int), np.asarray(frm).astype(int)
    return np.where(to == (frm + 1) % K, UP, np.where(to == (frm - 1) % K, 1 - UP, 0.0))


def exact_kernel() -> np.ndarray:
    P = np.zeros((K, K))
    for i in range(K):
        for j in range(K):
            if i != j and _q(j, i) > 0:
                P[i, j] = _q(j, i) * min(1.0, PI[j] * _q(i, j) / (PI[i] * _q(j, i)))
        P[i, i] = 1 - P[i].sum()
    return P


def discrete_run(n_steps=50_000, m=40, seed=1, hastings=True):
    energy = lambda x: -np.log(PI[x[:, 0].astype(int)])  # noqa: E731
    propose = lambda x, rng, t: (x + np.where(rng.random(x.shape) < UP, 1, -1)) % K  # noqa: E731
    log_q = (lambda a, b: np.log(_q(a[:, 0], b[:, 0]))) if hastings else None
    x0 = np.arange(m)[:, None] % K
    run = run_chains(energy, x0, n_steps, propose, np.random.default_rng(seed), log_q=log_q)
    return run["path"][..., 0].astype(int)  # (n + 1, m)


def check_kernel(path) -> tuple[bool, str]:
    P = exact_kernel()
    db = np.abs(PI[:, None] * P - (PI[:, None] * P).T).max()
    stat = np.abs(PI @ P - PI).max()
    a, b = path[:-1].ravel(), path[1:].ravel()
    C = np.zeros((K, K))
    np.add.at(C, (a, b), 1)
    emp = C / C.sum(axis=1, keepdims=True)
    gap = np.abs(emp - P).max()
    freq = np.bincount(path[1000:].ravel(), minlength=K) / path[1000:].size
    tv = 0.5 * np.abs(freq - PI).sum()
    ok = db < 1e-12 and stat < 1e-12 and gap < 0.01 and tv < 0.01
    return ok, (f"detailed balance error {db:.1e}, stationarity error {stat:.1e}; code's transition probabilities vs "
                f"formula: largest gap {gap:.4f} over {a.size:,} steps; time in each state vs target: distance {tv:.4f}")


def check_markov(path) -> tuple[bool, str]:
    prev, cur, nxt = path[:-2].ravel(), path[1:-1].ravel(), path[2:].ravel()
    worst, cells = 0.0, 0
    for c in range(K):
        base = np.bincount(nxt[cur == c], minlength=K) / (cur == c).sum()
        for p in range(K):
            sel = (cur == c) & (prev == p)
            if sel.sum() < 5_000:
                continue
            cells += 1
            worst = max(worst, np.abs(np.bincount(nxt[sel], minlength=K) / sel.sum() - base).max())
    params = list(inspect.signature(mh_step).parameters)
    ok = worst < 0.015 and "path" not in params and "history" not in params
    return ok, (f"P(next | current, previous) vs P(next | current): largest gap {worst:.4f} across {cells} "
                f"(previous, current) pairs; mh_step takes only the current state ({', '.join(params[:2])})")


# ----------------------------------------------------------------------------- 3. continuous Hastings correction
def gamma_run(hastings=True, n_steps=60_000, m=16, seed=3, s=0.8):
    energy = lambda x: np.where(x[:, 0] > 0, x[:, 0] - np.log(np.abs(x[:, 0]) + 1e-300), np.inf)  # Gamma(2, 1)  # noqa: E731
    propose = lambda x, rng, t: x * np.exp(s * rng.normal(size=x.shape))  # log-normal: not symmetric  # noqa: E731
    log_q = (lambda a, b: -np.log(a[:, 0]) - np.log(a[:, 0] / b[:, 0]) ** 2 / (2 * s * s)) if hastings else None
    run = run_chains(energy, np.ones((m, 1)), n_steps, propose, np.random.default_rng(seed), log_q=log_q)
    return run["path"][5_000:, :, 0]


def check_gamma() -> tuple[bool, str]:
    d = gamma_run(True)
    se = batch_se(d)
    bad = gamma_run(False)
    ok = abs(d.mean() - 2) < 4 * se and abs(d.var() - 2) < 0.15 and abs(bad.mean() - 2) > 0.5
    return ok, (f"with the correction: mean {d.mean():.3f} (exact 2, ±{se:.3f}), variance {d.var():.3f} (exact 2); "
                f"negative control without it: mean {bad.mean():.3f}, wrong as expected")


# ----------------------------------------------------------------------------- 4-7. banana
def check_banana(smp) -> tuple[bool, str, list[str]]:
    s = smp["samples"]
    rows, ok = [], True
    est = {"mean_x": s[..., 0], "mean_y": s[..., 1], "var_x": (s[..., 0] - s[..., 0].mean()) ** 2,
           "var_y": (s[..., 1] - s[..., 1].mean()) ** 2}
    for k, draws in est.items():
        v, se = draws.mean(), batch_se(draws)
        z = (v - EXACT[k]) / se
        ok &= abs(z) < 4
        rows.append(f"| {k.replace('_', ' of ')} | {v:.4f} | {EXACT[k]:.4f} | ±{se:.4f} | {z:+.1f} | {'✅' if abs(z) < 4 else '❌'} |")
    return ok, f"all four within 4 standard errors (ESS of x {ess(s[..., 0]):,.0f}, of y {ess(s[..., 1]):,.0f})", rows


def check_mixing(smp) -> tuple[bool, str]:
    s = smp["samples"]
    rx, ry, acc = r_hat(s[..., 0]), r_hat(s[..., 1]), smp["accept"]
    ok = rx < 1.05 and ry < 1.05 and (0.1 < acc).all() and (acc < 0.6).all()
    return ok, f"R-hat x {rx:.3f}, y {ry:.3f}; acceptance {', '.join(f'{a * 100:.0f}%' for a in acc)} (healthy range 10-60%)"


def check_anneal() -> tuple[bool, str]:
    r = anneal()
    d = np.hypot(*(r["x"] - 1).T)
    r2 = anneal()
    ok = (d < 0.01).all() and (r["e"] < 1e-4).all()
    same = np.array_equal(r["path"], r2["path"])
    return ok and same, (f"distance to [1, 1]: {', '.join(f'{v:.4f}' for v in d)}; height z: "
                         f"{', '.join(f'{v:.1e}' for v in r['e'])}; same seed reproduces the run exactly: {'yes' if same else 'NO'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results_metropolis")
    a = ap.parse_args()

    path = discrete_run()
    smp = banana_sampling()
    c1, c2, c3 = check_kernel(path), check_markov(path), check_gamma()
    ok4, msg4, rows = check_banana(smp)
    c5, c6 = check_mixing(smp), check_anneal()
    checks = [("1. Exact kernel and detailed balance", *c1), ("2. Markov property", *c2),
              ("3. Hastings correction", *c3), ("4. Banana at T = 1 matches the exact answer", ok4, msg4),
              ("5. Chains agree (convergence)", *c5), ("6-7. Annealing reaches [1, 1, 0], reproducibly", *c6)]
    n_ok = sum(ok for _, ok, _ in checks)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    o = ["# Audit: Metropolis-Hastings", "", f"Run {now} · code: [`mcsim/metropolis.py`](../mcsim/metropolis.py) · "
         f"audit: [`mcsim/metropolis_audit.py`](../mcsim/metropolis_audit.py) · [← results](RESULTS.md)", "",
         f"**{n_ok} of {len(checks)} checks passed.**", "",
         "| Check | Result | Detail |", "|---|---|---|"]
    o += [f"| {name} | {'✅ pass' if ok else '❌ fail'} | {msg} |" for name, ok, msg in checks]
    o += ["", "## Banana at T = 1: estimates vs exact values", "",
          "Exact: x ~ Normal(1, 0.5) and y | x ~ Normal(x², 1/200), so mean x = 1, var x = 0.5, mean y = 1.5, var y = 2.505. "
          "The standard error uses batch means, which allows for the chains' autocorrelation.", "",
          "| Quantity | Estimate | Exact | Standard error | Gap in standard errors | Result |", "|---|---|---|---|---|---|", *rows, "",
          "## What each check means", "",
          "1. **Exact kernel.** A 5-state target (1:2:3:4:5) with a proposal that steps up 70% of the time. The code's observed "
          "transition probabilities match the Metropolis-Hastings formula, and that kernel satisfies detailed balance "
          "(π_i P_ij = π_j P_ji), the condition that makes the target the chain's long-run distribution.",
          "2. **Markov property.** Knowing the previous state as well as the current one does not change the odds of the next "
          "state, and the step function receives only the current state.",
          "3. **Hastings correction.** The q(x | y) / q(y | x) term matters when proposals are lopsided. With it, draws match "
          "Gamma(2, 1); without it (negative control) they do not, which shows the check can fail.",
          "4. **Known answer.** The banana distribution's moments are known exactly and the draws reproduce them.",
          "5. **Convergence.** Chains started far apart end up describing the same distribution (R-hat near 1).",
          "6-7. **Optimisation and reproducibility.** Lowering the temperature on a fixed schedule takes all three chains to "
          "[1, 1, 0], and the same seed gives the same result.", ""]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "AUDIT.md").write_text("\n".join(o))
    for name, ok, msg in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {msg}")
    print(f"audit: {n_ok}/{len(checks)} passed")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
