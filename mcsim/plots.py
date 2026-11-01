"""All charts, saved into one folder per category (AI-assisted code).

results/charts/
  1_inputs/    glide path, what the sampled history looked like
  2_paths/     simulated futures (one colour per path) and percentile fans
  3_outcomes/  where the portfolio ends up on the valuation date
  4_funding/   shortfall chance, contribution with confidence levels, contribution ranges
  5_risk/      worst fall in the stress window, regime days
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import style
from .core import SLEEVES, TD, pv_annuity_due

CATEGORIES = {"inputs": "1_inputs", "paths": "2_paths", "outcomes": "3_outcomes", "funding": "4_funding", "risk": "5_risk"}
PCTS = (5, 10, 25, 50, 75, 90, 95)


def central_rate(rates) -> float:
    """The reserve rate used for single-rate charts: the one closest to 3%."""
    return min(rates, key=lambda r: abs(r - 0.03))


def make_all(cfg: dict, hist, results: dict, outdir: Path) -> dict[str, list[str]]:
    """Draw every chart. Returns {category: [paths relative to the results folder]}."""
    plt = style.setup()
    from matplotlib.patches import Patch
    from matplotlib.ticker import FuncFormatter

    made: dict[str, list[str]] = {k: [] for k in CATEGORIES}
    names = list(results)
    scol = {n: style.SCENARIO[i % len(style.SCENARIO)] for i, n in enumerate(names)}
    rates = cfg["reserve"]["stress_rates"]
    pmt, n_pay = cfg["reserve"]["payment"], cfg["reserve"]["n_payments"]
    flex = cfg["reserve"].get("flexibility_amount", 0.0)
    r0 = central_rate(rates)
    R0 = pv_annuity_due(pmt, n_pay, r0)
    end = cfg["case"]["end_year"]
    win = tuple(cfg["case"].get("stress_window", (2031, 2032)))
    fmt_money = FuncFormatter(style.money)

    def save(fig, cat, name):
        d = outdir / CATEGORIES[cat]
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{name}.png"
        fig.savefig(p, dpi=120, bbox_inches="tight")
        plt.close(fig)
        made[cat].append(p.relative_to(outdir.parent).as_posix())

    # ---------------------------------------------------------------- 1 inputs
    years = list(cfg["glide"])
    W = np.array([cfg["glide"][y] for y in years]) * 100
    fig, ax = plt.subplots(figsize=(8.5, 4))
    bottom = np.zeros(len(years))
    for j, s in enumerate(SLEEVES):
        bars = ax.bar([str(y) for y in years], W[:, j], bottom=bottom, color=style.SLEEVE[s], label=s.capitalize(),
                      edgecolor="white", linewidth=1.2, width=0.68)
        for b, v, bt in zip(bars, W[:, j], bottom):
            if v >= 6:
                ax.text(b.get_x() + b.get_width() / 2, bt + v / 2, f"{v:.0f}%", ha="center", va="center",
                        color="white", fontsize=9.5, fontweight="bold")
        bottom += W[:, j]
    ax.set_ylim(0, 100)
    ax.set_ylabel("share of the portfolio (%)")
    ax.set_title("Glide path: target weights set each 1 January")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    ax.grid(axis="x", visible=False)
    save(fig, "inputs", "glide_path")

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), constrained_layout=True)
    for ax, (col, title, scale, f) in zip(axes, [("mean", "Average return a year", 100, "{:.1f}%"),
                                                 ("vol", "Volatility a year", 100, "{:.1f}%"),
                                                 ("worst_fall", "Worst fall", 100, "{:.1f}%")]):
        vals = [hist.loc[s, col] * scale for s in SLEEVES]
        bars = ax.bar([s.capitalize() for s in SLEEVES], vals, color=[style.SLEEVE[s] for s in SLEEVES], width=0.6)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, f.format(v), ha="center", va="bottom" if v >= 0 else "top",
                    fontsize=9.5, fontweight="bold", color=style.INK)
        ax.axhline(0, color="#999", lw=0.8)
        ax.set_title(title)
        ax.grid(axis="x", visible=False)
        lo, hi = min(vals + [0]), max(vals + [0])
        ax.set_ylim(lo - 0.15 * (hi - lo + 1), hi + 0.15 * (hi - lo + 1))
    fig.suptitle("What the sampled history looked like, by sleeve", fontweight="bold")
    save(fig, "inputs", "sleeve_history")

    # ---------------------------------------------------------------- 2 paths
    for name in names:
        sim = results[name]["sim"]
        x = sim["start_year"] + sim["sample_idx"] / TD
        V = sim["values"]
        rng = np.random.default_rng(0)
        pick = rng.choice(len(V), size=min(150, len(V)), replace=False)
        pick = pick[np.argsort(V[pick, -1])]
        cmap = plt.get_cmap("RdYlGn")
        fig, ax = plt.subplots(figsize=(10, 5))
        for c, i in zip(cmap(np.linspace(0.02, 0.98, len(pick))), pick):
            ax.plot(x, V[i], color=c, lw=0.9, alpha=0.8)
        q = np.percentile(V, [5, 50, 95], axis=0)
        ax.plot(x, q[1], color=style.INK, lw=2.6, label="Median of all futures")
        ax.plot(x, q[0], color=style.INK, lw=1.4, ls="--", label="5th and 95th percentile")
        ax.plot(x, q[2], color=style.INK, lw=1.4, ls="--")
        ax.axhline(R0, color=style.ZONE["short"], lw=1.8, ls=(0, (6, 3)), label=f"Reserve needed if it earns {r0 * 100:g}%")
        ax.yaxis.set_major_formatter(fmt_money)
        ax.set_xlabel("year")
        ax.set_ylabel("portfolio value")
        ax.set_title(f"{name}: {len(pick)} of {len(V):,} simulated futures (colour = where each one ends: red low, green high)")
        ax.legend(loc="upper left")
        save(fig, "paths", f"paths_{name}")

    fig, axes = plt.subplots(1, len(names), figsize=(6.2 * len(names), 4.6), sharey=True, squeeze=False, constrained_layout=True)
    for ax, name in zip(axes[0], names):
        sim = results[name]["sim"]
        x = sim["start_year"] + sim["sample_idx"] / TD
        q = np.percentile(sim["values"], [5, 25, 50, 75, 95], axis=0)
        c = scol[name]
        ax.fill_between(x, q[0], q[4], color=c, alpha=0.18, label="5th–95th percentile")
        ax.fill_between(x, q[1], q[3], color=c, alpha=0.38, label="25th–75th percentile")
        ax.plot(x, q[2], color=c, lw=2.4, label="Median")
        for r, ls in zip(rates, [":", "--", "-."]):
            ax.axhline(pv_annuity_due(pmt, n_pay, r), color=style.ZONE["short"], lw=1.1, ls=ls, label=f"Reserve at {r * 100:g}%")
        ax.set_title(name)
        ax.set_xlabel("year")
        ax.yaxis.set_major_formatter(fmt_money)
    axes[0][0].set_ylabel("portfolio value")
    axes[0][0].legend(loc="upper left", fontsize=8)
    save(fig, "paths", "fan_all_scenarios")

    # ---------------------------------------------------------------- 3 outcomes
    for name in names:
        v = results[name]["sim"]["v_final"]
        counts, edges = np.histogram(v, bins=60)
        share = counts / len(v) * 100
        centers = (edges[:-1] + edges[1:]) / 2
        colors = [style.ZONE["short"] if c < R0 else style.ZONE["thin"] if c < R0 * 1.10 else style.ZONE["ok"] for c in centers]
        fig, ax = plt.subplots(figsize=(10, 4.8))
        ax.bar(centers, share, width=np.diff(edges), color=colors, edgecolor="white", linewidth=0.5)
        smooth = np.convolve(share, np.ones(5) / 5, mode="same")
        ax.plot(centers, smooth, color=style.INK, lw=1.5)
        top = share.max()
        for p, ls in [(5, ":"), (50, "-"), (95, ":")]:
            qv = np.percentile(v, p)
            ax.axvline(qv, color=style.INK, ls=ls, lw=1.2)
            ax.text(qv, top * 1.08, f"{p}th\n{style.money(qv)}", ha="center", va="bottom", fontsize=8.5, color=style.INK)
        ax.axvline(R0, color=style.ZONE["short"], lw=2.2)
        p_short = (v < R0).mean() * 100
        p_thin = ((v >= R0) & (v < R0 * 1.10)).mean() * 100
        ax.legend(handles=[Patch(color=style.ZONE["short"], label=f"Below the reserve: {p_short:.1f}%"),
                           Patch(color=style.ZONE["thin"], label=f"Up to 10% above the reserve: {p_thin:.1f}%"),
                           Patch(color=style.ZONE["ok"], label=f"More than 10% above: {100 - p_short - p_thin:.1f}%")],
                  loc="upper right", title=f"Reserve at {r0 * 100:g}% = {style.money(R0)}")
        ax.set_ylim(0, top * 1.35)
        ax.xaxis.set_major_formatter(fmt_money)
        ax.set_xlabel(f"portfolio value on 1 Jan {end}")
        ax.set_ylabel("share of simulated futures (%)")
        ax.set_title(f"{name}: where the portfolio ends up on 1 Jan {end}")
        save(fig, "outcomes", f"value_{end}_{name}")

    # ---------------------------------------------------------------- 4 funding
    xpos = np.arange(len(rates))
    w = 0.8 / len(names)
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for k, name in enumerate(names):
        v = results[name]["sim"]["v_final"]
        vals = [(v < pv_annuity_due(pmt, n_pay, r)).mean() * 100 for r in rates]
        bars = ax.bar(xpos - 0.4 + w * (k + 0.5), vals, w * 0.92, color=scol[name], label=name)
        for b, val in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, val, f"{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_xticks(xpos, [f"Reserve earns {r * 100:g}%\n(needs {style.money(pv_annuity_due(pmt, n_pay, r))})" for r in rates])
    ax.set_ylabel("chance the portfolio is below the reserve (%)")
    ax.set_title(f"Funding reliability on 1 Jan {end}: chance of a shortfall")
    ax.grid(axis="x", visible=False)
    ax.legend()
    save(fig, "funding", "shortfall_by_reserve_rate")

    confs = (0.80, 0.90, 0.95)
    xpos = np.arange(len(confs))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for k, name in enumerate(names):
        c = results[name]["sim"]["v_final"] - R0 - flex
        vals = [np.percentile(c, (1 - cf) * 100) for cf in confs]
        bars = ax.bar(xpos - 0.4 + w * (k + 0.5), vals, w * 0.92, color=scol[name], label=name)
        for b, val in zip(bars, vals):
            if val < 0:
                b.set_hatch("///")
                b.set_edgecolor(style.ZONE["short"])
            ax.text(b.get_x() + b.get_width() / 2, val, style.money(val), ha="center", va="bottom" if val >= 0 else "top",
                    fontsize=9, fontweight="bold")
    ax.axhline(0, color="#888", lw=1)
    ax.set_xticks(xpos, [f"{cf * 100:.0f}% confident" for cf in confs])
    ax.yaxis.set_major_formatter(fmt_money)
    ax.set_ylabel("contribution is at least")
    ax.set_title(f"Contribution you could state with a confidence level (reserve earning {r0 * 100:g}%)")
    ax.grid(axis="x", visible=False)
    ax.legend()
    save(fig, "funding", "contribution_confidence")

    rows = [(name, r) for name in names for r in rates]
    fig, ax = plt.subplots(figsize=(10, 0.55 * len(rows) + 1.6))
    for i, (name, r) in enumerate(rows):
        c = results[name]["sim"]["v_final"] - pv_annuity_due(pmt, n_pay, r) - flex
        p = np.percentile(c, PCTS)
        ax.barh(i, p[5] - p[1], left=p[1], height=0.6, color=scol[name], alpha=0.35)
        ax.barh(i, p[4] - p[2], left=p[2], height=0.6, color=scol[name], alpha=0.85)
        ax.plot([p[3], p[3]], [i - 0.3, i + 0.3], color="white", lw=2.5)
        ax.text(p[5], i, f"  median {style.money(p[3])}", va="center", fontsize=8.5, color=style.INK)
    ax.axvline(0, color=style.ZONE["short"], lw=1.4)
    ax.set_yticks(range(len(rows)), [f"{n} · reserve {r * 100:g}%" for n, r in rows])
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(fmt_money)
    ax.set_xlabel(f"contribution capacity on 1 Jan {end} (light bar = 10th–90th percentile, dark = 25th–75th, white line = median)")
    ax.set_title("Range for the facility contribution")
    ax.grid(axis="y", visible=False)
    save(fig, "funding", "contribution_ranges")

    # ---------------------------------------------------------------- 5 risk
    fig, ax = plt.subplots(figsize=(10, 4.4))
    data = [results[n]["sim"]["dd_window"] * 100 for n in names]
    lo = min(d.min() for d in data)
    bins = np.linspace(min(lo, -35), 0, 36)
    ax.hist(data, bins=bins, color=[scol[n] for n in names], label=names, rwidth=0.9)
    for t in (-20, -30):
        ax.axvline(t, color=style.ZONE["short"], ls="--", lw=1.2)
        ax.text(t, 0.02, f" {t}%", color=style.ZONE["short"], fontsize=9, va="bottom", transform=ax.get_xaxis_transform())
    lines = [f"{n}: worse than −20% in {(d < -20).mean() * 100:.1f}% of futures" for n, d in zip(names, data)]
    ax.legend(title="\n".join(lines), loc="upper left", title_fontsize=8.5)
    ax.set_xlabel(f"worst fall inside {win[0]}–{win[1]} (%)")
    ax.set_ylabel("number of simulated futures")
    ax.set_title(f"Sequence risk: the largest fall during {win[0]}–{win[1]}")
    save(fig, "risk", "stress_window_drawdown")

    fig, ax = plt.subplots(figsize=(10, 0.7 * len(names) + 1.6))
    for i, name in enumerate(names):
        reg = results[name]["sim"]["regime"]
        shares = np.median(reg, axis=0) / reg.sum(axis=1)[0] * 100
        left = 0.0
        for j, lab in enumerate(["Bear", "Sideways", "Bull"]):
            ax.barh(i, shares[j], left=left, color=style.REGIME[lab], height=0.6, label=lab if i == 0 else None, edgecolor="white")
            ax.text(left + shares[j] / 2, i, f"{lab} {shares[j]:.0f}%", ha="center", va="center", color="white", fontsize=9, fontweight="bold")
            left += shares[j]
    ax.set_yticks(range(len(names)), names)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("median share of days in each regime (growth sleeve, 20-day return, ±2% rule)")
    ax.set_title("Regime mix of the growth sleeve over the accumulation years")
    ax.grid(axis="y", visible=False)
    save(fig, "risk", "regime_days")
    return made
