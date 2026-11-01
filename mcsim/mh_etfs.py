"""Metropolis-Hastings on the ETFs from the Markov model: how sure can we be of each fund's return and risk?

    uv run python -m mcsim.mh_etfs --config config/markov_etfs.toml --out results_mh_etfs
    uv run python -m mcsim.mh_audit --out results_mh_etfs

Model, per fund. Daily log returns are independent draws from a skewed Student-t (Fernández-Steel):
    r = mu + sigma * X,   X ~ skew-t(nu, gamma)
    nu    : tail weight (small = fat tails, crashes more common than a bell curve allows)
    gamma : skew (below 1 = bigger falls than rises)
Parameters theta = (mu, log sigma, log(nu - 2), log gamma). Weak priors:
    mu ~ N(0, 0.002^2)   log sigma ~ N(log 0.01, 1.5^2)   nu ~ Gamma(2, rate 0.1) on nu > 2   log gamma ~ N(0, 0.5^2)
Metropolis-Hastings draws theta from its posterior (4 chains). From each draw:
    growth a year     = exp(252 * mean daily log return) - 1
    volatility a year = sqrt(252 * variance of daily log returns)
Prediction: each simulated 10-year future first draws its own theta from the posterior, then 2,520 daily returns,
so the range includes both market randomness and the uncertainty in the fund's true return and risk.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from . import style
from .metropolis import correlated_walk, ess, gaussian_walk, r_hat, run_chains

TD = 252
PRIOR = {"mu_sd": 0.002, "log_sigma_mean": math.log(0.01), "log_sigma_sd": 1.5, "nu_rate": 0.1, "log_gamma_sd": 0.5}
PARAMS = ["mu", "log_sigma", "log_nu_minus_2", "log_gamma"]
_lgamma = np.vectorize(math.lgamma, otypes=[float])


# ----------------------------------------------------------------------------- model
def unpack(th):
    th = np.atleast_2d(th)
    with np.errstate(over="ignore"):
        return th[:, 0], np.exp(th[:, 1]), 2 + np.exp(th[:, 2]), np.exp(th[:, 3])


def log_prior(th) -> np.ndarray:
    th = np.atleast_2d(th)
    mu, ls, eta, lg = th.T
    _, _, nu, _ = unpack(th)
    with np.errstate(invalid="ignore", over="ignore"):  # impossible values give nan here and are rejected by the energy
        return _prior_terms(mu, ls, eta, lg, nu)


def _prior_terms(mu, ls, eta, lg, nu):
    return (-mu ** 2 / (2 * PRIOR["mu_sd"] ** 2)
            - (ls - PRIOR["log_sigma_mean"]) ** 2 / (2 * PRIOR["log_sigma_sd"] ** 2)
            + np.log(nu) - PRIOR["nu_rate"] * nu + eta  # Gamma(2, rate) density on nu, times the Jacobian d nu / d eta
            - lg ** 2 / (2 * PRIOR["log_gamma_sd"] ** 2))


def log_lik(th, r: np.ndarray) -> np.ndarray:
    """Skew-t log-likelihood of the daily log returns r, for each row of th."""
    mu, sig, nu, g = unpack(th)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        z = (r[None, :] - mu[:, None]) / sig[:, None]
        w = np.where(z >= 0, z / g[:, None], z * g[:, None])
        const = math.log(2) - np.log(g + 1 / g) + _lgamma((nu + 1) / 2) - _lgamma(nu / 2) - 0.5 * np.log(nu * np.pi) - np.log(sig)
        return len(r) * const - ((nu + 1) / 2) * np.log1p(w ** 2 / nu[:, None]).sum(axis=1)


def make_energy(r: np.ndarray):
    r = np.asarray(r, dtype=float)

    def energy(th):
        e = -(log_lik(th, r) + log_prior(th))
        return np.where(np.isfinite(e), e, np.inf)

    return energy


def abs_t_mean(nu):
    """E|T| for a standard Student-t with nu degrees of freedom."""
    return 2 * np.sqrt(nu) * np.exp(_lgamma((nu + 1) / 2) - _lgamma(nu / 2)) / ((nu - 1) * np.sqrt(np.pi))


def moments(th) -> tuple[np.ndarray, np.ndarray]:
    """Mean and variance of a daily log return under each parameter row."""
    mu, sig, nu, g = unpack(th)
    m1 = abs_t_mean(nu)
    mean = mu + sig * m1 * (g - 1 / g)
    ex2 = sig ** 2 * (nu / (nu - 2)) * (g ** 3 + g ** -3) / (g + 1 / g)
    return mean, ex2 - (sig * m1 * (g - 1 / g)) ** 2


def derived(th) -> dict:
    mean, var = moments(th)
    _, _, nu, g = unpack(th)
    return {"growth": np.expm1(TD * mean), "vol": np.sqrt(TD * var), "nu": nu, "gamma": g, "mean": mean}


def sample_skew_t(rng, nu, g, size):
    """Fernández-Steel skew-t draws: |T| scaled by gamma on the right, by 1/gamma on the left."""
    a = np.abs(rng.standard_t(nu, size=size))
    pos = rng.random(size) < g ** 2 / (1 + g ** 2)
    return np.where(pos, g * a, -a / g)


# ----------------------------------------------------------------------------- fitting
def fit_fund(r: np.ndarray, seed: int = 0, steps: int = 20_000, pilot: int = 4_000, burn: int = 4_000, m: int = 4) -> dict:
    """Pilot run to learn the proposal's shape, then the main chains with that proposal held fixed."""
    r = np.asarray(r, dtype=float)
    rng = np.random.default_rng(seed)
    n, s = len(r), r.std()
    energy = make_energy(r)
    base = np.array([np.median(r), math.log(0.75 * s), math.log(3.0), 0.0])
    starts = base + rng.normal(0, [3 * s / math.sqrt(n), 0.1, 0.5, 0.1], size=(m, 4))
    p = run_chains(energy, starts, pilot, gaussian_walk(np.array([s / math.sqrt(n), 0.7 / math.sqrt(n), 0.1, 0.02])), rng)
    cov = np.cov(p["path"][pilot // 2:].reshape(-1, 4).T) * 2.38 ** 2 / 4 + np.eye(4) * 1e-14
    main = run_chains(energy, p["x"], steps, correlated_walk(cov), rng)
    draws = main["path"][burn + 1:]  # (steps - burn, m, 4)
    d = derived(draws.reshape(-1, 4))
    per_chain = {k: d[k].reshape(draws.shape[0], m) for k in ("growth", "vol")}
    diag = {"rhat": max([r_hat(draws[..., j]) for j in range(4)] + [r_hat(v) for v in per_chain.values()]),
            "ess": min([ess(draws[..., j]) for j in range(4)] + [ess(v) for v in per_chain.values()]),
            "accept": float(main["accept"].mean())}
    return {"draws": draws, "theta": draws.reshape(-1, 4), "derived": d, "diag": diag, "per_chain": per_chain}


# ----------------------------------------------------------------------------- prediction
def predict(theta: np.ndarray, amount: float, years: int, n_paths: int, seed: int, chunk: int = 500) -> dict:
    """Simulated values: each path draws one parameter row from theta, then its daily returns."""
    rng = np.random.default_rng(seed)
    n_days = years * TD
    sample_idx = np.arange(0, n_days + 1, 21)
    values = np.empty((n_paths, len(sample_idx)))
    mdd = np.empty(n_paths)
    pick = rng.integers(0, len(theta), n_paths)
    for s0 in range(0, n_paths, chunk):
        sl = slice(s0, min(s0 + chunk, n_paths))
        mu, sig, nu, g = unpack(theta[pick[sl]])
        x = sample_skew_t(rng, nu[:, None], g[:, None], (len(mu), n_days))
        G = np.exp(np.cumsum(mu[:, None] + sig[:, None] * x, axis=1))
        G = np.concatenate([np.ones((len(mu), 1)), G], axis=1)
        values[sl] = amount * G[:, sample_idx]
        mdd[sl] = (G / np.maximum.accumulate(G, axis=1) - 1).min(axis=1)
    return {"values": values, "sample_idx": sample_idx, "end": values[:, -1], "mdd": mdd, "amount": amount}


def at_year(pred: dict, year: int) -> np.ndarray:
    return pred["values"][:, int(np.argmin(np.abs(pred["sample_idx"] - year * TD)))]


# ----------------------------------------------------------------------------- charts
def _hbar_interval(plt, funds, cols, med, lo, hi, dots, title, xlabel, out, pct=True):
    fig, ax = plt.subplots(figsize=(10, 0.42 * len(funds) + 1.6), constrained_layout=True)
    y = np.arange(len(funds))[::-1]
    ax.barh(y, med, color=[cols[f] for f in funds], alpha=0.85, height=0.62)
    ax.errorbar(med, y, xerr=[med - lo, hi - med], fmt="none", ecolor="#222", capsize=3, lw=1.1)
    ax.scatter(dots, y, color="black", zorder=3, s=18, label="Actual over the data window")
    ax.set_yticks(y, funds)
    ax.axvline(0, color="#888", lw=0.8)
    if pct:
        ax.xaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f}%")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.legend(loc="lower right")
    fig.savefig(out, dpi=120)
    plt.close(fig)


def chart_loss(plt, funds, cols, p_fixed, p_unc, years, out):
    fig, ax = plt.subplots(figsize=(10, 0.42 * len(funds) + 1.6), constrained_layout=True)
    y = np.arange(len(funds))[::-1]
    ax.barh(y + 0.18, p_fixed, height=0.36, color="#9AA5B1", label="Return and risk taken as known")
    ax.barh(y - 0.18, p_unc, height=0.36, color=[cols[f] for f in funds], label="Including uncertainty about them")
    for yy, v in zip(y, p_unc):
        ax.text(v + 0.005, yy - 0.18, f"{v * 100:.0f}%", va="center", fontsize=8)
    ax.set_yticks(y, funds)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f}%")
    ax.set_title(f"Chance of ending below the amount invested after {years} years")
    ax.legend(loc="lower right")
    fig.savefig(out, dpi=120)
    plt.close(fig)


