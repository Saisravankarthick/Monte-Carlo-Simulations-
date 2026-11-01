"""Load daily total-return prices from Yahoo Finance (dividend-adjusted)."""

from __future__ import annotations

import sys
import time

import pandas as pd


def load_prices(tickers: list[str], years: int) -> dict[str, pd.Series]:
    """Adjusted close per ticker, each over as much of the last `years` as the fund has existed."""
    import yfinance as yf

    end = pd.Timestamp.now("UTC").tz_localize(None).normalize()
    start = end - pd.DateOffset(years=years)
    out = {}
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
            print(f"  ! {t}: no data, skipped", file=sys.stderr)
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        out[t] = df["Close"].dropna()
    return out


def returns_of(prices: dict[str, pd.Series]) -> dict[str, pd.Series]:
    return {t: p.pct_change().dropna() for t, p in prices.items()}


def mix_returns(rets: dict[str, pd.Series], weights: dict[str, float]) -> pd.Series:
    """Daily return of a fixed-weight mix, on the dates every member has data (rebalanced daily)."""
    w = pd.Series(weights, dtype=float)
    if abs(w.sum() - 1) > 1e-9:
        raise ValueError(f"mix weights must add to 1 (got {w.sum():.4f})")
    df = pd.DataFrame({t: rets[t] for t in w.index}).dropna()
    return (df * w).sum(axis=1)


def correlation(rets: dict[str, pd.Series]) -> pd.DataFrame:
    """Correlation of daily returns, each pair over the dates both funds have data."""
    return pd.DataFrame(rets).corr(min_periods=250)
