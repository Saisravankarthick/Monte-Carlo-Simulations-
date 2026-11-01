"""Metropolis-Hastings on the ETFs from the Markov model: how sure can we be of each fund's return and risk?

    uv run python -m mcsim.mh_etfs --config config/markov_etfs.toml --out results_mh_etfs
    uv run python -m mcsim.mh_audit --out results_mh_etfs

Model, per fund: a GARCH(1, 1) with skewed Student-t shocks, for daily log returns r_t.
    r_t = mu + s_t z_t                       z_t: skew-t(nu, gamma), rescaled to mean 0 and variance 1
    s_t^2 = v (1 - p) + alpha e_{t-1}^2 + beta s_{t-1}^2,   p = alpha + beta < 1
Today's volatility depends on recent days (calm and stormy spells); shocks have fat tails (nu) and can be
lopsided (gamma below 1 = bigger falls than rises).
  * Long-run variance v is set to the fund's actual variance (variance targeting), so the model's long-run
    volatility is the fund's actual volatility; the chains learn how volatility moves around it.
  * The average return mu is anchored to the fund's actual average: its likelihood is that of the sample mean,
    whose spread is the sum of the GARCH daily variances / n^2. Inferring mu from the fitted shape instead lets a small
    misfit in the crash tail move it by several points a year (found by the audit in an earlier version).
  * The shape (p, alpha / p, nu, gamma) is fitted to the shocks e_t = r_t - mean(r).
Parameters theta = (mu, logit p, logit a, log(nu - 2), log gamma), a = alpha / p. Weak priors:
    mu ~ N(0, 0.002^2)   logit p ~ N(2.5, 2^2)   logit a ~ N(-2, 1.5^2)   nu ~ Gamma(2, rate 0.1) on nu > 2
    log gamma ~ N(0, 0.5^2)
Metropolis-Hastings draws theta from its posterior (4 Markov chains per fund). Growth a year = exp(252 mu) - 1.
Prediction: each simulated 10-year future draws its own theta, starts from that theta's volatility on the last
day of data and runs the GARCH forward, so the range includes market randomness, today's volatility and the
uncertainty in the fund's true average return.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import lfilter
from scipy.special import expit, gammaln

from . import style
from .metropolis import correlated_walk, ess, gaussian_walk, r_hat, run_chains

TD = 252
PRIOR = {"mu_sd": 0.002, "logit_p_mean": 2.5, "logit_p_sd": 2.0, "logit_a_mean": -2.0, "logit_a_sd": 1.5,
         "nu_rate": 0.1, "log_gamma_sd": 0.5}
PARAMS = ["mu", "logit_p", "logit_a", "log_nu_minus_2", "log_gamma"]
NP = len(PARAMS)


# ----------------------------------------------------------------------------- model
def unpack(th, v: float) -> dict:
    """Named parameters; v is the fund's long-run daily variance (its actual variance)."""
    th = np.atleast_2d(np.asarray(th, dtype=float))
    with np.errstate(over="ignore"):
        p, a = expit(th[:, 1]), expit(th[:, 2])
        nu, g = 2 + np.exp(th[:, 3]), np.exp(th[:, 4])
    vv = np.full(len(th), float(v))
    return {"mu": th[:, 0], "v": vv, "p": p, "alpha": a * p, "beta": (1 - a) * p, "omega": vv * (1 - p), "nu": nu, "gamma": g}


def skew_t_std(nu, g):
    """Mean and standard deviation of the raw Fernández-Steel skew-t, used to rescale it to mean 0, variance 1."""
    with np.errstate(over="ignore", invalid="ignore"):
        m1 = 2 * np.sqrt(nu) * np.exp(gammaln((nu + 1) / 2) - gammaln(nu / 2)) / ((nu - 1) * np.sqrt(np.pi))
        M = m1 * (g - 1 / g)
        S = np.sqrt((nu / (nu - 2)) * (g ** 3 + g ** -3) / (g + 1 / g) - M ** 2)
    return M, S


def skew_t_cdf(x, nu, g):
    """CDF of the raw Fernández-Steel skew-t (used by the audit's tail check)."""
    from scipy.stats import t as student

    x = np.asarray(x, dtype=float)
    lo = 2 / (1 + g ** 2) * student.cdf(x * g, nu)
    hi = 1 / (1 + g ** 2) + 2 * g ** 2 / (1 + g ** 2) * (student.cdf(x / g, nu) - 0.5)
    return np.where(x < 0, lo, hi)


