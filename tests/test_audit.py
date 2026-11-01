"""The audit must reproduce the Markov repo's recipe and flag any difference."""

import numpy as np
import pandas as pd

from mcsim.audit import compare, label_regimes, markov_stats, stationary, transition_matrix


def _prices(seed=5, n=900):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-02", periods=n)
    return pd.Series(100 * np.cumprod(1 + rng.normal(0.0004, 0.012, n)), index=idx)


def test_markov_stats_are_consistent():
    s = markov_stats(_prices())
    assert s["rows"] == 900
    assert abs(s["bear"] + s["side"] + s["bull"] - 1) < 1e-9
    assert s["current"] in {"Bear", "Sideways", "Bull"}
    assert -1 < s["bh_maxdd"] < 0


def test_label_rule_is_20_day_plus_minus_2_percent():
    close = pd.Series(np.r_[np.full(25, 100.0), 103.0, 97.0], index=pd.bdate_range("2024-01-01", periods=27))
    lab = label_regimes(close)
    assert lab.iloc[-2] == 2 and lab.iloc[-1] == 0  # +3% over 20 days is Bull, -3% is Bear
    P = transition_matrix(lab)
    assert np.allclose(P.sum(axis=1)[P.sum(axis=1) > 0], 1)
    assert abs(stationary(P).sum() - 1) < 1e-9


def test_compare_flags_differences():
    s = markov_stats(_prices())
    assert compare(s, dict(s)) == []
    flipped = dict(s, current="Bull" if s["current"] != "Bull" else "Bear", rows=s["rows"] + 3, bh_maxdd=s["bh_maxdd"] - 0.05)
    msgs = " ".join(compare(s, flipped))
    assert "current" in msgs and "rows" in msgs and "max drawdown" in msgs
