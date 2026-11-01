"""Metropolis-Hastings with Markov chains, shown on the Rosenbrock 'banana' function.

    uv run python -m mcsim.metropolis --out results_metropolis
    uv run python -m mcsim.metropolis_audit --out results_metropolis

The same sampler is used two ways:

  1. Annealing: the temperature T is lowered on a fixed schedule, so the chains settle on the minimum of
     f(x, y) = (1 - x)^2 + 100 (y - x^2)^2, which is [x, y, z] = [1, 1, 0] (the picture in the report).
  2. Sampling: at a fixed T = 1 the chains draw from p(x, y) ∝ exp(-f(x, y)). That distribution has exact
     answers (x ~ Normal(1, 0.5) and y | x ~ Normal(x², 1/200)), which the audit uses as a check.

Each step:  propose y from q(y | x);  accept with probability
            min(1, [p(y) q(x | y)] / [p(x) q(y | x)])   (the Hastings ratio);  otherwise stay at x.
Only the current state x enters a step, never the earlier path, so every chain is a Markov chain.
The temperature and step size follow a fixed schedule set in advance (not adapted from the path),
which keeps that property.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import numpy as np

A, B = 1.0, 100.0
MINIMUM = np.array([1.0, 1.0])
STARTS = np.array([[-0.2, -0.9], [-1.9, -0.8], [-1.9, 2.85]])  # chains 1-3, spread like the picture
COLORS = ["#00E5FF", "#FF3DF5", "#FFE600"]  # cyan, magenta, yellow
EXACT = {"mean_x": 1.0, "var_x": 0.5, "mean_y": 1.5, "var_y": 2.505}  # p ∝ exp(-f): see the module docstring


def rosenbrock(p) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    x, y = p[..., 0], p[..., 1]
    return (A - x) ** 2 + B * (y - x ** 2) ** 2


# ----------------------------------------------------------------------------- the algorithm
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
    return {"path": path, "energy": epath, "accept": accepted / n_steps, "x": x, "e": e, "temps": temps}


def gaussian_walk(scale):
    """Symmetric random-walk proposal; scale is a number or a per-step array (fixed schedule)."""
    sc = np.asarray(scale, dtype=float)
    return lambda x, rng, t: x + rng.normal(0.0, sc[t] if sc.ndim else sc, size=x.shape)


def anneal_schedule(n: int, t0: float = 1.0, t1: float = 1e-6) -> np.ndarray:
    return t0 * (t1 / t0) ** (np.arange(n) / (n - 1))


def step_schedule(temps: np.ndarray, s0: float = 0.15, smin: float = 0.001) -> np.ndarray:
    return np.clip(s0 * np.sqrt(temps / temps[0]), smin, s0)


def anneal(n: int = 30_000, seed: int = 42, keep_every: int = 10) -> dict:
    temps = anneal_schedule(n)
    return run_chains(rosenbrock, STARTS, n, gaussian_walk(step_schedule(temps)), np.random.default_rng(seed),
                      temps=temps, keep_every=keep_every)


def banana_sampling(n: int = 1_000_000, burn: int = 50_000, seed: int = 7, scale: float = 0.25) -> dict:
    starts = np.array([[-1.5, 2.5], [2.0, 3.0], [-1.0, -0.5], [1.5, 1.0]])
    run = run_chains(rosenbrock, starts, n, gaussian_walk(scale), np.random.default_rng(seed))
    run["samples"] = run["path"][burn + 1:]  # (n - burn, m, 2)
    return run


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
    return float(chains.var(ddof=1) / batch_se(chains) ** 2)


# ----------------------------------------------------------------------------- charts
def _banana_background(ax, xlim=(-2.0, 2.0), ylim=(-1.0, 3.0)):
    import matplotlib.pyplot as plt

    gx, gy = np.meshgrid(np.linspace(*xlim, 400), np.linspace(*ylim, 400))
    f = rosenbrock(np.stack([gx, gy], axis=-1))
    ax.pcolormesh(gx, gy, np.log10(1 + f), cmap=plt.get_cmap("turbo_r"), shading="auto", alpha=0.85)
    tri = np.linspace(xlim[0] - 4, xlim[1] + 4, 60)  # light triangular mesh, like the sample picture
    for c in tri:
        for slope in (np.sqrt(3), -np.sqrt(3)):
            ax.plot(gx[0], slope * (gx[0] - c), color="black", lw=0.25, alpha=0.35)
    for yy in np.linspace(*ylim, 30):
        ax.axhline(yy, color="black", lw=0.25, alpha=0.35)
    ax.contour(gx, gy, f, levels=[100], colors="#FFE600", linewidths=1.6)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xticks([])
    ax.set_yticks([])


def chart_chains(run: dict, out: Path, upto: int | None = None, ax=None, fig=None):
    import matplotlib.pyplot as plt

    path = run["path"] if upto is None else run["path"][: upto + 1]
    own = ax is None
    if own:
        fig = plt.figure(figsize=(10.24, 6.92), facecolor="black")
        ax = fig.add_axes([0.24, 0.06, 0.55, 0.80])
    _banana_background(ax)
    for k in range(path.shape[1]):
        ax.plot(path[:, k, 0], path[:, k, 1], color=COLORS[k], lw=1.0, alpha=0.9)
        ax.plot(*STARTS[k], "o", ms=6, mfc="none", mec=COLORS[k], mew=2)
        ax.plot(*path[-1, k], "o", ms=5, mfc="none", mec=COLORS[k], mew=2)
    ax.plot(*MINIMUM, "o", ms=7, mfc="none", mec="white", mew=2)
    fig.text(0.5, 0.94, "Metropolis-Hastings: Markov chains converging to [1 1 0]\nminimum of the Rosenbrock 'banana' function",
             color="white", ha="center", va="center", fontsize=14)
    total = (len(run["path"]) - 1)
    fig.text(0.03, 0.86, f"Iteration: {len(path) - 1} / {total}" + (" (×10)" if total < run["temps"].size else ""),
             color="white", fontsize=10)
    for k in range(path.shape[1]):
        x, y = path[-1, k]
        fig.text(0.03, 0.74 - 0.18 * k,
                 f"Markov chain n° {k + 1}\nx = {x:.5f}\ny = {y:.5f}\nz = {rosenbrock([x, y]):.2e}",
                 color=COLORS[k], fontsize=10, va="top", family="monospace")
    fig.text(0.81, 0.86, "Yellow line: f = 100", color="#FFE600", fontsize=10)
    fig.text(0.81, 0.80, "o  minimum [1 1 0]", color="white", fontsize=10)
    if own:
        fig.savefig(out, dpi=100, facecolor="black")
        plt.close(fig)


def chart_animation(run: dict, out: Path, frames: int = 40):
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter

    fig = plt.figure(figsize=(10.24, 6.92), facecolor="black")
    stops = np.unique(np.geomspace(1, len(run["path"]) - 1, frames).astype(int))

    def draw(i):
        fig.clf()
        ax = fig.add_axes([0.24, 0.06, 0.55, 0.80])
        chart_chains(run, out, upto=int(stops[i]), ax=ax, fig=fig)

    FuncAnimation(fig, draw, frames=len(stops)).save(out, writer=PillowWriter(fps=8), dpi=60,
                                                     savefig_kwargs={"facecolor": "black"})
    plt.close(fig)


def chart_convergence(run: dict, out: Path, keep_every: int):
    import matplotlib.pyplot as plt

    it = np.arange(len(run["energy"])) * keep_every
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, constrained_layout=True)
    for k in range(run["energy"].shape[1]):
        a1.plot(it, run["energy"][:, k] + 1e-12, color=COLORS[k], lw=1.4, label=f"Chain {k + 1}")
        d = np.linalg.norm(run["path"][:, k] - MINIMUM, axis=1)
        a2.plot(it, d, color=COLORS[k], lw=1.4)
    a1.set_yscale("log")
    a1.set_ylabel("f(x, y): height of the chain")
    a1.set_title("Annealing: each chain's height and distance to the minimum [1, 1]")
    a1.legend(frameon=False)
    a2.set_yscale("log")
    a2.set_ylabel("Distance to [1, 1]")
    a2.set_xlabel("Iteration")
    t = a1.twinx()
    t.plot(np.arange(run["temps"].size), run["temps"], color="#555", lw=1, ls="--")
    t.set_yscale("log")
    t.set_ylabel("Temperature T (dashed)")
    for ax in (a1, a2):
        ax.grid(alpha=0.3)
    fig.savefig(out, dpi=110)
    plt.close(fig)


def chart_sampling(run: dict, out: Path):
    import matplotlib.pyplot as plt

    s = run["samples"]
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.8), constrained_layout=True)
    ax = axs[0]
    _banana_background(ax, xlim=(-2.0, 3.0), ylim=(-1.0, 7.0))
    pts = s[::40].reshape(-1, 2)
    ax.scatter(pts[:, 0], pts[:, 1], s=2, color="white", alpha=0.5)
    ax.set_title("Draws at T = 1 follow the banana")
    ax = axs[1]
    ax.hist(s[..., 0].ravel(), bins=120, density=True, color="#4C78A8", alpha=0.75, label="Metropolis-Hastings draws")
    xs = np.linspace(-2, 4, 300)
    ax.plot(xs, np.exp(-(xs - 1) ** 2) / np.sqrt(np.pi), color="#E45756", lw=2, label="Exact: Normal(1, 0.5)")
    ax.set_title("x: draws vs the exact answer")
    ax.legend(frameon=False)
    ax = axs[2]
    n = min(4000, s.shape[0])
    for k in range(s.shape[1]):
        ax.plot(s[:n, k, 0], lw=0.6, alpha=0.8, label=f"Chain {k + 1}")
    ax.set_title(f"Trace of x, first {n:,} steps after burn-in")
    ax.legend(frameon=False, ncol=2, fontsize=8)
    fig.savefig(out, dpi=110)
    plt.close(fig)


# ----------------------------------------------------------------------------- report
def main() -> int:
    import matplotlib

    matplotlib.use("Agg")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results_metropolis")
    ap.add_argument("--steps", type=int, default=30_000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    out = Path(a.out)
    (out / "charts").mkdir(parents=True, exist_ok=True)

    keep = 10
    run = anneal(a.steps, a.seed, keep)
    chart_chains(run, out / "charts" / "chains_on_banana.png")
    chart_animation(run, out / "charts" / "chains_animation.gif")
    chart_convergence(run, out / "charts" / "convergence.png", keep)
    smp = banana_sampling()
    chart_sampling(smp, out / "charts" / "sampling_T1.png")

    s = smp["samples"]
    est = {"mean_x": s[..., 0].mean(), "var_x": s[..., 0].var(), "mean_y": s[..., 1].mean(), "var_y": s[..., 1].var()}
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    o = ["# Metropolis-Hastings: Markov chains on the Rosenbrock banana", "",
         f"Updated {now} · {len(STARTS)} chains · {a.steps:,} steps each · seed {a.seed} · code: [`mcsim/metropolis.py`](../mcsim/metropolis.py) · "
         "**[Audit of the algorithm →](AUDIT.md)**", "",
         "## How it works", "",
         "The target is the Rosenbrock function f(x, y) = (1 − x)² + 100 (y − x²)², a long curved valley whose lowest point is "
         "**[x, y, z] = [1, 1, 0]**. Each chain repeats one step:", "",
         "1. **Propose** a nearby point by adding a small random (Gaussian) move to the current point.",
         "2. **Accept** it with probability min(1, p(new) q(old | new) / [p(old) q(new | old)]), with p ∝ exp(−f / T). "
         "Downhill moves are always accepted; uphill moves sometimes, less often as T falls.",
         "3. Otherwise **stay** where it is (the step still counts).", "",
         "The next point depends only on the current point, not on how the chain got there: that is the **Markov property**. "
         "The temperature and step size follow a schedule fixed in advance, so it holds at every step.", "",
         "## 1. Three chains converging to the minimum (annealing)", "",
         f"Temperature lowered from {run['temps'][0]:g} to {run['temps'][-1]:g} over {a.steps:,} steps.", "",
         "![Chains on the banana](charts/chains_on_banana.png)", "",
         "![Animation](charts/chains_animation.gif)", "",
         "| Chain | Start | End x | End y | End z = f(x, y) | Distance to [1, 1] | Moves accepted |",
         "|---|---|---|---|---|---|---|"]
    for k in range(len(STARTS)):
        x, y = run["x"][k]
        o.append(f"| {k + 1} | ({STARTS[k][0]:g}, {STARTS[k][1]:g}) | {x:.5f} | {y:.5f} | {run['e'][k]:.2e} | "
                 f"{np.hypot(x - 1, y - 1):.4f} | {run['accept'][k] * 100:.0f}% |")
    o += ["", "![Convergence](charts/convergence.png)", "",
          "## 2. Sampling at a fixed temperature (T = 1)", "",
          "At a fixed temperature the same algorithm does not just find the minimum; it draws points in proportion to "
          "exp(−f). For this function the answer is known exactly, so the draws can be checked.", "",
          "![Sampling](charts/sampling_T1.png)", "",
          "| Quantity | Metropolis-Hastings | Exact |", "|---|---|---|"]
    names = {"mean_x": "Mean of x", "var_x": "Variance of x", "mean_y": "Mean of y", "var_y": "Variance of y"}
    o += [f"| {names[k]} | {est[k]:.3f} | {EXACT[k]:.3f} |" for k in EXACT]
    o += ["", f"{s.shape[1]} chains × {s.shape[0]:,} steps after burn-in · moves accepted {smp['accept'].mean() * 100:.0f}% · "
          f"Gelman-Rubin R̂ for x: {r_hat(s[..., 0]):.3f} (1.00 = chains agree) · effective sample size of x: {ess(s[..., 0]):,.0f}", "",
          "## Where this fits", "",
          "The ETF reports in this repo use a block-bootstrap Monte Carlo, which resamples real returns. "
          "Metropolis-Hastings is a different tool: Markov chain Monte Carlo (MCMC), used to draw from a distribution that "
          "can only be written up to a constant, such as the uncertainty in a model's parameters.", ""]
    (out / "RESULTS.md").write_text("\n".join(o))
    print("metropolis ok:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
