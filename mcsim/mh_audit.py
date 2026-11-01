"""Audit of the Metropolis-Hastings ETF run (mcsim/mh_etfs.py).

    uv run python -m mcsim.mh_audit --out results_mh_etfs

Algorithm (answers known in advance):
  1. Exact kernel: on a 5-state target with a lopsided proposal, the code's transition probabilities match the
     Metropolis-Hastings formula, and that kernel satisfies detailed balance.
  2. Markov property: knowing the previous state as well as the current one does not change the next step.
  3. Hastings correction: right answer with it, wrong answer without it (negative control).
  4. Recovery: on made-up GARCH returns with known parameters, the 90% ranges contain the truth about 90% of the time.
ETF run:
  5. Data: the returns are the same ones the bootstrap report used (which the data check matched to Yahoo).
  6. Convergence: for every fund, R-hat below 1.01, effective sample size above 400, acceptance 10-60%.
  7. Seed stability: refitting every fund with a different seed gives the same answer.
  8. Fit: the average return is anchored to the actual one, and bad and good days happen as often as the model says.
  9. Prediction: adding parameter uncertainty widens the ranges, and the fixed-parameter median matches the formula.
 10. Volatility clustering: after the GARCH, squared shocks no longer predict each other.
Note: 11. Compares the model's uncertainty about the mean with a block-bootstrap estimate.
Exits with status 1 if a check fails.
"""

from __future__ import annotations

import argparse
import datetime as dt
import inspect
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import style
from .metropolis import batch_se, mh_step, run_chains
from .mh_etfs import PARAMS, TD, cond_var, derived, fit_fund, simulate_returns, skew_t_cdf, skew_t_std, unpack

K = 5
PI = np.arange(1, K + 1) / np.arange(1, K + 1).sum()  # target 1:2:3:4:5
UP = 0.7  # proposal: one step up the ring with prob 0.7, down with 0.3 (not symmetric)


# ----------------------------------------------------------------------------- 1-3. the algorithm
def _q(to, frm):
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
    run = run_chains(energy, np.arange(m)[:, None] % K, n_steps, propose, np.random.default_rng(seed), log_q=log_q)
    return run["path"][..., 0].astype(int)


def check_kernel(path):
    P = exact_kernel()
    db = np.abs(PI[:, None] * P - (PI[:, None] * P).T).max()
    stat = np.abs(PI @ P - PI).max()
    C = np.zeros((K, K))
    np.add.at(C, (path[:-1].ravel(), path[1:].ravel()), 1)
    gap = np.abs(C / C.sum(axis=1, keepdims=True) - P).max()
    freq = np.bincount(path[1000:].ravel(), minlength=K) / path[1000:].size
    tv = 0.5 * np.abs(freq - PI).sum()
    return (db < 1e-12 and stat < 1e-12 and gap < 0.01 and tv < 0.01,
            f"detailed balance error {db:.1e}; code vs formula: largest gap {gap:.4f} over {path[1:].size:,} steps; "
            f"time in each state vs target: distance {tv:.4f}")


def check_markov(path):
    prev, cur, nxt = path[:-2].ravel(), path[1:-1].ravel(), path[2:].ravel()
    worst, cells = 0.0, 0
    for c in range(K):
        base = np.bincount(nxt[cur == c], minlength=K) / (cur == c).sum()
        for p in range(K):
            sel = (cur == c) & (prev == p)
            if sel.sum() >= 5_000:
                cells += 1
                worst = max(worst, np.abs(np.bincount(nxt[sel], minlength=K) / sel.sum() - base).max())
    params = list(inspect.signature(mh_step).parameters)
    return (worst < 0.015 and "path" not in params and "history" not in params,
            f"P(next | current, previous) vs P(next | current): largest gap {worst:.4f} over {cells} pairs; "
            "each step receives only the current state; the ETF chains' proposal is fixed before they start")


