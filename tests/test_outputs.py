"""Smoke test: every chart, table and the report are produced and link to files that exist."""

import re

import numpy as np
import pandas as pd

from mcsim.__main__ import load_config, run
from mcsim.data import history_summary
from mcsim.plots import make_all
from mcsim.report import render
from mcsim.tables import write_tables


def test_all_outputs_are_written_and_linked(tmp_path):
    cfg = load_config("config/example_placeholder.toml")
    rng = np.random.default_rng(7)
    T = 2000
    mkt = rng.normal(0.0004, 0.011, T)
    S = pd.DataFrame({"growth": 0.9 * mkt + rng.normal(0, 0.004, T), "matching": rng.normal(0.00015, 0.004, T),
                      "flex": rng.normal(0.00012, 0.0004, T)}, index=pd.bdate_range("2015-01-02", periods=T))
    results = run(cfg, S, n_paths=300)
    hist = history_summary(S)
    charts = make_all(cfg, hist, results, tmp_path / "charts")
    tables = write_tables(cfg, results, tmp_path / "tables")
    md = render(cfg, hist, results, 300, "test data", charts, tables)
    # one folder per category, each with at least one chart
    assert {p.name for p in (tmp_path / "charts").iterdir()} == {"1_inputs", "2_paths", "3_outcomes", "4_funding", "5_risk"}
    assert sum(len(v) for v in charts.values()) >= 12
    # every image and file link in the report points to a file that exists
    links = re.findall(r"\]\(((?:charts|tables)/[^)]+)\)", md)
    assert links and all((tmp_path / l).exists() for l in links)
    # the funding table has one row per scenario and reserve rate
    f = pd.read_csv(tmp_path / "tables" / "funding_and_contribution.csv")
    assert len(f) == len(cfg["scenarios"]) * len(cfg["reserve"]["stress_rates"])
