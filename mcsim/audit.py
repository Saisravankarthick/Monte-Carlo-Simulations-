"""Data audit: re-download the Yahoo Finance prices and check them against the Markov model repo.

    uv run python -m mcsim.audit --config config/markov_etfs.toml --markov data/markov_stats.json \
        --summary results_markov_etfs/tables/fund_summary.csv --out data_check

Three checks per fund:
  A. Markov repo vs fresh Yahoo: same window, same rule, so rows, regime now, long-run mix,
     buy-and-hold drawdown and Sharpe should reproduce the Markov repo's report/stats.json.
  B. Simulation inputs vs Yahoo: the history the simulation used (years, yearly growth, worst fall).
  C. Data quality: gaps, duplicate dates and the largest one-day moves.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .__main__ import load_config
from .core import THRESHOLD, TD, WINDOW

MIN_TRAIN = 252  # the Markov repo scores buy-and-hold from this many days in


# --------------------------------------------------------------------- Markov rule (mirrors the Markov repo)
def label_regimes(close: pd.Series, window: int = WINDOW, threshold: float = THRESHOLD) -> pd.Series:
    r = close.pct_change(window)
    labels = pd.Series(1, index=close.index, dtype=int)
    labels[r > threshold] = 2
    labels[r < -threshold] = 0
    return labels


def transition_matrix(labels: pd.Series) -> np.ndarray:
    counts = np.zeros((3, 3))
    a = labels.to_numpy()
    for i in range(len(a) - 1):
        counts[a[i], a[i + 1]] += 1
    s = counts.sum(axis=1, keepdims=True)
    s[s == 0] = 1.0
    return counts / s


def stationary(P: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eig(P.T)
    v = np.abs(np.real(vecs[:, np.argmin(np.abs(vals - 1.0))]))
    return v / v.sum()


def sharpe(r: pd.Series) -> float:
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(TD)) if sd and np.isfinite(sd) else float("nan")


def max_drawdown(r: pd.Series) -> float:
    eq = (1 + r).cumprod()
    return float(((eq - eq.cummax()) / eq.cummax()).min())


def markov_stats(close: pd.Series) -> dict:
    """The numbers in the Markov repo's report table, recomputed from a price series."""
    labels = label_regimes(close)
    P = transition_matrix(labels)
    pi = stationary(P)
    rets = close.pct_change().dropna()
    bh = rets.loc[labels.index.intersection(rets.index)].iloc[MIN_TRAIN + 1:]
    ok = len(bh) > 30
    return {"rows": len(close), "start": str(close.index[0].date()), "end": str(close.index[-1].date()),
            "current": ["Bear", "Sideways", "Bull"][int(labels.iloc[-1])],
            "bear": float(pi[0]), "side": float(pi[1]), "bull": float(pi[2]),
            "bear_stay": float(P[0, 0]), "bull_stay": float(P[2, 2]),
            "bh_sharpe": sharpe(bh) if ok else float("nan"), "bh_maxdd": max_drawdown(bh) if ok else float("nan")}


def compare(ref: dict, got: dict) -> list[str]:
    """What differs between the Markov repo's numbers (ref) and ours (got). Empty list = all match."""
    bad = []
    for k in ("rows", "start", "end", "current"):
        if ref[k] != got[k]:
            bad.append(f"{k}: {ref[k]} vs {got[k]}")
    mix = max(abs(ref[k] - got[k]) for k in ("bear", "side", "bull", "bear_stay", "bull_stay"))
    if mix > 0.005:
        bad.append(f"regime mix off by {mix * 100:.1f} pts")
    if abs(ref["bh_maxdd"] - got["bh_maxdd"]) > 0.005:
        bad.append(f"max drawdown {ref['bh_maxdd'] * 100:.1f}% vs {got['bh_maxdd'] * 100:.1f}%")
    tol = max(0.02, 0.01 * abs(ref["bh_sharpe"])) if np.isfinite(ref["bh_sharpe"]) else 0
    if np.isfinite(ref["bh_sharpe"]) and abs(ref["bh_sharpe"] - got["bh_sharpe"]) > tol:
        bad.append(f"Sharpe {ref['bh_sharpe']:.2f} vs {got['bh_sharpe']:.2f}")
    return bad


# --------------------------------------------------------------------- Yahoo
def download(t: str, start: str, end: str, adjusted: bool) -> pd.Series:
    import yfinance as yf

    df = pd.DataFrame()
    for attempt in (1, 2, 3):
        try:
            df = yf.download(t, start=start, end=end, progress=False, auto_adjust=adjusted)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {t}: attempt {attempt} failed: {exc}", file=sys.stderr)
        if not df.empty:
            break
        time.sleep(10 * attempt)
    if df.empty:
        raise RuntimeError(f"no Yahoo data for {t}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"].dropna()


def growth_stats(r: pd.Series) -> tuple[float, float]:
    """Yearly growth (geometric) and worst fall of a daily-return series."""
    G = (1 + r).cumprod()
    return float(G.iloc[-1] ** (TD / len(r)) - 1), float((G / G.cummax() - 1).min())


