"""Key numbers as CSV files, for spreadsheets and for checking by hand (AI-assisted code)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .core import TD, contribution_metrics


def value_at_year(sim: dict, year: int) -> np.ndarray | None:
    """Simulated portfolio values on 1 January of a given year, or None if not sampled."""
    day = (year - sim["start_year"]) * TD
    hit = np.where(sim["sample_idx"] == day)[0]
    return sim["values"][:, hit[0]] if len(hit) else None


def write_tables(cfg: dict, results: dict, outdir: Path) -> list[str]:
    import pandas as pd

    outdir.mkdir(parents=True, exist_ok=True)
    rates = cfg["reserve"]["stress_rates"]
    pmt, n_pay = cfg["reserve"]["payment"], cfg["reserve"]["n_payments"]
    flex = cfg["reserve"].get("flexibility_amount", 0.0)
    end = cfg["case"]["end_year"]
    w0, w1 = tuple(cfg["case"].get("stress_window", (2031, 2032)))
    pcts = (5, 10, 25, 50, 75, 90, 95)
    values, funding, risk = [], [], []
    for name, res in results.items():
        sim = res["sim"]
        for year in sorted({w0, end}):
            v = value_at_year(sim, year)
            if v is not None:
                values.append({"scenario": name, "date": f"{year}-01-01", **{f"p{p}": round(float(np.percentile(v, p)), 2) for p in pcts},
                               "mean": round(float(v.mean()), 2)})
        cm = contribution_metrics(sim["v_final"], pmt, n_pay, rates, flex)
        for r, m in cm.items():
            funding.append({"scenario": name, "reserve_rate": r, "reserve_needed": round(m["reserve"], 2),
                            "chance_below_reserve": round(m["shortfall"], 4),
                            "funding_ratio_p10": round(m["ratio_pcts"][10], 4), "funding_ratio_p50": round(m["ratio_pcts"][50], 4),
                            **{f"contribution_p{p}": round(m["contrib_pcts"][p], 2) for p in (5, 10, 25, 50, 75, 90, 95)},
                            **{f"contribution_at_least_{int(c * 100)}pct_conf": round(v, 2) for c, v in m["lower_bounds"].items()}})
        dd = sim["dd_window"]
        reg = sim["regime"]
        tot = reg.sum(axis=1)[0]
        risk.append({"scenario": name, "window": f"{w0}-{w1}", "worst_fall_median": round(float(np.median(dd)), 4),
                     "chance_fall_worse_than_20pct": round(float((dd < -0.20).mean()), 4),
                     "chance_fall_worse_than_30pct": round(float((dd < -0.30).mean()), 4),
                     "max_drawdown_whole_period_median": round(float(np.median(sim["mdd"])), 4),
                     "bear_days_median_share": round(float(np.median(reg[:, 0]) / tot), 4),
                     "sideways_days_median_share": round(float(np.median(reg[:, 1]) / tot), 4),
                     "bull_days_median_share": round(float(np.median(reg[:, 2]) / tot), 4)})
    files = []
    for fname, rows in [("portfolio_values.csv", values), ("funding_and_contribution.csv", funding), ("risk.csv", risk)]:
        p = outdir / fname
        pd.DataFrame(rows).to_csv(p, index=False)
        files.append(p.relative_to(outdir.parent).as_posix())
    return files