def chart_fans(plt, funds, cols, preds, fixed, amount, years, out):
    n = len(funds)
    nc = 4
    nr = -(-n // nc)
    fig, axs = plt.subplots(nr, nc, figsize=(16, 3.1 * nr), constrained_layout=True)
    for ax in axs.ravel()[n:]:
        ax.axis("off")
    for ax, f in zip(axs.ravel(), funds):
        p, q = preds[f], fixed[f]
        t = p["sample_idx"] / TD
        lo, q1, md, q3, hi = np.percentile(p["values"], [5, 25, 50, 75, 95], axis=0)
        ax.fill_between(t, lo, hi, color=cols[f], alpha=0.18, lw=0)
        ax.fill_between(t, q1, q3, color=cols[f], alpha=0.38, lw=0)
        ax.plot(t, md, color=cols[f], lw=2)
        flo, fhi = np.percentile(q["values"], [5, 95], axis=0)
        ax.plot(t, flo, color="#555", lw=0.9, ls=":")
        ax.plot(t, fhi, color="#555", lw=0.9, ls=":")
        ax.axhline(amount, color="#888", lw=0.9, ls="--")
        ax.set_title(f"{f}: median {style.usd(md[-1])}", fontsize=10)
        ax.yaxis.set_major_formatter(style.money)
        ax.set_xlim(0, years)
    fig.suptitle("Predicted value: 5–95% (light), 25–75% (dark), median (line). Dotted: 5–95% if return and risk were known exactly.",
                 fontsize=11)
    fig.savefig(out, dpi=110)
    plt.close(fig)


# ----------------------------------------------------------------------------- report
def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def main() -> int:
    from .__main__ import load_config
    from .data import load_prices, returns_of

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/markov_etfs.toml")
    ap.add_argument("--out", default="results_mh_etfs")
    ap.add_argument("--returns", default=None, help="CSV of daily returns (default: download from Yahoo Finance)")
    ap.add_argument("--paths", type=int, default=10_000)
    ap.add_argument("--steps", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    cfg = load_config(a.config)
    amount, years = cfg["investment"]["amount"], cfg["investment"]["years"]
    funds_cfg = list(cfg["etfs"])
    if a.returns:
        R = pd.read_csv(a.returns, index_col=0, parse_dates=True)
    else:
        R = pd.DataFrame(returns_of(load_prices(funds_cfg, cfg["simulation"]["history_years"])))
    funds = [f for f in funds_cfg if f in R]
    out = Path(a.out)
    shutil.rmtree(out, ignore_errors=True)
    (out / "charts").mkdir(parents=True)
    (out / "tables").mkdir()
    R[funds].to_csv(out / "tables" / "returns_used.csv", float_format="%.10g")

    fits, preds, fixed, rows, prow = {}, {}, {}, [], []
    for i, f in enumerate(funds):
        r = np.log1p(R[f].dropna().to_numpy())
        fit = fit_fund(r, seed=a.seed + i, steps=a.steps)
        d = fit["derived"]
        preds[f] = predict(fit["theta"], amount, years, a.paths, seed=a.seed + 100 + i)
        fixed[f] = predict(np.median(fit["theta"], axis=0)[None, :], amount, years, a.paths, seed=a.seed + 200 + i)
        fits[f] = fit
        idx = R[f].dropna().index
        rows.append({"fund": f, "description": cfg["etfs"][f], "start": str(idx[0].date()), "end": str(idx[-1].date()),
                     "days": len(r), "sample_growth": math.expm1(TD * r.mean()), "sample_vol": r.std(ddof=1) * math.sqrt(TD),
                     **{f"growth_p{q}": np.percentile(d["growth"], q) for q in (5, 50, 95)}, "growth_sd": d["growth"].std(),
                     **{f"vol_p{q}": np.percentile(d["vol"], q) for q in (5, 50, 95)},
                     "nu_p50": np.median(d["nu"]), "gamma_p50": np.median(d["gamma"]),
                     "p_growth_below_0": float((d["growth"] < 0).mean()),
                     **{f"{k}_p50": v for k, v in zip(PARAMS, np.median(fit["theta"], axis=0))},
                     "rhat_max": fit["diag"]["rhat"], "ess_min": fit["diag"]["ess"], "accept": fit["diag"]["accept"]})
        for model, pr in (("uncertain", preds[f]), ("fixed", fixed[f])):
            for y in sorted({1, 3, 5, years}):
                v = at_year(pr, y)
                prow.append({"fund": f, "model": model, "year": y, **{f"p{q}": np.percentile(v, q) for q in (5, 25, 50, 75, 95)},
                             "p_loss": float((v < amount).mean()), "paths": a.paths})
        print(f"  {f}: growth {pct(np.median(d['growth']))} ({pct(np.percentile(d['growth'], 5))} to "
              f"{pct(np.percentile(d['growth'], 95))}), R-hat {fit['diag']['rhat']:.3f}, ESS {fit['diag']['ess']:.0f}")
    S = pd.DataFrame(rows).set_index("fund")
    P = pd.DataFrame(prow)
    S.to_csv(out / "tables" / "posterior_summary.csv", float_format="%.6g")
    P.to_csv(out / "tables" / "prediction_by_year.csv", index=False, float_format="%.6g")

    plt = style.setup()
    cols = style.fund_colors(funds)
    by_g = list(S.sort_values("growth_p50", ascending=False).index)
    _hbar_interval(plt, by_g, cols, S.loc[by_g, "growth_p50"].to_numpy(), S.loc[by_g, "growth_p5"].to_numpy(),
                   S.loc[by_g, "growth_p95"].to_numpy(), S.loc[by_g, "sample_growth"].to_numpy(),
                   "Long-run growth a year: most likely value and 90% range", "Growth a year", out / "charts" / "growth_ranges.png")
    by_v = list(S.sort_values("vol_p50", ascending=False).index)
    _hbar_interval(plt, by_v, cols, S.loc[by_v, "vol_p50"].to_numpy(), S.loc[by_v, "vol_p5"].to_numpy(),
                   S.loc[by_v, "vol_p95"].to_numpy(), S.loc[by_v, "sample_vol"].to_numpy(),
                   "Volatility a year: most likely value and 90% range", "Volatility a year", out / "charts" / "volatility_ranges.png")
    end = {f: P[(P.fund == f) & (P.year == years)].set_index("model") for f in funds}
    by_end = sorted(funds, key=lambda f: end[f].loc["uncertain", "p50"], reverse=True)
    chart_loss(plt, by_end, cols, [end[f].loc["fixed", "p_loss"] for f in by_end], [end[f].loc["uncertain", "p_loss"] for f in by_end],
               years, out / "charts" / "chance_of_loss.png")
    chart_fans(plt, by_end, cols, preds, fixed, amount, years, out / "charts" / "prediction_fans.png")

    boot = Path(cfg.get("report", {}).get("out", "results_markov_etfs")) / "tables" / "prediction_by_year.csv"
    bmed = pd.read_csv(boot).query("year == @years").set_index("fund")["p50"] if boot.exists() else pd.Series(dtype=float)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    short = [f for f in funds if S.loc[f, "days"] < 8 * TD]
    o = ["# Metropolis-Hastings: the Markov model ETFs", "",
         f"Updated {now} · {len(funds)} ETFs · daily Yahoo Finance prices (dividend-adjusted), last {cfg['simulation']['history_years']} years, "
         f"the same window as the Markov model · {style.usd(amount)} in each fund over {years} years · {a.paths:,} simulated futures per fund · "
         "**[Audit →](AUDIT.md)**", "",
         "> Research tool, not advice. The model learns only from each fund's last decade; a different decade would give different answers.", ""]
    if short:
        o += [f"> ⚠ Under 8 years of data: {', '.join(short)}. Their ranges are wider, which is the point of this method.", ""]
    o += ["## What this adds",
          "",
          "The bootstrap report takes each fund's past decade as the truth. But ten years of noisy returns only pin down a fund's "
          "true long-run return roughly. Metropolis-Hastings measures how roughly: it draws thousands of plausible "
          "(return, risk, tail, skew) combinations, each in proportion to how well it explains the actual daily returns. "
          "Each simulated future then uses one of those combinations, so the predictions carry that uncertainty.", "",
          "**Model:** daily log returns follow a skewed Student-t distribution, which allows fat tails (crashes) and bigger falls "
          "than rises. Four Markov chains per fund; the proposal's shape is learned in a pilot run and then held fixed, so the "
          "main chains keep the Markov property. Details: [`mcsim/mh_etfs.py`](../mcsim/mh_etfs.py).", "",
          "**Contents:** [1. Bar diagrams](#1-bar-diagrams) · [2. Simulation prediction](#2-simulation-prediction) · "
          "[3. Model estimates](#3-model-estimates) · [Notes](#notes)", "",
          "## 1. Bar diagrams", "",
          "### 1a. Long-run growth a year", "",
          "Bar: most likely value. Whisker: 90% range. Dot: what the fund actually returned over the data window.", "",
          "![Growth ranges](charts/growth_ranges.png)", "",
          "### 1b. Volatility a year", "", "![Volatility ranges](charts/volatility_ranges.png)", "",
          f"### 1c. Chance of losing money over {years} years", "",
          "Grey: if each fund's return and risk were known exactly. Colour: including uncertainty about them.", "",
          "![Chance of loss](charts/chance_of_loss.png)", "",
          "## 2. Simulation prediction", "",
          f"### 2a. Predicted value of {style.usd(amount)}, median (5th to 95th percentile)", "",
          "| Fund | What it is | " + " | ".join(f"Year {y}" for y in sorted({1, 3, 5, years})) +
          f" | Chance of loss | Bootstrap median, year {years} |", "|---|---|" + "---|" * len({1, 3, 5, years}) + "---|---|"]
    for f in by_end:
        u = P[(P.fund == f) & (P.model == "uncertain")].set_index("year")
        cells = [f"**{style.usd(u.loc[y, 'p50'])}** ({style.usd(u.loc[y, 'p5'])} – {style.usd(u.loc[y, 'p95'])})" for y in u.index]
        b = style.usd(bmed[f]) if f in bmed.index else "–"
        o.append(f"| **{f}** | {cfg['etfs'][f]} | " + " | ".join(cells) + f" | {pct(u.loc[years, 'p_loss'], 0)} | {b} |")
    o += ["", f"*Bootstrap median*: the same {years}-year median from the [block-bootstrap report](../results_markov_etfs/RESULTS.md), "
          "which resamples real 20-day blocks instead of fitting a model.", "",
          "### 2b. Predicted range over time", "", "![Prediction fans](charts/prediction_fans.png)", "",
          "## 3. Model estimates", "",
          "| Fund | Data | Growth a year: actual | Growth a year: model (90% range) | Chance true growth is below 0 | Volatility: actual | Volatility: model (90% range) | Tails ν | Skew γ |",
          "|---|---|---|---|---|---|---|---|---|"]
    for f in by_g:
        s = S.loc[f]
        o.append(f"| {f} | {s['start']} to {s['end']} ({s['days'] / TD:.1f} y) | {pct(s['sample_growth'])} | **{pct(s['growth_p50'])}** "
                 f"({pct(s['growth_p5'])} to {pct(s['growth_p95'])}) | {pct(s['p_growth_below_0'], 0)} | {pct(s['sample_vol'])} | "
                 f"{pct(s['vol_p50'])} ({pct(s['vol_p5'])} to {pct(s['vol_p95'])}) | {s['nu_p50']:.1f} | {s['gamma_p50']:.2f} |")
    o += ["", "*Tails ν*: below about 5 means crashes and spikes are far more common than a bell curve allows. "
          "*Skew γ*: below 1 means falls tend to be larger than rises.", "",
          "## Notes", "",
          "- Days are treated as independent. Real markets have calm and stormy spells; the bootstrap report keeps those, this model does not. "
          "The audit checks how much that matters for the return estimates.",
          "- The ranges describe uncertainty given this decade. They cannot include risks the decade never showed.",
          "- No taxes, inflation or currency effects beyond what is in the fund prices.", "",
          "**Files:** " + ", ".join(f"[`{p.name}`](charts/{p.name})" for p in sorted((out / 'charts').glob('*.png'))) + " · " +
          ", ".join(f"[`{p.name}`](tables/{p.name})" for p in sorted((out / 'tables').glob('*.csv'))), ""]
    (out / "RESULTS.md").write_text("\n".join(o))
    print("mh_etfs ok:", out, "-", len(funds), "funds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