def log_prior(th) -> np.ndarray:
    th = np.atleast_2d(th)
    with np.errstate(invalid="ignore", over="ignore"):  # impossible values give nan here and are rejected
        nu = 2 + np.exp(th[:, 3])
        return (-th[:, 0] ** 2 / (2 * PRIOR["mu_sd"] ** 2)
                - (th[:, 1] - PRIOR["logit_p_mean"]) ** 2 / (2 * PRIOR["logit_p_sd"] ** 2)
                - (th[:, 2] - PRIOR["logit_a_mean"]) ** 2 / (2 * PRIOR["logit_a_sd"] ** 2)
                + np.log(nu) - PRIOR["nu_rate"] * nu + th[:, 3]  # Gamma(2, rate) on nu, times the Jacobian
                - th[:, 4] ** 2 / (2 * PRIOR["log_gamma_sd"] ** 2))


def cond_var(e: np.ndarray, q: dict, i: int) -> np.ndarray:
    """Conditional variances s_1..s_{n+1}^2 from shocks e, for parameter row i (s_1^2 = long-run variance)."""
    u = q["omega"][i] + q["alpha"][i] * e ** 2  # input for s_2^2 .. s_{n+1}^2
    rest = lfilter([1.0], [1.0, -q["beta"][i]], u, zi=[q["beta"][i] * q["v"][i]])[0]
    return np.concatenate([[q["v"][i]], rest])


def log_lik(th, r: np.ndarray) -> np.ndarray:
    """Shock likelihood (GARCH skew-t) plus the likelihood of the sample mean given mu."""
    r = np.asarray(r, dtype=float)
    n, rbar = len(r), r.mean()
    e = r - rbar
    q = unpack(th, e.var())
    M, S = skew_t_std(q["nu"], q["gamma"])
    out = np.empty(len(q["mu"]))
    for i in range(len(out)):
        if not np.isfinite(S[i]):
            out[i] = -np.inf
            continue
        h = cond_var(e, q, i)[:-1]
        x = M[i] + S[i] * e / np.sqrt(h)  # back on the raw skew-t scale
        g, nu = q["gamma"][i], q["nu"][i]
        w = np.where(x >= 0, x / g, x * g)
        shocks = (n * (math.log(2) - math.log(g + 1 / g) + gammaln((nu + 1) / 2) - gammaln(nu / 2)
                       - 0.5 * math.log(nu * math.pi) + math.log(S[i]))
                  - ((nu + 1) / 2) * np.log1p(w ** 2 / nu).sum() - 0.5 * np.log(h).sum())
        var_mean = h.sum() / n ** 2  # variance of the sample mean under this volatility path
        out[i] = shocks - 0.5 * (rbar - q["mu"][i]) ** 2 / var_mean - 0.5 * math.log(2 * math.pi * var_mean)
    return out


def make_energy(r: np.ndarray):
    r = np.asarray(r, dtype=float)

    def energy(th):
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            e = -(log_lik(th, r) + log_prior(th))
        return np.where(np.isfinite(e), e, np.inf)

    return energy


def derived(th, v: float) -> dict:
    q = unpack(th, v)
    return {"growth": np.expm1(TD * q["mu"]), "vol": np.sqrt(TD * q["v"]), "nu": q["nu"], "gamma": q["gamma"],
            "mean": q["mu"], "persistence": q["p"], "alpha": q["alpha"]}


def sample_skew_t(rng, nu, g, size):
    """Raw Fernández-Steel skew-t draws: |T| scaled by gamma on the right, by 1/gamma on the left."""
    a = np.abs(rng.standard_t(nu, size=size))
    pos = rng.random(size) < g ** 2 / (1 + g ** 2)
    return np.where(pos, g * a, -a / g)


def sample_z(rng, nu, g, size):
    """Skew-t shocks rescaled to mean 0 and variance 1."""
    M, S = skew_t_std(nu, g)
    return (sample_skew_t(rng, nu, g, size) - M) / S


def simulate_returns(th, n_days: int, rng, v: float) -> np.ndarray:
    """One series of daily log returns from a single parameter row (made-up data for the audit and tests)."""
    q = unpack(th, v)
    mu, om, al, be = q["mu"][0], q["omega"][0], q["alpha"][0], q["beta"][0]
    z = sample_z(rng, q["nu"][0], q["gamma"][0], n_days)
    h, out = v, np.empty(n_days)
    for t in range(n_days):
        e = math.sqrt(h) * z[t]
        out[t] = mu + e
        h = om + al * e * e + be * h
    return out


