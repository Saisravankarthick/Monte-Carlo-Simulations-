"""RESULTS.md: a readable comparison of ETFs with every chart embedded (AI-assisted code)."""

from __future__ import annotations

import datetime as dt

from .style import usd


def _img(charts: dict, cat: str, contains: str, alt: str) -> list[str]:
    hits = [p for p in charts.get(cat, []) if contains in p]
    return [f"![{alt}]({hits[0]})", ""] if hits else []


def render(cfg: dict, assets: dict, charts: dict, tables: list[str]) -> str:
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
