"""Core maths for the cash-flow Monte Carlo (AI-assisted code; see README for the disclosure).

Question it answers: starting from the case-study contributions, how much could the
portfolio be worth on 1 January of the valuation year, and how does that compare with
the reserve needed to pay ten annual payments? Everything is a function of explicit
inputs so each number can be reproduced by hand.

Pieces
  * pv_annuity_due     present value of n payments made at the START of each year
  * block_bootstrap    resample blocks of real daily returns (keeps co-movement and
                       short-term clustering)
  * simulate           daily path of a three-sleeve portfolio with dated contributions
                       and an annual rebalance to a glide path
  * contribution_metrics  turn the final value into funding ratio, shortfall probability
                       and a range for the facility contribution
"""

from __future__ import annotations

import numpy as np

TD = 252  # trading days per year
SLEEVES = ("growth", "matching", "flex")
WINDOW, THRESHOLD = 20, 0.02  # regime rule: 20-day return, +/-2%


# ------------------------------------------------------------------ closed-form maths
def pv_annuity_due(pmt: float, n: int, r: float) -> float:
    """PV, on the date of the first payment, of n payments at the start of each year."""
    if r == 0:
        return pmt * n
    return pmt * (1 - (1 + r) ** -n) / r * (1 + r)


def fv_contributions(contribs: dict[int, float], growth: float, end_year: int) -> float:
    """Value on 1 Jan of end_year of contributions made on 1 Jan of the given years."""
    return sum(a * (1 + growth) ** (end_year - y) for y, a in contribs.items())