# ----------------------------------------------------------------------------- fitting
def fit_fund(r: np.ndarray, seed: int = 0, steps: int = 20_000, pilot: int = 4_000, burn: int = 4_000, m: int = 4) -> dict:
    """Pilot run to learn the proposal's shape, then the main chains with that proposal held fixed."""
    r = np.asarray(r, dtype=float)
    rng = np.random.default_rng(seed)
    n, s = len(r), r.std()
    energy = make_energy(r)
    base = np.array([r.mean(), math.log(0.95 / 0.05), math.log(0.1 / 0.9), math.log(4.0), 0.0])
    starts = base + rng.normal(0, [2 * s / math.sqrt(n), 0.3, 0.3, 0.3, 0.05], size=(m, NP))
    p = run_chains(energy, starts, pilot, gaussian_walk(np.array([s / math.sqrt(n), 0.1, 0.1, 0.1, 0.02])), rng)
    cov = np.cov(p["path"][pilot // 2:].reshape(-1, NP).T) * 2.38 ** 2 / NP + np.eye(NP) * 1e-14
    main = run_chains(energy, p["x"], steps, correlated_walk(cov), rng)
    draws = main["path"][burn + 1:]  # (steps - burn, m, NP)
    d = derived(draws.reshape(-1, NP), r.var())
    per_chain = {k: d[k].reshape(draws.shape[0], m) for k in ("growth", "persistence")}
    diag = {"rhat": max(r_hat(draws[..., j]) for j in range(NP)),
            "ess": min(ess(draws[..., j]) for j in range(NP)),
            "accept": float(main["accept"].mean())}
    return {"draws": draws, "theta": draws.reshape(-1, NP), "derived": d, "diag": diag, "per_chain": per_chain}


def last_var(theta: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Each row's variance for the first day after the data (where the predictions start)."""
    e = r - r.mean()
    q = unpack(theta, e.var())
    return np.array([cond_var(e, q, i)[-1] for i in range(len(theta))])


# ----------------------------------------------------------------------------- prediction
def predict(theta: np.ndarray, r: np.ndarray, amount: float, years: int, n_paths: int, seed: int, chunk: int = 2000) -> dict:
    """Simulated values: each path draws one parameter row, starts from its last-day volatility and runs the GARCH."""
    rng = np.random.default_rng(seed)
    n_days = years * TD
    sample_idx = np.arange(0, n_days + 1, 21)
    values = np.empty((n_paths, len(sample_idx)))
    mdd = np.empty(n_paths)
    pick = rng.integers(0, len(theta), n_paths)
    uniq, inv = np.unique(pick, return_inverse=True)
    r = np.asarray(r, dtype=float)
    h_start = last_var(theta[uniq], r)[inv]
    for s0 in range(0, n_paths, chunk):
        sl = slice(s0, min(s0 + chunk, n_paths))
        q = unpack(theta[pick[sl]], np.var(r))
        z = sample_z(rng, q["nu"][:, None], q["gamma"][:, None], (len(q["mu"]), n_days))
        h, logG, peak, worst = h_start[sl].copy(), np.zeros(len(q["mu"])), np.zeros(len(q["mu"])), np.zeros(len(q["mu"]))
        vals = [np.ones(len(q["mu"]))]
        for t in range(n_days):
            e = np.sqrt(h) * z[:, t]
            logG += q["mu"] + e
            h = q["omega"] + q["alpha"] * e * e + q["beta"] * h
            peak = np.maximum(peak, logG)
            worst = np.minimum(worst, logG - peak)
            if (t + 1) % 21 == 0:
                vals.append(np.exp(logG))
        values[sl] = amount * np.stack(vals, axis=1)
        mdd[sl] = np.expm1(worst)
    return {"values": values, "sample_idx": sample_idx, "end": values[:, -1], "mdd": mdd, "amount": amount,
            "vol_now": np.sqrt(TD * h_start)}


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
        preds[f] = predict(fit["theta"], r, amount, years, a.paths, seed=a.seed + 100 + i)
        fixed[f] = predict(np.median(fit["theta"], axis=0)[None, :], r, amount, years, a.paths, seed=a.seed + 200 + i)
        fits[f] = fit
        idx = R[f].dropna().index
        rows.append({"fund": f, "description": cfg["etfs"][f], "start": str(idx[0].date()), "end": str(idx[-1].date()),
                     "days": len(r), "sample_growth": math.expm1(TD * r.mean()), "sample_vol": r.std(ddof=1) * math.sqrt(TD),
                     **{f"growth_p{q}": np.percentile(d["growth"], q) for q in (5, 50, 95)}, "growth_sd": d["growth"].std(),
                     **{f"vol_now_p{q}": np.percentile(preds[f]["vol_now"], q) for q in (5, 50, 95)},
                     "nu_p50": np.median(d["nu"]), "gamma_p50": np.median(d["gamma"]),
                     "persistence_p50": np.median(d["persistence"]), "persistence_sd": d["persistence"].std(),
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
    by_v = list(S.sort_values("sample_vol", ascending=False).index)
    _hbar_interval(plt, by_v, cols, S.loc[by_v, "vol_now_p50"].to_numpy(), S.loc[by_v, "vol_now_p5"].to_numpy(),
                   S.loc[by_v, "vol_now_p95"].to_numpy(), S.loc[by_v, "sample_vol"].to_numpy(),
                   "Volatility today (bar, 90% range) vs the fund's long-run volatility (dot)", "Volatility a year",
                   out / "charts" / "volatility_today.png")
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
          "combinations of return, risk, tails and skew, each in proportion to how well it explains the actual daily returns. "
          "Each simulated future then uses one of those combinations, so the predictions carry that uncertainty.", "",
          "**Model:** a GARCH volatility model with skewed Student-t shocks. Today's volatility depends on recent days, so calm "
          "and stormy spells are kept; shocks can have fat tails (crashes) and falls can be bigger than rises. The average return "
          "is anchored to the fund's actual average, with its uncertainty set by the volatility; the long-run volatility is the "
          "fund's actual volatility. Predictions start from each fund's volatility today. Four Markov chains per fund; the proposal's shape is learned in a pilot run and then held fixed, so the "
          "main chains keep the Markov property. Details: [`mcsim/mh_etfs.py`](../mcsim/mh_etfs.py).", "",
          "**Contents:** [1. Bar diagrams](#1-bar-diagrams) · [2. Simulation prediction](#2-simulation-prediction) · "
          "[3. Model estimates](#3-model-estimates) · [Notes](#notes)", "",
          "## 1. Bar diagrams", "",
          "### 1a. Long-run growth a year", "",
          "Bar: most likely value. Whisker: 90% range. Dot: what the fund actually returned over the data window.", "",
          "![Growth ranges](charts/growth_ranges.png)", "",
          "### 1b. Volatility today vs long-run", "",
          "Bar beyond the dot: a stormier spell than usual, which the predictions start from and then fade at the fund's own pace.", "",
          "![Volatility today](charts/volatility_today.png)", "",
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
          "| Fund | Data | Growth a year: actual | Growth a year: model (90% range) | Chance true growth is below 0 | Volatility: long-run | Volatility today (90% range) | Calm/stormy persistence | Tails ν | Skew γ |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for f in by_g:
        s = S.loc[f]
        o.append(f"| {f} | {s['start']} to {s['end']} ({s['days'] / TD:.1f} y) | {pct(s['sample_growth'])} | **{pct(s['growth_p50'])}** "
                 f"({pct(s['growth_p5'])} to {pct(s['growth_p95'])}) | {pct(s['p_growth_below_0'], 0)} | {pct(s['sample_vol'])} | "
                 f"{pct(s['vol_now_p50'])} ({pct(s['vol_now_p5'])} to {pct(s['vol_now_p95'])}) | {s['persistence_p50']:.3f} | "
                 f"{s['nu_p50']:.1f} | {s['gamma_p50']:.2f} |")
    o += ["", "*Volatility today*: the model's estimate for the day after the data ends; above the long-run figure means a stormy spell. "
          "*Persistence*: how slowly a calm or stormy spell fades (0.99 = very slowly). "
          "*Tails ν*: below about 5 means crashes and spikes are far more common than a bell curve allows. "
          "*Skew γ*: below 1 means falls tend to be larger than rises.", "",
          "## Notes", "",
          "- Volatility follows a GARCH(1, 1); the average return is taken as constant (no momentum or mean reversion in returns).",
          "- The ranges describe uncertainty given this decade. They cannot include risks the decade never showed.",
          "- No taxes, inflation or currency effects beyond what is in the fund prices.", "",
          "**Files:** " + ", ".join(f"[`{p.name}`](charts/{p.name})" for p in sorted((out / 'charts').glob('*.png'))) + " · " +
          ", ".join(f"[`{p.name}`](tables/{p.name})" for p in sorted((out / 'tables').glob('*.csv'))), ""]
    (out / "RESULTS.md").write_text("\n".join(o))
    print("mh_etfs ok:", out, "-", len(funds), "funds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