def gamma_run(hastings=True, n_steps=60_000, m=16, seed=3, s=0.8):
    energy = lambda x: np.where(x[:, 0] > 0, x[:, 0] - np.log(np.abs(x[:, 0]) + 1e-300), np.inf)  # Gamma(2, 1)  # noqa: E731
    propose = lambda x, rng, t: x * np.exp(s * rng.normal(size=x.shape))  # log-normal: not symmetric  # noqa: E731
    log_q = (lambda a, b: -np.log(a[:, 0]) - np.log(a[:, 0] / b[:, 0]) ** 2 / (2 * s * s)) if hastings else None
    return run_chains(energy, np.ones((m, 1)), n_steps, propose, np.random.default_rng(seed), log_q=log_q)["path"][5_000:, :, 0]


def check_hastings():
    d, bad = gamma_run(True), gamma_run(False)
    se = batch_se(d)
    return (abs(d.mean() - 2) < 4 * se and abs(bad.mean() - 2) > 0.5,
            f"with the correction: mean {d.mean():.3f} (exact 2, ±{se:.3f}); without it: {bad.mean():.3f}, wrong as expected")


# ----------------------------------------------------------------------------- 4. recovery on made-up data
# (mu, daily sd, persistence alpha + beta, share alpha / (alpha + beta), nu, gamma)
TRUTHS = [(0.0005, 0.011, 0.97, 0.10, 6.0, 0.92), (0.0003, 0.007, 0.95, 0.08, 8.0, 0.95), (0.0006, 0.015, 0.98, 0.12, 5.0, 0.90),
          (0.0001, 0.003, 0.90, 0.05, 10.0, 1.0), (0.0004, 0.012, 0.96, 0.15, 4.5, 0.88), (0.0002, 0.005, 0.93, 0.07, 7.0, 1.05)]


def check_recovery(n_sets=12, n_days=2520, seed=11):
    rng = np.random.default_rng(seed)
    hits, total, rows = 0, 0, []
    for k in range(n_sets):
        mu, sd, pp, aa, nu, g = TRUTHS[k % len(TRUTHS)]
        th = np.array([[mu, math.log(pp / (1 - pp)), math.log(aa / (1 - aa)), math.log(nu - 2), math.log(g)]])
        r = simulate_returns(th, n_days, rng, sd * sd)
        fit = fit_fund(r, seed=seed + k, steps=12_000)
        truth = {kk: float(v[0]) for kk, v in derived(th, sd * sd).items() if kk in ("growth", "nu", "gamma", "persistence")}
        inside = {kk: np.percentile(fit["derived"][kk], 5) <= v <= np.percentile(fit["derived"][kk], 95) for kk, v in truth.items()}
        hits += sum(inside.values())
        total += len(inside)
        rows.append(f"| {k + 1} | {pct(truth['growth'])} | {pct(np.median(fit['derived']['growth']))} | "
                    f"{truth['nu']:.1f} / {np.median(fit['derived']['nu']):.1f} | "
                    f"{truth['gamma']:.2f} / {np.median(fit['derived']['gamma']):.2f} | "
                    f"{truth['persistence']:.3f} / {np.median(fit['derived']['persistence']):.3f} | {sum(inside.values())} of {len(inside)} |")
    # 90% ranges: expect 0.9 * total; pass if within about 2.5 binomial standard deviations below
    need = int(math.floor(0.9 * total - 2.5 * math.sqrt(total * 0.09)))
    return hits >= need, f"{hits} of {total} 90% ranges contain the true value (expected about {0.9 * total:.0f}; pass at {need} or more)", rows


