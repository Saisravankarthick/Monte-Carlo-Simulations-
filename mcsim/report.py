"""RESULTS.md: a readable report with every chart embedded, organised by section (AI-assisted code)."""

from __future__ import annotations

import datetime as dt

import numpy as np

from .core import SLEEVES, contribution_metrics, pv_annuity_due
from .plots import central_rate
from .style import usd
from .tables import value_at_year


def _img(charts: dict, cat: str, contains: str, alt: str) -> list[str]:
    hits = [p for p in charts.get(cat, []) if contains in p]
    return [f"![{alt}]({hits[0]})", ""] if hits else []


def render(cfg: dict, hist, results: dict, n_paths: int, history_span: str, charts: dict, tables: list[str]) -> str:
    case = cfg["case"]
    end = case["end_year"]
    rates = cfg["reserve"]["stress_rates"]
    flex = cfg["reserve"].get("flexibility_amount", 0.0)
    pmt, n_pay = cfg["reserve"]["payment"], cfg["reserve"]["n_payments"]
    w0, w1 = tuple(case.get("stress_window", (2031, 2032)))
    r0 = central_rate(rates)
    names = list(results)
    cms = {n: contribution_metrics(results[n]["sim"]["v_final"], pmt, n_pay, rates, flex) for n in names}
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    o = ["# Cash-flow Monte Carlo: results", "",
         f"Updated {now} · **{n_paths:,} simulated futures** · seed {cfg['simulation']['seed']} · "
         f"blocks of {cfg['simulation']['block']} real trading days resampled from {history_span}", ""]
    if cfg.get("placeholder"):
        o += ["> ⚠️ **Placeholder allocation.** The sleeve weights and glide path in this run are illustrative inputs that show how the model "
              "works. They are not a recommendation; the strategy's allocation is the team's own decision.", ""]
    o += ["**Contents:** [At a glance](#at-a-glance) · [1. Inputs](#1-inputs) · [2. Simulated futures](#2-simulated-futures) · "
          f"[3. Where it ends up](#3-where-the-portfolio-ends-up) · [4. Funding and contribution](#4-funding-reliability-and-the-facility-contribution) · "
          "[5. Risk](#5-risk) · [6. Limits](#6-limits) · [Files](#files)", ""]

    # ------------------------------------------------------------------ at a glance
    o += ["## At a glance", "", "| Measure | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]

    def row(label, f):
        o.append(f"| {label} | " + " | ".join(f(n) for n in names) + " |")

    row(f"Median value on 1 Jan {end}", lambda n: f"**{usd(np.median(results[n]['sim']['v_final']))}**")
    row("5th – 95th percentile", lambda n: f"{usd(np.percentile(results[n]['sim']['v_final'], 5))} – {usd(np.percentile(results[n]['sim']['v_final'], 95))}")
    for r in rates:
        row(f"Chance of falling short of the reserve (earning {r * 100:g}%)", lambda n, r=r: f"{cms[n][r]['shortfall'] * 100:.1f}%")
    row(f"Median facility contribution (reserve at {r0 * 100:g}%)", lambda n: usd(cms[n][r0]["contrib_pcts"][50]))
    row(f"Contribution with 90% confidence ≥ (reserve at {r0 * 100:g}%)", lambda n: f"**{usd(cms[n][r0]['lower_bounds'][0.9])}**")
    row(f"Chance of a fall worse than −20% in {w0}–{w1}", lambda n: f"{(results[n]['sim']['dd_window'] < -0.20).mean() * 100:.1f}%")
    o.append("")

    # ------------------------------------------------------------------ 1 inputs
    o += ["## 1. Inputs", "", "| Item | Value |", "|---|---|"]
    for y, a in cfg["contributions"].items():
        o.append(f"| Contribution on 1 Jan {y} | {usd(a)} |")
    o += [f"| Valuation date | 1 Jan {end} |", f"| Operating payments | {n_pay} × {usd(pmt)}, at the start of each year (annuity-due) |",
          f"| Flexibility amount held back | {usd(flex)} |", "", "| Sleeve | Holdings (weights inside the sleeve) |", "|---|---|"]
    for s in SLEEVES:
        o.append(f"| {s.capitalize()} | " + ", ".join(f"{t} {w * 100:.0f}%" for t, w in cfg["sleeves"][s].items()) + " |")
    o.append("")
    o += _img(charts, "inputs", "glide_path", "Glide path")
    o += _img(charts, "inputs", "sleeve_history", "Sampled history by sleeve")
    o += ["| Sleeve | Average return a year | Volatility a year | Worst fall |", "|---|---|---|---|"]
    for s in SLEEVES:
        h = hist.loc[s]
        o.append(f"| {s.capitalize()} | {h['mean'] * 100:.1f}% | {h['vol'] * 100:.1f}% | {h['worst_fall'] * 100:.0f}% |")
    o.append("")

    # ------------------------------------------------------------------ 2 paths
    o += ["## 2. Simulated futures", "",
          "Each line is one possible future for the portfolio, coloured by where it ends (red = low, green = high). "
          "The step in early 2028 is the second contribution.", ""]
    for n in names:
        o += _img(charts, "paths", f"paths_{n}", f"Simulated futures, {n}")
    o += _img(charts, "paths", "fan_all", "Percentile fan, all scenarios")

    # ------------------------------------------------------------------ 3 outcomes
    o += ["## 3. Where the portfolio ends up", "",
          f"Bars are coloured against the reserve needed if it earns {r0 * 100:g}% ({usd(pv_annuity_due(pmt, n_pay, r0))}): "
          "red below it, amber up to 10% above it, green more than 10% above.", ""]
    for n in names:
        o += _img(charts, "outcomes", f"_{n}", f"Value on the valuation date, {n}")
    o += ["| Scenario | Date | 5th | 25th | Median | 75th | 95th |", "|---|---|---|---|---|---|---|"]
    for n in names:
        for y in sorted({w0, end}):
            v = value_at_year(results[n]["sim"], y)
            if v is not None:
                p = np.percentile(v, [5, 25, 50, 75, 95])
                o.append(f"| {n} | 1 Jan {y} | " + " | ".join(usd(x) for x in p) + " |")
    o.append("")

    # ------------------------------------------------------------------ 4 funding
    o += ["## 4. Funding reliability and the facility contribution", "",
          "Reserve = present value of the payments at the assumed reserve return (closed form). "
          "Contribution = portfolio value − reserve − flexibility amount.", "",
          "| Reserve earns | Reserve needed |", "|---|---|"]
    for r in rates:
        o.append(f"| {r * 100:g}% | {usd(pv_annuity_due(pmt, n_pay, r))} |")
    o += ["", f"For scale: the contributions add up to {usd(sum(cfg['contributions'].values()))} even if they earn nothing.", ""]
    o += _img(charts, "funding", "shortfall", "Chance of a shortfall")
    o += _img(charts, "funding", "confidence", "Contribution with confidence levels")
    o += _img(charts, "funding", "ranges", "Contribution ranges")
    o += ["| Scenario | Reserve earns | Funding ratio 10th / median | Chance below reserve | Contribution 10th / median / 90th | ≥ with 80% / 90% / 95% confidence |",
          "|---|---|---|---|---|---|"]
    for n in names:
        for r in rates:
            m = cms[n][r]
            lb = m["lower_bounds"]
            o.append(f"| {n} | {r * 100:g}% | {m['ratio_pcts'][10]:.2f}× / {m['ratio_pcts'][50]:.2f}× | {m['shortfall'] * 100:.2f}% | "
                     f"{usd(m['contrib_pcts'][10])} / {usd(m['contrib_pcts'][50])} / {usd(m['contrib_pcts'][90])} | "
                     f"{usd(lb[0.8])} / {usd(lb[0.9])} / {usd(lb[0.95])} |")
    o.append("")

    # ------------------------------------------------------------------ 5 risk
    o += ["## 5. Risk", "", f"### Sequence risk: the largest fall during {w0}–{w1}", ""]
    o += _img(charts, "risk", "stress_window", "Worst fall in the stress window")
    o += ["| Scenario | Median worst fall in the window | Worse than −20% | Worse than −30% | Median worst fall, whole period |", "|---|---|---|---|---|"]
    for n in names:
        s = results[n]["sim"]
        dd = s["dd_window"]
        o.append(f"| {n} | {np.median(dd) * 100:.0f}% | {(dd < -0.20).mean() * 100:.1f}% | {(dd < -0.30).mean() * 100:.1f}% | {np.median(s['mdd']) * 100:.0f}% |")
    o += ["", "### Regime days of the growth sleeve", ""]
    o += _img(charts, "risk", "regime_days", "Regime mix")
    o += ["| Scenario | Bear days (5th – median – 95th) | Sideways days | Bull days |", "|---|---|---|---|"]
    for n in names:
        reg = results[n]["sim"]["regime"]
        o.append(f"| {n} | " + " | ".join(" – ".join(f"{x:,.0f}" for x in np.percentile(reg[:, j], [5, 50, 95])) for j in range(3)) + " |")
    o.append("")

    # ------------------------------------------------------------------ limits + files
    o += ["## 6. Limits", "",
          "- The sampled history is the only source of randomness. It is limited and spans particular market conditions, so a history-based scenario can flatter or penalise a sleeve.",
          "- Block resampling keeps co-movement and short-term clustering but nothing longer than one block.",
          "- The reserve return is a fixed assumption. Yields available when the reserve is bought are not simulated.",
          "- No taxes, trading costs or inflation. The payments are fixed in nominal terms.",
          "- Results are ranges under stated assumptions, not predictions.", "",
          "## Files", "", "Charts are sorted into one folder per category; the CSV tables hold every number shown above.", ""]
    labels = {"inputs": "1. Inputs", "paths": "2. Simulated futures", "outcomes": "3. Outcomes", "funding": "4. Funding", "risk": "5. Risk"}
    for cat, files in charts.items():
        if files:
            o.append(f"- **{labels.get(cat, cat)}:** " + ", ".join(f"[`{f.split('/')[-1]}`]({f})" for f in files))
    o.append("- **Tables:** " + ", ".join(f"[`{f.split('/')[-1]}`]({f})" for f in tables))
    o.append("")
    return "\n".join(o)