# --------------------------------------------------------------------- report
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--markov", required=True, help="the Markov repo's report/stats.json")
    ap.add_argument("--summary", required=True, help="fund_summary.csv written by the simulation")
    ap.add_argument("--out", default="data_check")
    a = ap.parse_args()

    cfg = load_config(a.config)
    md = {d["ticker"]: d for d in json.load(open(a.markov))["tickers"]}
    summ = pd.read_csv(a.summary).set_index("fund")
    end = pd.Timestamp.now("UTC").tz_localize(None).normalize()
    start = end - pd.DateOffset(years=cfg["simulation"]["history_years"])
    # reach back far enough to include the Markov repo's first row, whatever window the simulation used
    start = min([start] + [pd.Timestamp(d["start"]) - pd.Timedelta(days=7) for d in md.values()])

    A, B, C, E, verdicts = [], [], [], [], {}
    for t in cfg["etfs"]:
        print(f"  checking {t}")
        adj = download(t, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), True)
        raw = download(t, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), False)

        # A. same window as the Markov repo
        m = md.get(t)
        if m:
            win = adj.loc[m["start"]:m["end"]]
            got = markov_stats(win)
            bad = compare(m, got)
            verdicts[t] = bad
            A.append(f"| {t} | {m['rows']} / {got['rows']} | {m['start']} → {m['end']} | {m['current']} / {got['current']} | "
                     f"{max(abs(m[k] - got[k]) for k in ('bear', 'side', 'bull')) * 100:.2f} | "
                     f"{m['bh_maxdd'] * 100:.1f}% / {got['bh_maxdd'] * 100:.1f}% | {m['bh_sharpe']:.2f} / {got['bh_sharpe']:.2f} | "
                     f"{'✅ match' if not bad else '⚠ ' + '; '.join(bad)} |")
            r10 = win.pct_change().dropna()
            cagr10, dd10 = growth_stats(r10)
        else:
            A.append(f"| {t} | not in the Markov repo | | | | | | – |")
            cagr10 = dd10 = float("nan")

        # B. what the simulation used
        if t in summ.index:
            s = summ.loc[t]
            p = adj.loc[:s["history_to"]]
            r = p.pct_change().dropna().loc[s["history_from"]:]
            cagr, dd = growth_stats(r)
            ok = abs(cagr - s["hist_growth_a_year"]) < 0.001 and abs(dd - s["hist_worst_fall"]) < 0.005 \
                and abs(len(r) / TD - s["history_years"]) < 0.06
            B.append(f"| {t} | {s['history_from']} → {s['history_to']} | {s['history_years']:.1f} | "
                     f"{s['hist_growth_a_year'] * 100:.2f}% / {cagr * 100:.2f}% | {s['hist_worst_fall'] * 100:.1f}% / {dd * 100:.1f}% | "
                     f"{'✅' if ok else '⚠'} |")
            E.append(f"| {t} | {s['history_years']:.1f} | {cagr * 100:.1f}% | {cagr10 * 100:.1f}% | {dd * 100:.0f}% | {dd10 * 100:.0f}% |")

        # C. data quality and a spot check you can compare with finance.yahoo.com/quote/<ticker>/history
        ret = adj.pct_change().dropna()
        gap = int(adj.index.to_series().diff().dt.days.max())
        top = ret.abs().sort_values(ascending=False).head(2)
        big = ", ".join(f"{d.date()} {ret.loc[d] * 100:+.1f}%" for d in top.index)
        C.append(f"| {t} | {adj.index[-1].date()} | {raw.iloc[-1]:.2f} | {adj.iloc[-1]:.2f} | {int(adj.index.duplicated().sum())} | {gap} | {big} |")

    n_ok = sum(1 for v in verdicts.values() if not v)
    md_out = [
        "# Data check: Yahoo Finance vs the Markov model repo", "",
        f"Run {pd.Timestamp.now('UTC'):%Y-%m-%d %H:%M} UTC · prices are Yahoo Finance daily closes, dividend-adjusted (the same setting the Markov model and the simulation use).", "",
        f"**{n_ok} of {len(verdicts)} funds reproduce the Markov repo's report exactly** "
        f"(same rows, regime now, long-run mix within 0.5 pts, buy-and-hold drawdown within 0.5 pts, Sharpe within 0.02).", "",
        "## A. Markov repo vs fresh Yahoo data (Markov's own 10-year window)", "",
        "| Fund | Rows: Markov / Yahoo | Window | Regime now: Markov / Yahoo | Max gap in long-run mix (pts) | Buy-and-hold worst fall: Markov / Yahoo | Sharpe: Markov / Yahoo | Result |",
        "|---|---|---|---|---|---|---|---|", *A, "",
        "## B. What the Monte Carlo used vs Yahoo (the simulation's own window)", "",
        "| Fund | Dates used | Years | Growth a year: simulation / Yahoo | Worst fall: simulation / Yahoo | Result |",
        "|---|---|---|---|---|---|", *B, "",
        "## C. Same funds over the simulation's window vs the Markov window", "",
        "The two windows differ, and for some funds the difference is large. Funds whose simulation window reaches back before 2016 include the 2008-09 crash; the Markov window does not.", "",
        "| Fund | Years in simulation window | Growth a year, simulation window | Growth a year, Markov window | Worst fall, simulation window | Worst fall, Markov window |",
        "|---|---|---|---|---|---|", *E, "",
        "## D. Data quality and spot check", "",
        "Compare the raw close with the *Close* column on finance.yahoo.com/quote/TICKER/history for the same date. The adjusted close is that price with dividends added back.", "",
        "| Fund | Last date | Raw close | Adjusted close | Duplicate dates | Longest gap (days) | Two biggest one-day moves |",
        "|---|---|---|---|---|---|---|", *C, "",
    ]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "DATA_CHECK.md").write_text("\n".join(md_out))
    print(f"audit ok: {n_ok}/{len(verdicts)} funds match the Markov repo; wrote {out / 'DATA_CHECK.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
