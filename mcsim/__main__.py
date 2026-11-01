"""Command line: run the cash-flow Monte Carlo from a TOML config (AI-assisted code).

    uv run python -m mcsim --config config/example_placeholder.toml --out results
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from .core import SLEEVES, adjust_returns, simulate
from .data import history_summary, load_returns, sleeve_returns
from .plots import make_all
from .report import render
from .tables import write_tables


def load_config(path: str) -> dict:
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    cfg["contributions"] = {int(k): float(v) for k, v in cfg["contributions"].items()}
    cfg["glide"] = {int(k): [float(x) for x in v] for k, v in cfg["glide"].items()}
    cfg.setdefault("scenarios", {"history": {}})
    return cfg


def run(cfg: dict, S, n_paths: int | None = None) -> dict:
    sim_cfg = cfg["simulation"]
    n = n_paths or sim_cfg["paths"]
    results = {}
    for name, sc in cfg["scenarios"].items():
        A = adjust_returns(S.to_numpy(), expected=sc.get("returns"), haircuts=sc.get("haircuts"))
        sim = simulate(A, cfg["contributions"], cfg["glide"], cfg["case"]["start_year"], cfg["case"]["end_year"],
                       n, sim_cfg["block"], sim_cfg["seed"], window_years=tuple(cfg["case"].get("stress_window", (2031, 2032))))
        results[name] = {"sim": sim}
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--paths", type=int, default=None, help="override the number of simulated futures")
    a = ap.parse_args()
    cfg = load_config(a.config)
    tickers = sorted({t for s in SLEEVES for t in cfg["sleeves"][s]})
    R = load_returns(tickers, cfg["simulation"]["history_years"])
    S = sleeve_returns(R, cfg["sleeves"])
    span = f"{R.index[0].date()} to {R.index[-1].date()} ({len(R):,} trading days)"
    results = run(cfg, S, a.paths)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    n = a.paths or cfg["simulation"]["paths"]
    hist = history_summary(S)
    charts = make_all(cfg, hist, results, out / "charts")
    tables = write_tables(cfg, results, out / "tables")
    (out / "RESULTS.md").write_text(render(cfg, hist, results, n, span, charts, tables))
    print("mcsim ok:", tickers, n, "paths")
    return 0


if __name__ == "__main__":
    sys.exit(main())
