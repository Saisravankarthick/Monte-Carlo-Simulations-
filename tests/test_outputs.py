"""Smoke test: every chart, table and the report are produced and link to files that exist."""

import re

import numpy as np
import pandas as pd

from mcsim.__main__ import build_assets, load_config
from mcsim.data import correlation
from mcsim.plots import make_all
from mcsim.report import render
from mcsim.tables import write_tables


def test_all_outputs_are_written_and_linked(tmp_path):
    cfg = load_config("config/etf_research.toml")
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2012-01-02", periods=2500)
    mkt = rng.normal(0.0004, 0.011, len(idx))
    rets = {t: pd.Series(rng.uniform(0.2, 1.1) * mkt + rng.normal(0.0001, 0.005, len(idx)), index=idx) for t in cfg["etfs"]}
    rets["SHY"] = pd.Series(rng.normal(0.0001, 0.0005, len(idx)), index=idx)
    assets = build_assets(cfg, rets, n_paths=200)
    corr = correlation(rets)
    charts = make_all(cfg, assets, corr, tmp_path / "charts")
    tables = write_tables(assets, corr, tmp_path / "tables", cfg)
    md = render(cfg, assets, charts, tables)
    assert {p.name for p in (tmp_path / "charts").iterdir()} == {"1_overview", "2_risk_return", "3_paths", "4_distributions",
                                                                "5_regimes", "6_diversification"}
    links = re.findall(r"\]\(((?:charts|tables)/[^)]+)\)", md)
    assert links and all((tmp_path / l).exists() for l in links)
    s = pd.read_csv(tmp_path / "tables" / "fund_summary.csv")
    assert len(s) == len(cfg["etfs"]) + len(cfg["mixes"])
    assert "liability" not in md.lower() and "reserve" not in md.lower()


def test_two_section_layout(tmp_path):
    cfg = load_config("config/markov_etfs.toml")
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2015-01-02", periods=1500)
    rets = {t: pd.Series(rng.normal(0.0003, 0.01, len(idx)), index=idx) for t in cfg["etfs"]}
    assets = build_assets(cfg, rets, n_paths=200)
    corr = correlation(rets)
    charts = make_all(cfg, assets, corr, tmp_path / "charts")
    tables = write_tables(assets, corr, tmp_path / "tables", cfg)
    md = render(cfg, assets, charts, tables)
    assert {p.name for p in (tmp_path / "charts").iterdir()} == {"1_bar_diagrams", "2_simulation_prediction"}
    assert "## 1. Bar diagrams" in md and "## 2. Simulation prediction" in md
    assert "prediction_fans" in md
    links = re.findall(r"\]\(((?:charts|tables)/[^)]+)\)", md)
    assert links and all((tmp_path / l).exists() for l in links)
    pred = pd.read_csv(tmp_path / "tables" / "prediction_by_year.csv")
    assert set(pred["year"]) == {1, 3, 5, 10} and (pred["p5"] <= pred["p50"]).all() and (pred["p50"] <= pred["p95"]).all()
