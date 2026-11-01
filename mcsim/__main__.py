"""Command line: compare ETFs by Monte Carlo simulation (AI-assisted code).

    uv run python -m mcsim --config config/etf_research.toml --out results
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tomllib
from pathlib import Path

import pandas as pd

from .core import history_stats, simulate_asset, summarise
from .data import correlation, load_prices, mix_returns, returns_of
from .plots import make_all
from .report import render
from .tables import write_tables


def load_config(path: str) -> dict:
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    cfg.setdefault("mixes", {})
    cfg["investment"].setdefault("monthly", 0)
    return cfg


def build_assets(cfg: dict, rets: dict[str, pd.Series], n_paths: int | None = None) -> dict:
    """Simulate every fund and mix under both scenarios."""
    inv, sim_cfg = cfg["investment"], cfg["simulation"]
    n = n_paths or sim_cfg["paths"]
    series = {t: (cfg["etfs"][t], rets[t]) for t in cfg["etfs"] if t in rets}
    for name, w in cfg["mixes"].items():
        if all(t in rets for t in w):
            series[name] = ("Mix: " + ", ".join(f"{t} {v * 100:.0f}%" for t, v in w.items()), mix_returns(rets, w))
    assets = {}
    for name, (label, r) in series.items():
        sims = {sc: simulate_asset(r.to_numpy(), inv["amount"], inv["monthly"], inv["years"], n, sim_cfg["block"], sim_cfg["seed"],
                                   haircut=h)
                for sc, h in (("history", 0.0), ("stress", sim_cfg["haircut"]))}
        assets[name] = {"label": label, "hist": history_stats(r.to_numpy()), "sims": sims,
                        "sums": {sc: summarise(s) for sc, s in sims.items()},
                        "span": (str(r.index[0].date()), str(r.index[-1].date()), len(r) / 252)}
    return assets


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None, help="output folder (default: [report] out in the config, else results)")
    ap.add_argument("--paths", type=int, default=None, help="override the number of simulated futures")
    a = ap.parse_args()
    cfg = load_config(a.config)
    if a.paths:
        cfg["simulation"]["paths"] = a.paths
    tickers = sorted(set(cfg["etfs"]) | {t for w in cfg["mixes"].values() for t in w})
    rets = returns_of(load_prices(tickers, cfg["simulation"]["history_years"]))
    assets = build_assets(cfg, rets)
    corr = correlation({t: rets[t] for t in cfg["etfs"] if t in rets})
    out = Path(a.out or cfg.get("report", {}).get("out", "results"))
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    charts = make_all(cfg, assets, corr, out / "charts")
    tables = write_tables(assets, corr, out / "tables", cfg)
    (out / "RESULTS.md").write_text(render(cfg, assets, charts, tables))
    print("mcsim ok:", out, "-", len(assets), "funds/mixes,", cfg["simulation"]["paths"], "paths each")
    return 0


if __name__ == "__main__":
    sys.exit(main())
