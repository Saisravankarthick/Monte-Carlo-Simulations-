"""Markdown report and charts from simulation results (AI-assisted code)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np

from .core import SLEEVES, TD, contribution_metrics, pct

NAMES = ["Bear", "Sideways", "Bull"]


def usd(x: float) -> str:
    return f"${x:,.0f}" if x >= 0 else f"−${-x:,.0f}"


def render(cfg: dict, hist, results: dict, n_paths: int, history_span: str) -> str:
    case = cfg["case"]
    start, end = case["start_year"], case["end_year"]
    rates = cfg["reserve"]["stress_rates"]
    flex = cfg["reserve"].get("flexibility_amount", 0.0)
    pmt, n_pay = cfg["reserve"]["payment"], cfg["reserve"]["n_payments"]
    win = tuple(cfg["case"].get("stress_window", (2031, 2032)))
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    o = [f"# Cash-flow Monte Carlo: results", "",
         f"Updated {now} · {n_paths:,} simulated futures · seed {cfg['simulation']['seed']} · "
         f"blocks of {cfg['simulation']['block']} real days resampled from {history_span}", ""]
    if cfg.get("placeholder"):
        o += ["> **PLACEHOLDER ALLOCATION.** The sleeve weights and glide path in this run are illustrative inputs used to show how the model works. "
              "They are not a recommendation. The strategy's allocation is the team's own decision.", ""]
    o += ["## Inputs", "", "| Item | Value |", "|---|---|"]
    for y, a in cfg["contributions"].items():
        o.append(f"| Contribution on 1 Jan {y} | {usd(a)} |")
    o += [f"| Valuation date | 1 Jan {end} |", f"| Operating payments | {n_pay} × {usd(pmt)} at the start of each year (annuity-due) |",
          f"| Flexibility amount held back from the contribution | {usd(flex)} |", ""]
    o += ["**Sleeves**", "", "| Sleeve | Holdings (weights inside the sleeve) |", "|---|---|"]
    for s in SLEEVES:
        o.append(f"| {s} | " + ", ".join(f"{t} {w * 100:.0f}%" for t, w in cfg["sleeves"][s].items()) + " |")
    o += ["", "**Glide path** (rebalanced to these weights on 1 January of each year)", "",
          "| Year | Growth | Matching | Flex |", "|---|---|---|---|"]
    for y, w in cfg["glide"].items():
        o.append(f"| {y} | {w[0] * 100:.0f}% | {w[1] * 100:.0f}% | {w[2] * 100:.0f}% |")
    o += ["", "**What the sampled history looked like** (annualised, before any scenario adjustment)", "",
          "| Sleeve | Average return | Volatility | Worst fall |", "|---|---|---|---|"]
    for s in SLEEVES:
        h = hist.loc[s]
        o.append(f"| {s} | {h['mean'] * 100:.1f}% | {h['vol'] * 100:.1f}% | {h['worst_fall'] * 100:.0f}% |")
    o += ["", "## Reserve needed on 1 Jan " + str(end) + " (closed form, no simulation)", "",
          "| Reserve earns | Reserve needed for the payments |", "|---|---|"]
    for r in rates:
        from .core import pv_annuity_due
        o.append(f"| {r * 100:g}% | {usd(pv_annuity_due(pmt, n_pay, r))} |")
    zero = sum(a for a in cfg["contributions"].values())
    o += ["", f"For scale: the contributions add up to {usd(zero)} even if they earn nothing.", ""]

    names = list(results)
    for name in names:
        sim = results[name]["sim"]
        sc = cfg["scenarios"][name]
        v = sim["v_final"]
        o += [f"## Scenario: {name}", ""]
        desc = []
        if sc.get("returns"):
            desc.append("expected returns set to " + ", ".join(f"{k} {x * 100:g}%" for k, x in sc["returns"].items()))
        else:
            desc.append("historical average returns kept")
        if sc.get("haircuts"):
            desc.append("haircut of " + ", ".join(f"{k} −{x * 100:g} points a year" for k, x in sc["haircuts"].items()))
        o += ["; ".join(desc).capitalize() + ".", "",
              f"### Portfolio value", "",
              "| Percentile | 1 Jan " + str(win[0]) + " | 1 Jan " + str(end) + " |", "|---|---|---|"]
        idx_w0 = (win[0] - sim["start_year"]) * TD
        col = int(np.where(sim["sample_idx"] == idx_w0)[0][0]) if idx_w0 in set(sim["sample_idx"]) else None
        pv_w = pct(sim["values"][:, col]) if col is not None else None
        pv_e = pct(v)
        for p in (5, 25, 50, 75, 95):
            o.append(f"| {p}th{' (median)' if p == 50 else ''} | {usd(pv_w[p]) if pv_w else '–'} | {usd(pv_e[p])} |")
        cm = contribution_metrics(v, pmt, n_pay, rates, flex)
        o += ["", "### Funding reliability and the facility contribution", "",
              "Contribution = portfolio value − reserve − flexibility amount.", "",
              "| If the reserve earns | Reserve | Funding ratio: 10th pct / median | Chance value < reserve | Contribution: 10th / median / 90th |",
              "|---|---|---|---|---|"]
        for r in rates:
            m = cm[r]
            o.append(f"| {r * 100:g}% | {usd(m['reserve'])} | {m['ratio_pcts'][10]:.2f}× / {m['ratio_pcts'][50]:.2f}× | "
                     f"{m['shortfall'] * 100:.2f}% | {usd(m['contrib_pcts'][10])} / {usd(m['contrib_pcts'][50])} / {usd(m['contrib_pcts'][90])} |")
        o += ["", "**A range you could state with a confidence level** (the contribution is at least this much, with the stated probability):", "",
              "| If the reserve earns | 80% confident ≥ | 90% confident ≥ | 95% confident ≥ |", "|---|---|---|---|"]
        for r in rates:
            lb = cm[r]["lower_bounds"]
            o.append(f"| {r * 100:g}% | {usd(lb[0.8])} | {usd(lb[0.9])} | {usd(lb[0.95])} |")
        dd = sim["dd_window"]
        big = dd < -0.30
        r3 = rates[min(range(len(rates)), key=lambda i: abs(rates[i] - 0.03))]
        R3 = cm[r3]["reserve"]
        o += ["", f"### Sequence risk: a large fall in {win[0]}–{win[1]}", "",
              f"| Measure | Value |", "|---|---|",
              f"| Worst fall inside the window, median | {np.median(dd) * 100:.0f}% |",
              f"| Chance of a fall worse than −20% in the window | {(dd < -0.20).mean() * 100:.1f}% |",
              f"| Chance of a fall worse than −30% in the window | {big.mean() * 100:.1f}% |"]
        if big.sum() >= 20:
            o += [f"| Median value on 1 Jan {end} if that happens | {usd(np.median(v[big]))} |",
                  f"| Median value on 1 Jan {end} otherwise | {usd(np.median(v[~big]))} |",
                  f"| Chance value < reserve at {r3 * 100:g}% if that happens | {(v[big] < R3).mean() * 100:.2f}% |"]
        else:
            o.append("| (too few paths with such a fall to condition on) | – |")
        reg = sim["regime"]
        tot = reg.sum(axis=1)[0]
        o += ["", "### Regime days of the growth sleeve (20-day return, ±2% rule)", "",
              f"Out of {tot:,} labelled days, 5th – median – 95th percentile:", "",
              "| Bear | Sideways | Bull |", "|---|---|---|",
              "| " + " | ".join(" – ".join(f"{x:,.0f}" for x in np.percentile(reg[:, j], [5, 50, 95])) for j in range(3)) + " |", ""]
    o += ["## Limits", "",
          "- The sampled history is the only source of randomness. It is limited and includes a long bull market, so the history-based scenario flatters the growth sleeve.",
          "- Block resampling keeps co-movement and short-term clustering but nothing longer than one block.",
          "- The reserve return is a fixed assumption here. In practice it depends on the yields available when the reserve is bought, which is a risk this model does not simulate.",
          "- No taxes, trading costs, or inflation. The payments are fixed in nominal terms.",
          "- Results are ranges under stated assumptions, not predictions.", ""]
    return "\n".join(o)


def make_charts(cfg: dict, results: dict, outdir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from .core import pv_annuity_due

    outdir.mkdir(parents=True, exist_ok=True)
    names = list(results)
    rates = cfg["reserve"]["stress_rates"]
    pmt, n_pay = cfg["reserve"]["payment"], cfg["reserve"]["n_payments"]
    flex = cfg["reserve"].get("flexibility_amount", 0.0)
    fig, axes = plt.subplots(1, len(names), figsize=(6 * len(names), 4.4), sharey=True, squeeze=False, constrained_layout=True)
    for ax, name in zip(axes[0], names):
        sim = results[name]["sim"]
        x = sim["start_year"] + sim["sample_idx"] / TD
        q = np.percentile(sim["values"], [5, 25, 50, 75, 95], axis=0)
        ax.fill_between(x, q[0], q[4], color="#84BBA1", alpha=0.25, label="5th–95th percentile")
        ax.fill_between(x, q[1], q[3], color="#84BBA1", alpha=0.45, label="25th–75th percentile")
        ax.plot(x, q[2], color="#2E6F57", lw=2, label="Median")
        for r, c in zip(rates, ["#C57F86", "#9A4750", "#5F2830"]):
            ax.axhline(pv_annuity_due(pmt, n_pay, r), color=c, ls="--", lw=1.1, label=f"Reserve needed at {r * 100:g}%")
        ax.set_title(name, fontweight="bold")
        ax.set_xlabel("year")
        ax.grid(alpha=0.25)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0][0].set_ylabel("portfolio value")
    axes[0][0].yaxis.set_major_formatter(lambda v, _: f"${v / 1000:,.0f}k")
    axes[0][0].legend(frameon=False, fontsize=7.5, loc="upper left")
    fig.savefig(outdir / "portfolio_fan.png", dpi=110, bbox_inches="tight")
    plt.close(fig)

    r3 = min(rates, key=lambda r: abs(r - 0.03))
    fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
    for name, color in zip(names, ["#2E6F57", "#9A4750", "#5F6673", "#C9A227"]):
        c = results[name]["sim"]["v_final"] - pv_annuity_due(pmt, n_pay, r3) - flex
        ax.hist(c, bins=80, histtype="step", density=True, lw=1.8, color=color, label=name)
    ax.axvline(0, color="#444", ls=":", lw=1.2)
    ax.set_xlabel(f"contribution capacity on 1 Jan {cfg['case']['end_year']} ($), reserve earning {r3 * 100:g}%")
    ax.set_yticks([])
    ax.legend(frameon=False)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    fig.savefig(outdir / "contribution_distribution.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
