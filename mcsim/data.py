"""Load daily total-return data (Yahoo Finance, dividend-adjusted) and build sleeve returns."""

from __future__ import annotations

import sys
import time

import numpy as np
import pandas as pd

from .core import SLEEVES


def load_returns(tickers: list[str], years: int) -> pd.DataFrame:
    """Daily simple returns for all tickers, on the dates every ticker has a price."""
    import yfinance as yf

    end = pd.Timestamp.now("UTC").tz_localize(None).normalize()
    start = end - pd.DateOffset(years=years)
    closes = {}
    for t in tickers:
        df = pd.DataFrame()
        for attempt in (1, 2, 3):
            try:
                df = yf.download(t, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"),
                                 progress=False, auto_adjust=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {t}: attempt {attempt} failed: {exc}", file=sys.stderr)
            if not df.empty:
                break
            time.sleep(10 * attempt)
        if df.empty:
            raise RuntimeError(f"no data for {t} from Yahoo Finance")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        closes[t] = df["Close"].dropna()
    px = pd.DataFrame(closes).dropna()
    return px.pct_change().dropna()


def sleeve_returns(R: pd.DataFrame, sleeves: dict[str, dict[str, float]]) -> pd.DataFrame:
    """Weighted daily return of each sleeve (weights inside a sleeve are held constant)."""
    out = {}
    for name in SLEEVES:
        cfg = sleeves[name]
        w = pd.Series(cfg, dtype=float)
        if abs(w.sum() - 1) > 1e-9:
            raise ValueError(f"weights inside sleeve '{name}' must add to 1 (got {w.sum():.4f})")
        out[name] = (R[w.index] * w).sum(axis=1)
    return pd.DataFrame(out)


def history_summary(S: pd.DataFrame) -> pd.DataFrame:
    """Annualised mean, volatility and worst fall of each sleeve over the sampled history."""
    rows = []
    for name in SLEEVES:
        r = S[name].to_numpy()
        eq = np.cumprod(1 + r)
        rows.append({"sleeve": name, "mean": r.mean() * 252, "vol": r.std(ddof=1) * np.sqrt(252),
                     "worst_fall": float((eq / np.maximum.accumulate(eq) - 1).min())})
    return pd.DataFrame(rows).set_index("sleeve")
