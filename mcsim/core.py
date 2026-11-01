"""Core maths for comparing ETFs by Monte Carlo simulation (AI-assisted code; see README).

For each ETF (or mix of ETFs) the question is: if I invest an amount today, and
optionally add a fixed amount every month, what range of outcomes could I see over
the horizon, how often would I lose money, and how deep could the falls be?

  * block_bootstrap   resample blocks of real daily returns, keeping short-term clustering
  * simulate_asset    many possible futures for one return series, with optional monthly
                      contributions, plus worst fall, growth rate and regime days
  * summarise         turn simulated futures into the comparison numbers
"""

from __future__ import annotations

import numpy as np

TD = 252            # trading days per year
MONTH = 21          # trading days per month
WINDOW, THRESHOLD = 20, 0.02   # regime rule: 20-day return, +/-2%
PCTS = (5, 10, 25, 50, 75, 90, 95)


def block_bootstrap(R: np.ndarray, n_days: int, block: int, n_paths: int, rng, chunk: int = 1000):
    """Yield arrays of resampled daily returns built from blocks of real consecutive days.

    R is (T,) for one asset or (T, k) for several assets sampled on the same dates.
    Output is (m, n_days) or (m, n_days, k).
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


def fv_lump_and_monthly(amount: float, monthly: float, annual_growth: float, years: int) -> float:
    """Closed-form value for a steady growth rate: lump sum today plus a contribution every month
    (at the start of each month after the first), compounding per trading day. Used by the tests."""
    d = (1 + annual_growth) ** (1 / TD)
    n = years * TD
    total = amount * d ** n
    for k in range(1, (n - 1) // MONTH + 1):   # contribution days MONTH, 2*MONTH, ... strictly before day n
        total += monthly * d ** (n - k * MONTH)
    return total


def simulate_asset(r: np.ndarray, amount: float, monthly: float, years: int, n_paths: int, block: int, seed: int,
                   haircut: float = 0.0, sample_every: int = MONTH) -> dict:
    """Simulate futures for one daily return series r.

    amount   invested on day 0;  monthly  added at the start of every later month.
    haircut  points a year subtracted from the return (a stress case).
    """
    rng = np.random.default_rng(seed)
    r = np.asarray(r, dtype=float) - haircut / TD
    n = years * TD
    contrib_days = [0] + list(range(MONTH, n, MONTH))
    contrib = np.array([amount] + [monthly] * (len(contrib_days) - 1))
    invested = float(contrib.sum())
    sample_idx = np.arange(0, n + 1, sample_every)
    values = np.empty((n_paths, len(sample_idx)))
    end = np.empty(n_paths)
    growth = np.empty(n_paths)
    mdd = np.empty(n_paths)
    regime = np.zeros((n_paths, 3), dtype=int)
    done = 0
    for chunk in block_bootstrap(r, n, block, n_paths, rng):
        m = chunk.shape[0]
        sl = slice(done, done + m)
        G = np.concatenate([np.ones((m, 1)), np.cumprod(1 + chunk, axis=1)], axis=1)   # growth of $1 bought on day 0
        D = np.zeros((m, n + 1))
        D[:, contrib_days] = contrib[None, :] / G[:, contrib_days]                    # units bought on each contribution day
        V = G * np.cumsum(D, axis=1)                                                  # value = units held x price
        values[sl] = V[:, sample_idx]
        end[sl] = V[:, -1]
        growth[sl] = G[:, -1] ** (1 / years) - 1                                      # time-weighted growth a year
        mdd[sl] = (G / np.maximum.accumulate(G, axis=1) - 1).min(axis=1)              # worst fall of the price path
        r20 = G[:, WINDOW:] / G[:, :-WINDOW] - 1
        bear = (r20 < -THRESHOLD).sum(axis=1)
        bull = (r20 > THRESHOLD).sum(axis=1)
        regime[sl, 0], regime[sl, 2] = bear, bull
        regime[sl, 1] = r20.shape[1] - bear - bull
        done += m
    return {"values": values, "sample_idx": sample_idx, "end": end, "growth": growth, "mdd": mdd, "regime": regime,
            "invested": invested, "years": years}


def summarise(sim: dict) -> dict:
    """The comparison numbers for one simulated asset."""
    end, inv = sim["end"], sim["invested"]
    reg = sim["regime"]
    tot = reg.sum(axis=1)[0]
    return {
        "invested": inv,
        "end_pcts": {p: float(np.percentile(end, p)) for p in PCTS},
        "growth_median": float(np.median(sim["growth"])),
        "growth_p10": float(np.percentile(sim["growth"], 10)),
        "growth_p90": float(np.percentile(sim["growth"], 90)),
        "p_loss": float((end < inv).mean()),
        "p_double": float((end >= 2 * inv).mean()),
        "mdd_median": float(np.median(sim["mdd"])),
        "mdd_p5": float(np.percentile(sim["mdd"], 5)),
        "p_fall_20": float((sim["mdd"] < -0.20).mean()),
        "p_fall_30": float((sim["mdd"] < -0.30).mean()),
        "p_fall_40": float((sim["mdd"] < -0.40).mean()),
        "regime_share": (np.median(reg, axis=0) / tot).tolist(),
    }


def history_stats(r: np.ndarray) -> dict:
    """What the real history looked like: yearly mean and volatility, worst fall, current regime."""
    r = np.asarray(r, dtype=float)
    G = np.cumprod(1 + r)
    r20 = G[-1] / G[-1 - WINDOW] - 1 if len(G) > WINDOW else np.nan
    regime = "Bull" if r20 > THRESHOLD else "Bear" if r20 < -THRESHOLD else "Sideways"
    return {"mean": float(r.mean() * TD), "vol": float(r.std(ddof=1) * np.sqrt(TD)),
            "worst_fall": float((G / np.maximum.accumulate(G) - 1).min()), "cagr": float(G[-1] ** (TD / len(r)) - 1),
            "regime_now": regime, "r20_now": float(r20)}
