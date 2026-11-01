"""RESULTS.md: a readable comparison of ETFs with every chart embedded (AI-assisted code)."""

from __future__ import annotations

import datetime as dt

from .style import usd


def _img(charts: dict, cat: str, contains: str, alt: str) -> list[str]:
    hits = [p for p in charts.get(cat, []) if contains in p]
    return [f"![{alt}]({hits[0]})", ""] if hits else []


def prediction_points(cfg: dict) -> list[int]:
    years = cfg["investment"]["years"]
    return sorted({y for y in (1, 3, 5, years) if y <= years})


def predicted(sim: dict, year: int) -> dict:
    """5th / 25th / 50th / 75th / 95th percentile of value at a given year."""
    import numpy as np

    col = int(np.argmin(np.abs(sim["sample_idx"] - year * 252)))
    return dict(zip((5, 25, 50, 75, 95), np.percentile(sim["values"][:, col], [5, 25, 50, 75, 95])))


def render(cfg: dict, assets: dict, charts: dict, tables: list[str]) -> str:
    if cfg.get("report", {}).get("layout") == "two_sections":
        return render_two_sections(cfg, assets, charts, tables)
    inv_cfg, sim_cfg = cfg["investment"], cfg["simulation"]
    years = inv_cfg["years"]
    order = sorted(assets, key=lambda a: assets[a]["sums"]["history"]["end_pcts"][50], reverse=True)
    invested = assets[order[0]]["sums"]["history"]["invested"]
    hc = sim_cfg["haircut"] * 100
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    plan = f"{usd(inv_cfg['amount'])} today" + (f" plus {usd(inv_cfg['monthly'])} every month" if inv_cfg.get("monthly") else "")
    o = ["# ETF Monte Carlo research", "",
         f"Updated {now} · **{plan}**, over **{years} years** · {sim_cfg['paths']:,} simulated futures per fund · "
         f"blocks of {sim_cfg['block']} real trading days · seed {sim_cfg['seed']}", "",
         "> Research tool, not advice. Every future here is stitched together from each fund's own past, so it shows what "
         "the past implies, not what will happen.", "",
         "**Contents:** [At a glance](#at-a-glance) · [1. Outcomes](#1-outcomes) · [2. Risk and return](#2-risk-and-return) · "
         "[3. Simulated futures](#3-simulated-futures) · [4. Distributions](#4-distributions) · [5. Regimes](#5-regimes) · "
         "[6. Diversification](#6-diversification) · [7. The data used](#7-the-data-used) · [8. Limits](#8-limits) · [Files](#files)", "",
         "## At a glance", "",
         f"Ranked by median value after {years} years if history repeats. Total invested: {usd(invested)}.", "",
         "| # | Fund | What it is | Median value | 5th – 95th | Growth a year (median) | Chance of loss | Typical worst fall | "
         f"Fall worse than −30% | Median if −{hc:g} pts a year | Today |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, a in enumerate(order, 1):
        s, st = assets[a]["sums"]["history"], assets[a]["sums"]["stress"]
        o.append(f"| {i} | **{a}** | {assets[a]['label']} | **{usd(s['end_pcts'][50])}** | {usd(s['end_pcts'][5])} – {usd(s['end_pcts'][95])} | "
                 f"{s['growth_median'] * 100:.1f}% | {s['p_loss'] * 100:.0f}% | {s['mdd_median'] * 100:.0f}% | {s['p_fall_30'] * 100:.0f}% | "
                 f"{usd(st['end_pcts'][50])} | {assets[a]['hist']['regime_now']} |")
    o += ["", "*Typical worst fall* = the median, across futures, of the largest peak-to-trough fall. *Today* = the regime from the "
          "last 20 trading days (Bull above +2%, Bear below −2%).", ""]
    o += ["## 1. Outcomes", ""]
    o += _img(charts, "overview", "outcome_ranges", "Outcome ranges by fund")
    o += _img(charts, "overview", "history_vs_stress", "History vs stress")
    o += ["## 2. Risk and return", "", "Up and to the left is better: more growth for a smaller typical fall.", ""]
    o += _img(charts, "risk", "growth_vs_worst_fall", "Growth vs worst fall")
    o += _img(charts, "risk", "chance_of_loss", "Chance of loss")
    o += _img(charts, "risk", "chance_of_big_falls", "Chance of big falls")
    o += ["## 3. Simulated futures", ""]
    o += _img(charts, "paths", "simulated_futures", "Simulated futures")
    o += ["## 4. Distributions", ""]
    o += _img(charts, "dist", "outcome_distributions", "Outcome distributions")
    o += ["## 5. Regimes", ""]
    o += _img(charts, "regimes", "regime_mix", "Regime mix")
    o += ["## 6. Diversification", "",
          "Low or negative correlation means two funds tend not to fall on the same days, which is what makes combining them useful.", ""]
    o += _img(charts, "div", "correlation", "Correlation heatmap")
    o += ["## 7. The data used", "",
          "Each fund is simulated from its own history. Funds with short histories have seen fewer kinds of markets, so treat them with more caution.", "",
          "| Fund | History used | Years | Growth a year | Volatility | Worst fall |", "|---|---|---|---|---|---|"]
    for a in order:
        h, sp = assets[a]["hist"], assets[a]["span"]
        flag = " ⚠ short" if sp[2] < 8 else ""
        o.append(f"| {a} | {sp[0]} to {sp[1]} | {sp[2]:.1f}{flag} | {h['cagr'] * 100:.1f}% | {h['vol'] * 100:.1f}% | {h['worst_fall'] * 100:.0f}% |")
    o += ["", "## 8. Limits", "",
          "- The past is the only source of randomness. A decade dominated by one kind of market (for example falling rates, or a long US rally) shapes every simulated future.",
          "- Funds with different history lengths are compared side by side; the longer ones include crises the shorter ones never saw.",
          "- Blocks of 20 days keep short-term momentum and volatility clustering, but nothing longer than a block.",
          "- No taxes, fees beyond those already in the fund prices, currency effects beyond what is in the price, or inflation.",
          f"- The stress case simply subtracts {hc:g} points a year from every fund; it is a sensitivity check, not a forecast.", "",
          "## Files", "", "Charts are sorted into one folder per category; the CSV tables hold every number above.", ""]
    labels = {"overview": "1. Overview", "risk": "2. Risk and return", "paths": "3. Simulated futures",
              "dist": "4. Distributions", "regimes": "5. Regimes", "div": "6. Diversification"}
    for cat, files in charts.items():
        if files:
            o.append(f"- **{labels.get(cat, cat)}:** " + ", ".join(f"[`{f.split('/')[-1]}`]({f})" for f in files))
    o.append("- **Tables:** " + ", ".join(f"[`{f.split('/')[-1]}`]({f})" for f in tables))
    o.append("")
    return "\n".join(o)


def render_two_sections(cfg: dict, assets: dict, charts: dict, tables: list[str]) -> str:
    """Report in two parts: 1. Bar diagrams, 2. Simulation prediction."""
    inv_cfg, sim_cfg = cfg["investment"], cfg["simulation"]
    years = inv_cfg["years"]
    title = cfg.get("report", {}).get("title", "ETF Monte Carlo")
    order = sorted(assets, key=lambda a: assets[a]["sums"]["history"]["end_pcts"][50], reverse=True)
    invested = assets[order[0]]["sums"]["history"]["invested"]
    hc = sim_cfg["haircut"] * 100
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    plan = f"{usd(inv_cfg['amount'])} today" + (f" plus {usd(inv_cfg['monthly'])} every month" if inv_cfg.get("monthly") else "")
    short = [a for a in order if assets[a]["span"][2] < 8]
    hy = sim_cfg["history_years"]
    no_crash = int(min(assets[a]["span"][0] for a in order)[:4]) > 2009  # no fund's window reaches the 2008-09 crash
    o = [f"# {title}", "",
         f"Updated {now} · **{plan}** in each fund, over **{years} years** · {sim_cfg['paths']:,} simulated futures per fund · "
         f"blocks of {sim_cfg['block']} real trading days · seed {sim_cfg['seed']}", "",
         "> Research tool, not advice. Each fund's futures are stitched together from that fund's own past, so they show what "
         "the past implies, not what will happen.", ""]
    if short:
        o += [f"> ⚠ Short history (under 8 years): {', '.join(short)}. These have not been through a full crash cycle, "
              "so their predictions are less reliable.", ""]
    o += [f"> Window: every fund's last {hy} years of Yahoo Finance prices (dividend-adjusted), the same window as the Markov model, "
          "so the funds are compared over the same decade." +
          (" That decade does not include the 2008-09 crash, so falls and chances of loss are likely understated." if no_crash else ""), ""]
    o += ["**Contents:** [1. Bar diagrams](#1-bar-diagrams) · [2. Simulation prediction](#2-simulation-prediction) · "
          "[Notes](#notes)", "",
          "## 1. Bar diagrams", "",
          f"Funds are sorted by their median value after {years} years if history repeats. Total invested: {usd(invested)}.", ""]
    o += ["### 1a. Where the money could end up", ""] + _img(charts, "overview", "outcome_ranges", "Outcome ranges")
    o += ["### 1b. History repeats vs a tougher future", "",
          f"Blue: futures built from each fund's own past. Red: the same with {hc:g} points a year taken off.", ""]
    o += _img(charts, "overview", "history_vs_stress", "History vs stress")
    o += ["### 1c. Chance of losing money", ""] + _img(charts, "risk", "chance_of_loss", "Chance of loss")
    o += ["### 1d. How often big falls happen", "",
          "Chance of at least one peak-to-trough fall of each size during the period.", ""]
    o += _img(charts, "risk", "chance_of_big_falls", "Chance of big falls")
    o += ["### 1e. Bull, Sideways and Bear time (same regime rule as the Markov model)", ""]
    o += _img(charts, "regimes", "regime_mix", "Regime mix")
    pts = prediction_points(cfg)
    o += ["## 2. Simulation prediction", "",
          "### 2a. Predicted value, median (range in brackets = 5th to 95th percentile)", "",
          "| Fund | What it is | " + " | ".join(f"Year {y}" for y in pts) + " | Growth a year | Chance of loss | Today |",
          "|---|---|" + "---|" * len(pts) + "---|---|---|"]
    for a in order:
        sim, s = assets[a]["sims"]["history"], assets[a]["sums"]["history"]
        cells = []
        for y in pts:
            q = predicted(sim, y)
            cells.append(f"**{usd(q[50])}** ({usd(q[5])} – {usd(q[95])})")
        o.append(f"| **{a}** | {assets[a]['label']} | " + " | ".join(cells) +
                 f" | {s['growth_median'] * 100:.1f}% | {s['p_loss'] * 100:.0f}% | {assets[a]['hist']['regime_now']} |")
    o += ["", "*Today* = regime from the last 20 trading days (Bull above +2%, Bear below −2%).", "",
          "### 2b. Predicted range over time", ""] + _img(charts, "paths", "prediction_fans", "Prediction fans")
    o += ["### 2c. Sample simulated futures", ""] + _img(charts, "paths", "simulated_futures", "Simulated futures")
    o += ["### 2d. Distribution of final values", ""] + _img(charts, "dist", "outcome_distributions", "Outcome distributions")
    o += ["## Notes", "", "| Fund | History used | Years | Growth a year | Volatility | Worst fall |", "|---|---|---|---|---|---|"]
    for a in order:
        h, sp = assets[a]["hist"], assets[a]["span"]
        flag = " ⚠ short" if sp[2] < 8 else ""
        o.append(f"| {a} | {sp[0]} to {sp[1]} | {sp[2]:.1f}{flag} | {h['cagr'] * 100:.1f}% | {h['vol'] * 100:.1f}% | {h['worst_fall'] * 100:.0f}% |")
    o += ["", f"- Every fund uses its last {hy} years; funds younger than that (⚠) use all they have and have seen less of the market.",
          "- One decade is one sample. Strong years for a fund make its future look strong, and weak years the opposite.",
          "- No taxes, inflation or currency effects beyond what is in the fund prices.",
          f"- The tougher case simply subtracts {hc:g} points a year from every fund; it is a sensitivity check, not a forecast.", "",
          "**Files:** " + ", ".join(f"[`{f.split('/')[-1]}`]({f})" for fs in charts.values() for f in fs) + " · " +
          ", ".join(f"[`{f.split('/')[-1]}`]({f})" for f in tables), ""]
    return "\n".join(o)