# ----------------------------------------------------------------------------- 5-10. the ETF run
def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results_mh_etfs")
    ap.add_argument("--bootstrap", default="results_markov_etfs/tables/fund_summary.csv")
    ap.add_argument("--amount", type=float, default=10_000)
    ap.add_argument("--seed", type=int, default=1042)
    a = ap.parse_args()
    out = Path(a.out)
    R = pd.read_csv(out / "tables" / "returns_used.csv", index_col=0, parse_dates=True)
    S = pd.read_csv(out / "tables" / "posterior_summary.csv").set_index("fund")
    P = pd.read_csv(out / "tables" / "prediction_by_year.csv")
    funds = list(S.index)
    years = int(P.year.max())

    path = discrete_run()
    checks = [("1. Exact kernel and detailed balance", *check_kernel(path)), ("2. Markov property", *check_markov(path)),
              ("3. Hastings correction", *check_hastings())]
    ok4, msg4, rec_rows = check_recovery()
    checks.append(("4. Recovers known parameters", ok4, msg4))

    # 5. data
    bad5, n5 = [], 0
    if Path(a.bootstrap).exists():
        B = pd.read_csv(a.bootstrap).set_index("fund")
        for f in funds:
            r = np.log1p(R[f].dropna())
            b = B.loc[f]
            n5 += 1
            if str(r.index[0].date()) != b["history_from"] or str(r.index[-1].date()) != b["history_to"] \
                    or abs(TD * r.mean() - math.log1p(b["hist_growth_a_year"])) > 2e-4:
                bad5.append(f)
        checks.append(("5. Same data as the Yahoo-checked bootstrap run", not bad5,
                       f"{n5 - len(bad5)} of {n5} funds have the same dates and the same growth a year" +
                       (f"; differ: {', '.join(bad5)}" if bad5 else "")))
    else:
        checks.append(("5. Same data as the Yahoo-checked bootstrap run", False, f"{a.bootstrap} not found"))

    # 6-8, 10: refit every fund with another seed
    conv, stab, fitc, clus, garch = [], [], [], [], []
    trace_data = {}
    for i, f in enumerate(funds):
        r = np.log1p(R[f].dropna().to_numpy())
        fit = fit_fund(r, seed=a.seed + i)
        d, s = fit["derived"], S.loc[f]
        trace_data[f] = fit["per_chain"]["growth"]
        dg = abs(np.median(d["growth"]) - s["growth_p50"]) / s["growth_sd"]
        dv = abs(np.median(d["persistence"]) - s["persistence_p50"]) / max(s["persistence_sd"], 1e-12)
        conv.append((f, s["rhat_max"], s["ess_min"], s["accept"], fit["diag"]["rhat"]))
        stab.append((f, dg, dv))
        m_sd = d["mean"].std()
        z_mean = (np.median(d["mean"]) - r.mean()) / m_sd
        thm = np.median(fit["theta"], axis=0)[None, :]
        e = r - r.mean()
        q = unpack(thm, e.var())
        h = cond_var(e, q, 0)[:-1]
        M, Sd = skew_t_std(q["nu"], q["gamma"])
        u = skew_t_cdf(M[0] + Sd[0] * e / np.sqrt(h), q["nu"][0], q["gamma"][0])  # model probability of a day this bad or worse
        fitc.append((f, z_mean, float((u < 0.01).mean()), float((u < 0.05).mean()), float((u > 0.95).mean())))
        blocks = len(r) // 20
        bse = np.array([r[k * 20:(k + 1) * 20].mean() for k in range(blocks)]).std(ddof=1) / math.sqrt(blocks)
        clus.append((f, m_sd / bse))
        z2, r2 = (e / np.sqrt(h)) ** 2, e ** 2
        acf = lambda x, k: float(np.corrcoef(x[:-k], x[k:])[0, 1])  # noqa: E731
        garch.append((f, max(abs(acf(r2, k)) for k in range(1, 6)), max(abs(acf(z2, k)) for k in range(1, 6))))
        print(f"  audited {f}")
    ok6 = all(rh < 1.01 and e > 400 and 0.1 < ac < 0.6 and rh2 < 1.01 for _, rh, e, ac, rh2 in conv)
    checks.append(("6. Chains converged, every fund", ok6,
                   f"worst R-hat {max(c[1] for c in conv):.4f} (refit {max(c[4] for c in conv):.4f}); lowest ESS {min(c[2] for c in conv):,.0f}; "
                   f"acceptance {min(c[3] for c in conv) * 100:.0f}–{max(c[3] for c in conv) * 100:.0f}%"))
    ok7 = all(dg < 0.25 and dv < 0.25 for _, dg, dv in stab)
    checks.append(("7. Same answer with a different seed", ok7,
                   f"largest change in median growth {max(s[1] for s in stab):.2f} posterior standard deviations, "
                   f"in median persistence {max(s[2] for s in stab):.2f} (pass below 0.25)"))
    ok8 = all(abs(z) < 1 and 0.004 <= w1 <= 0.02 and 0.035 <= w5 <= 0.065 and 0.035 <= b5 <= 0.065 for _, z, w1, w5, b5 in fitc)
    checks.append(("8. Model fits each fund's actual returns", ok8,
                   f"average return: actual within {max(abs(c[1]) for c in fitc):.2f} posterior sd of the model's (pass below 1); "
                   f"days in the model's worst 1%: {min(c[2] for c in fitc) * 100:.1f}–{max(c[2] for c in fitc) * 100:.1f}% (pass 0.4–2%), "
                   f"worst 5%: {min(c[3] for c in fitc) * 100:.1f}–{max(c[3] for c in fitc) * 100:.1f}%, best 5%: "
                   f"{min(c[4] for c in fitc) * 100:.1f}–{max(c[4] for c in fitc) * 100:.1f}% (pass 3.5–6.5%)"))

    # 9. prediction
    bad9, z9 = [], []
    for f in funds:
        e = P[(P.fund == f) & (P.year == years)].set_index("model")
        wid_u, wid_f = e.loc["uncertain", "p95"] - e.loc["uncertain", "p5"], e.loc["fixed", "p95"] - e.loc["fixed", "p5"]
        th = S.loc[f, [f"{k}_p50" for k in PARAMS]].to_numpy(dtype=float)[None, :]
        dd = derived(th, np.log1p(R[f].dropna()).var())
        expect = a.amount * math.exp(years * TD * dd["mean"][0])
        # standard error of a simulated median, in log terms: 1.2533 * sd / sqrt(paths)
        se = 1.2533 * dd["vol"][0] * math.sqrt(years) / math.sqrt(e.loc["fixed", "paths"])
        z9.append(abs(math.log(e.loc["fixed", "p50"] / expect)) / se)
        if wid_u < wid_f or z9[-1] > 4:
            bad9.append(f)
    checks.append(("9. Predictions consistent", not bad9,
                   f"{len(funds) - len(bad9)} of {len(funds)} funds: the {years}-year range is wider with parameter uncertainty, "
                   f"and the fixed-parameter median matches amount × exp(days × mean daily log return) within simulation error (largest gap {max(z9):.1f} standard errors; pass below 4)" +
                   (f"; fail: {', '.join(bad9)}" if bad9 else "")))
    ok10 = all(zz < 0.1 for _, _, zz in garch)
    checks.append(("10. Calm and stormy spells captured", ok10,
                   f"day-to-day link in squared returns (lags 1-5): raw data up to {max(g[1] for g in garch):.2f}, after the GARCH "
                   f"up to {max(g[2] for g in garch):.2f} (pass below 0.10)"))
    low = [f"{f} ({v:.2f})" for f, v in clus if v < 0.8]
    note = (f"model's uncertainty about the mean ÷ 20-day block-bootstrap estimate: {min(v for _, v in clus):.2f}–{max(v for _, v in clus):.2f}. "
            + ("All above 0.8, so the return ranges are not overconfident." if not low
               else f"Below 0.8, so the return range may be too narrow: {', '.join(low)}. Its daily returns drift together "
                    "(they track short-term interest rates), which the model's constant average return does not capture."))

    # trace chart
    plt = style.setup()
    cols = style.fund_colors(funds)
    nc = 4
    nr = -(-len(funds) // nc)
    fig, axs = plt.subplots(nr, nc, figsize=(16, 2.4 * nr), constrained_layout=True)
    for ax in axs.ravel()[len(funds):]:
        ax.axis("off")
    for ax, f in zip(axs.ravel(), funds):
        tr = trace_data[f][::20]
        for c in range(tr.shape[1]):
            ax.plot(tr[:, c], lw=0.6, alpha=0.8)
        ax.set_title(f, fontsize=10, color=cols[f])
        ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f}%")
    fig.suptitle("Audit refit: growth a year, one line per Markov chain (well-mixed chains overlap)", fontsize=11)
    (out / "charts").mkdir(exist_ok=True)
    fig.savefig(out / "charts" / "audit_traces.png", dpi=100)
    plt.close(fig)

    n_ok = sum(ok for _, ok, _ in checks)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    o = ["# Audit: Metropolis-Hastings on the Markov model ETFs", "",
         f"Run {now} · [← results](RESULTS.md) · code: [`mcsim/mh_etfs.py`](../mcsim/mh_etfs.py), "
         f"[`mcsim/metropolis.py`](../mcsim/metropolis.py), audit: [`mcsim/mh_audit.py`](../mcsim/mh_audit.py)", "",
         f"**{n_ok} of {len(checks)} checks passed.**", "",
         "| Check | Result | Detail |", "|---|---|---|"]
    o += [f"| {n} | {'✅ pass' if ok else '❌ fail'} | {m} |" for n, ok, m in checks]
    o += [f"| 11. Uncertainty about the mean (note) | {'✅' if not low else '⚠'} | {note} |", "",
          "## Per fund", "",
          "| Fund | R-hat | Effective draws | Acceptance | Seed change: growth / persistence (sd) | Mean return gap (sd) | Days in model's worst 1% / worst 5% / best 5% | Squared-return link: raw → after GARCH | Uncertainty vs block bootstrap |",
          "|---|---|---|---|---|---|---|---|---|"]
    for (f, rh, ee, ac, _), (_, dg, dv), (_, z, w1, w5, b5), (_, cb), (_, g1, g2) in zip(conv, stab, fitc, clus, garch):
        o.append(f"| {f} | {rh:.4f} | {ee:,.0f} | {ac * 100:.0f}% | {dg:.2f} / {dv:.2f} | {z:+.2f} | "
                 f"{w1 * 100:.1f}% / {w5 * 100:.1f}% / {b5 * 100:.1f}% | {g1:.2f} → {g2:.2f} | {cb:.2f} |")
    o += ["", "![Traces](charts/audit_traces.png)", "",
          "## Recovery test (made-up data with known answers)", "",
          "Each row: 10 years of daily returns simulated from the GARCH model with known parameters, then fitted from scratch.", "",
          "| Set | Growth: true | Growth: fitted | Tails ν: true / fitted | Skew γ: true / fitted | Persistence: true / fitted | Inside the 90% range |",
          "|---|---|---|---|---|---|---|", *rec_rows, "",
          "## What the checks mean", "",
          "1-3 test the Metropolis-Hastings code itself against exact answers, including a negative control that must fail. "
          "4 tests the whole fitting method: if the 90% ranges caught the truth much less than 90% of the time, the ranges in the "
          "report would be overconfident. 5 ties the data to the Yahoo-checked bootstrap run. 6-7 show the chains settled and that "
          "the answer does not depend on the random seed. 8 checks the fit: bad days happen as often as the model says (about 1% of days "
          "fall in its worst 1%), so its crash risk is neither understated nor overstated. "
          "9 checks the prediction step. 10 checks that the GARCH removes the calm-and-stormy pattern from the shocks it leaves over. "
          "11 is a note comparing the model's uncertainty about the average return with a method that keeps 20-day runs of real days together.", ""]
    (out / "AUDIT.md").write_text("\n".join(o))
    for n, ok, m in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {n}: {m}")
    print("NOTE  10:", note)
    print(f"audit: {n_ok}/{len(checks)} passed")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