# ------------------------------------------------------------------ resampling
def block_bootstrap(R: np.ndarray, n_days: int, block: int, n_paths: int, rng, chunk: int = 1000):
    """Yield (m, n_days, k) arrays of resampled daily returns built from blocks of real days.

    All columns of R are sampled on the same dates, so their correlation is kept.
    """
    T = len(R)
    if T < block + 1:
        raise ValueError("not enough history for this block length")
    n_blocks = -(-n_days // block)
    for s in range(0, n_paths, chunk):
        m = min(chunk, n_paths - s)
        starts = rng.integers(0, T - block + 1, size=(m, n_blocks))
        idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(m, -1)[:, :n_days]
        yield R[idx]


def adjust_returns(S: np.ndarray, expected: dict[str, float] | None = None, haircuts: dict[str, float] | None = None) -> np.ndarray:
    """Return a copy of sleeve daily returns (T x 3) under a scenario.

    expected: replace each sleeve's historical average with the stated annual arithmetic
              return (the shape of the history is kept, only its centre moves).
    haircuts: subtract a number of percentage points a year from a sleeve.
    """
    A = S.copy()
    for j, name in enumerate(SLEEVES):
        if expected and name in expected:
            A[:, j] = A[:, j] - A[:, j].mean() + expected[name] / TD
        if haircuts and name in haircuts:
            A[:, j] = A[:, j] - haircuts[name] / TD
    return A


# ------------------------------------------------------------------ the simulation
def simulate(S: np.ndarray, contribs: dict[int, float], glide: dict[int, list[float]], start_year: int, end_year: int,
             n_paths: int, block: int, seed: int, sample_every: int = 21, window_years: tuple[int, int] | None = None) -> dict:
    """Simulate the accumulation phase from 1 Jan start_year to 1 Jan end_year.

    On each 1 January: add that year's contribution, then rebalance to that year's glide
    weights (growth, matching, flex). Between rebalances the sleeves drift.
    window_years: (first, last) calendar years of the stress window, for example (2031, 2032).
    """
    n_years = end_year - start_year
    n_days = n_years * TD
    rng = np.random.default_rng(seed)
    contrib_day = {(y - start_year) * TD: a for y, a in contribs.items()}
    weights = {(y - start_year) * TD: np.asarray(w, dtype=float) for y, w in glide.items()}
    for y in range(start_year, end_year):
        if y not in glide:
            raise ValueError(f"glide path is missing the year {y}")
        if abs(sum(glide[y]) - 1) > 1e-9 or min(glide[y]) < 0:
            raise ValueError(f"glide weights for {y} must be non-negative and add to 1")
    w0 = (window_years[0] - start_year) * TD if window_years else None
    w1 = (window_years[1] + 1 - start_year) * TD if window_years else None
    sample_idx = np.arange(0, n_days + 1, sample_every)
    sample_set = {int(i): j for j, i in enumerate(sample_idx)}

    values = np.empty((n_paths, len(sample_idx)))
    v_final = np.empty(n_paths)
    mdd_all = np.empty(n_paths)
    dd_window = np.zeros(n_paths)
    regime = np.zeros((n_paths, 3), dtype=int)
    done = 0
    for chunk in block_bootstrap(S, n_days, block, n_paths, rng):
        m = chunk.shape[0]
        sl = slice(done, done + m)
        hold = np.zeros((m, 3))
        idx = np.ones(m)
        peak_all = np.ones(m)
        mdd = np.zeros(m)
        peak_w = np.ones(m)
        ddw = np.zeros(m)
        g = np.ones((m, n_days + 1))
        for d in range(n_days):
            if d in contrib_day or d in weights:
                total = hold.sum(axis=1) + contrib_day.get(d, 0.0)
                hold = total[:, None] * weights[d][None, :]
            if d in sample_set:
                values[sl, sample_set[d]] = hold.sum(axis=1)
            prev = hold.sum(axis=1)
            hold = hold * (1.0 + chunk[:, d, :])
            idx = idx * (hold.sum(axis=1) / prev)
            peak_all = np.maximum(peak_all, idx)
            mdd = np.minimum(mdd, idx / peak_all - 1)
            if w0 is not None and w0 <= d < w1:
                if d == w0:
                    peak_w = idx.copy()
                peak_w = np.maximum(peak_w, idx)
                ddw = np.minimum(ddw, idx / peak_w - 1)
            g[:, d + 1] = g[:, d] * (1.0 + chunk[:, d, 0])
        v_final[sl] = hold.sum(axis=1)
        values[sl, sample_set[n_days]] = v_final[sl]
        mdd_all[sl] = mdd
        dd_window[sl] = ddw
        r20 = g[:, WINDOW:] / g[:, :-WINDOW] - 1
        bear = (r20 < -THRESHOLD).sum(axis=1)
        bull = (r20 > THRESHOLD).sum(axis=1)
        regime[sl, 0], regime[sl, 2] = bear, bull
        regime[sl, 1] = r20.shape[1] - bear - bull
        done += m
    return {"values": values, "sample_idx": sample_idx, "v_final": v_final, "mdd": mdd_all, "dd_window": dd_window,
            "regime": regime, "n_days": n_days, "start_year": start_year, "end_year": end_year}


# ------------------------------------------------------------------ funding metrics
def contribution_metrics(v_final: np.ndarray, pmt: float, n_pay: int, rates, flex_amount: float = 0.0,
                         confidences=(0.80, 0.90, 0.95)) -> dict:
    """For each assumed reserve return: reserve needed, funding ratio, shortfall chance, contribution range.

    contribution = portfolio value - reserve - flexibility amount (what is left for the facility)
    """
    out = {}
    for r in rates:
        R = pv_annuity_due(pmt, n_pay, r)
        ratio = v_final / R
        contrib = v_final - R - flex_amount
        out[r] = {
            "reserve": R,
            "ratio_pcts": {p: float(np.percentile(ratio, p)) for p in (5, 10, 50, 90)},
            "shortfall": float((v_final < R).mean()),
            "contrib_pcts": {p: float(np.percentile(contrib, p)) for p in (5, 10, 25, 50, 75, 90, 95)},
            "lower_bounds": {c: float(np.percentile(contrib, (1 - c) * 100)) for c in confidences},
        }
    return out


def pct(a, ps=(5, 25, 50, 75, 95)) -> dict:
    return {p: float(np.percentile(a, p)) for p in ps}
