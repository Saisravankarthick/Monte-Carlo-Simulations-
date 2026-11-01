"""All charts, saved into one folder per category (AI-assisted code).

results/charts/
  1_overview/        outcome ranges per fund, history vs stress
  2_risk_return/     growth against worst fall, chance of loss, chance of big falls
  3_paths/           simulated futures for every fund (one colour per path)
  4_distributions/   where $X ends up, per fund
  5_regimes/         Bear / Sideways / Bull mix, and today's regime
  6_diversification/ how the funds move together
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import style
from .core import TD

CATEGORIES = {"overview": "1_overview", "risk": "2_risk_return", "paths": "3_paths", "dist": "4_distributions",
              "regimes": "5_regimes", "div": "6_diversification"}


def make_all(cfg: dict, assets: dict, corr, outdir: Path) -> dict[str, list[str]]:
    """assets: {name: {"label", "hist", "sims": {scenario: sim}, "sums": {scenario: summary}}}."""
    plt = style.setup()
    from matplotlib.ticker import FuncFormatter

    made: dict[str, list[str]] = {k: [] for k in CATEGORIES}
    fmt_money = FuncFormatter(style.money)
    inv = next(iter(assets.values()))["sums"]["history"]["invested"]
    years = cfg["investment"]["years"]
    order = sorted(assets, key=lambda a: assets[a]["sums"]["history"]["end_pcts"][50], reverse=True)
    color = style.fund_colors(order)

    def save(fig, cat, name):
        d = outdir / CATEGORIES[cat]
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{name}.png"
        fig.savefig(p, dpi=120, bbox_inches="tight")
        plt.close(fig)
        made[cat].append(p.relative_to(outdir.parent).as_posix())

    # ---------------------------------------------------------------- 1 overview
    fig, ax = plt.subplots(figsize=(11, 0.48 * len(order) + 1.8))
    for i, a in enumerate(order):
        p = assets[a]["sums"]["history"]["end_pcts"]
        ax.barh(i, p[95] - p[5], left=p[5], height=0.62, color=color[a], alpha=0.30)
        ax.barh(i, p[75] - p[25], left=p[25], height=0.62, color=color[a], alpha=0.90)
        ax.plot([p[50]] * 2, [i - 0.31, i + 0.31], color="white", lw=2.6)
        ax.text(p[95], i, f"  {style.money(p[50])}", va="center", fontsize=8.5, color=style.INK)
    ax.axvline(inv, color=style.ZONE["short"], lw=1.4, ls="--")
    ax.text(inv, -0.9, f" invested {style.money(inv)}", color=style.ZONE["short"], fontsize=8.5, va="bottom")
    ax.set_yticks(range(len(order)), order)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(fmt_money)
    ax.set_xlabel(f"value after {years} years (light = 5th–95th percentile, dark = 25th–75th, white = median, label = median)")
    ax.set_title(f"Where {style.money(inv)} could end up after {years} years, by fund (history repeats)")
    ax.grid(axis="y", visible=False)
    save(fig, "overview", "outcome_ranges")

    fig, ax = plt.subplots(figsize=(max(9, 0.62 * len(order) + 2), 4.6))
    x = np.arange(len(order))
    for k, (sc, c) in enumerate([("history", style.SCENARIO[0]), ("stress", style.SCENARIO[1])]):
        vals = [assets[a]["sums"][sc]["end_pcts"][50] for a in order]
        ax.bar(x - 0.2 + 0.4 * k, vals, 0.38, color=c, label="history repeats" if sc == "history" else f"stress (−{cfg['simulation']['haircut'] * 100:g} pts a year)")
    ax.axhline(inv, color=style.ZONE["short"], lw=1.2, ls="--", label=f"invested {style.money(inv)}")
    ax.set_xticks(x, order, rotation=45, ha="right")
    ax.yaxis.set_major_formatter(fmt_money)
    ax.set_ylabel(f"median value after {years} years")
    ax.set_title("Median outcome: history repeats vs stress case")
    ax.grid(axis="x", visible=False)
    ax.legend()
    save(fig, "overview", "history_vs_stress")

    # ---------------------------------------------------------------- 2 risk / return
    fig, ax = plt.subplots(figsize=(10, 6.2))
    for a in order:
        s = assets[a]["sums"]["history"]
        xv, yv = -s["mdd_median"] * 100, s["growth_median"] * 100
        ax.scatter(xv, yv, s=140, color=color[a], edgecolor="white", linewidth=1.2, zorder=3)
        ax.annotate(a, (xv, yv), textcoords="offset points", xytext=(7, 5), fontsize=9, fontweight="bold", color=style.INK)
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_xlabel(f"typical worst fall over {years} years (median, %)  →  more painful")
    ax.set_ylabel("typical growth a year (median, %)  →  better")
    ax.set_title("Reward against pain: growth a year vs the typical worst fall")
    save(fig, "risk", "growth_vs_worst_fall")

    by_loss = sorted(order, key=lambda a: assets[a]["sums"]["history"]["p_loss"])
    fig, ax = plt.subplots(figsize=(max(9, 0.62 * len(order) + 2), 4.4))
    vals = [assets[a]["sums"]["history"]["p_loss"] * 100 for a in by_loss]
    bars = ax.bar(by_loss, vals, color=[color[a] for a in by_loss], width=0.7)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.0f}%", ha="center", va="bottom", fontsize=8.5, fontweight="bold")
    ax.set_xticks(range(len(by_loss)), by_loss, rotation=45, ha="right")
    ax.set_ylabel(f"chance of ending below the amount invested (%)")
    ax.set_title(f"Chance of losing money after {years} years (history repeats)")
    ax.grid(axis="x", visible=False)
    save(fig, "risk", "chance_of_loss")

    fig, ax = plt.subplots(figsize=(max(10, 0.75 * len(order) + 2), 4.6))
    x = np.arange(len(order))
    for k, (key, lab, c) in enumerate([("p_fall_20", "worse than −20%", "#EDAE49"), ("p_fall_30", "worse than −30%", "#E07A3F"),
                                       ("p_fall_40", "worse than −40%", "#D1495B")]):
        ax.bar(x - 0.27 + 0.27 * k, [assets[a]["sums"]["history"][key] * 100 for a in order], 0.26, color=c, label=lab)
    ax.set_xticks(x, order, rotation=45, ha="right")
    ax.set_ylabel(f"chance of at least one such fall in {years} years (%)")
    ax.set_title("How often the big falls happen", pad=28)
    ax.set_ylim(0, 105)
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False)
    save(fig, "risk", "chance_of_big_falls")

    # ---------------------------------------------------------------- 3 paths
    ncol = 4
    nrow = -(-len(order) // ncol)
    cmap = plt.get_cmap("RdYlGn")
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 3.0 * nrow), squeeze=False, constrained_layout=True)
    for ax, a in zip(axes.ravel(), order):
        sim = assets[a]["sims"]["history"]
        V = sim["values"]
        xs = sim["sample_idx"] / TD
        rng = np.random.default_rng(0)
        pick = rng.choice(len(V), size=min(60, len(V)), replace=False)
        pick = pick[np.argsort(V[pick, -1])]
        for c, i in zip(cmap(np.linspace(0.02, 0.98, len(pick))), pick):
            ax.plot(xs, V[i], color=c, lw=0.7, alpha=0.8)
        ax.plot(xs, np.median(V, axis=0), color=style.INK, lw=2)
        ax.axhline(inv, color=style.ZONE["short"], lw=1, ls="--")
        ax.set_title(a, fontsize=10.5)
        ax.yaxis.set_major_formatter(fmt_money)
        ax.tick_params(labelsize=8)
    for ax in axes.ravel()[len(order):]:
        ax.set_visible(False)
    fig.suptitle(f"60 of {cfg['simulation']['paths']:,} simulated futures per fund (colour = where each ends: red low, green high; "
                 f"black = median; dashed = invested)", fontweight="bold")
    save(fig, "paths", "simulated_futures_all_funds")

    # ---------------------------------------------------------------- 4 distributions
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 2.8 * nrow), squeeze=False, constrained_layout=True)
    for ax, a in zip(axes.ravel(), order):
        e = assets[a]["sims"]["history"]["end"]
        hi = np.percentile(e, 99.5)
        counts, edges = np.histogram(np.clip(e, None, hi), bins=40)
        centers = (edges[:-1] + edges[1:]) / 2
        ax.bar(centers, counts / len(e) * 100, width=np.diff(edges),
               color=[style.ZONE["short"] if c < inv else style.ZONE["ok"] for c in centers], edgecolor="white", linewidth=0.3)
        ax.axvline(np.median(e), color=style.INK, lw=1.4)
        s = assets[a]["sums"]["history"]
        ax.set_title(f"{a}   loss {s['p_loss'] * 100:.0f}% · median {style.money(s['end_pcts'][50])}", fontsize=9.5)
        ax.xaxis.set_major_formatter(fmt_money)
        ax.tick_params(labelsize=7.5)
        ax.set_yticks([])
    for ax in axes.ravel()[len(order):]:
        ax.set_visible(False)
    fig.suptitle(f"Where {style.money(inv)} ends up after {years} years (red = below the amount invested; black line = median)", fontweight="bold")
    save(fig, "dist", "outcome_distributions")

    # ---------------------------------------------------------------- 5 regimes
    fig, ax = plt.subplots(figsize=(11, 0.45 * len(order) + 1.8))
    for i, a in enumerate(order):
        sh = np.array(assets[a]["sums"]["history"]["regime_share"]) * 100
        left = 0.0
        for j, lab in enumerate(["Bear", "Sideways", "Bull"]):
            ax.barh(i, sh[j], left=left, color=style.REGIME[lab], height=0.62, edgecolor="white", label=lab if i == 0 else None)
            if sh[j] >= 7:
                ax.text(left + sh[j] / 2, i, f"{sh[j]:.0f}%", ha="center", va="center", color="white", fontsize=8.5, fontweight="bold")
            left += sh[j]
        now = assets[a]["hist"]["regime_now"]
        ax.text(101.5, i, now, va="center", fontsize=9, fontweight="bold", color=style.REGIME[now])
    ax.text(101.5, -0.95, "today", fontsize=8.5, color=style.MUTED)
    ax.set_yticks(range(len(order)), order)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("median share of days in each regime over the simulated years (20-day return, ±2% rule)")
    ax.set_title("Regime mix by fund, and the regime each is in today")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.grid(axis="y", visible=False)
    save(fig, "regimes", "regime_mix")

    # ---------------------------------------------------------------- 6 diversification
    if corr is not None and len(corr) > 1:
        names = [a for a in order if a in corr.index]
        C = corr.loc[names, names].to_numpy()
        fig, ax = plt.subplots(figsize=(0.6 * len(names) + 3, 0.55 * len(names) + 2))
        im = ax.imshow(C, cmap="RdBu_r", vmin=-1, vmax=1)
        for i in range(len(names)):
            for j in range(len(names)):
                if np.isfinite(C[i, j]):
                    ax.text(j, i, f"{C[i, j]:.2f}", ha="center", va="center", fontsize=7,
                            color="white" if abs(C[i, j]) > 0.6 else style.INK)
        ax.set_xticks(range(len(names)), names, rotation=45, ha="right")
        ax.set_yticks(range(len(names)), names)
        ax.grid(False)
        fig.colorbar(im, ax=ax, shrink=0.8, label="correlation of daily returns")
        ax.set_title("How the funds move together (red = together, blue = opposite)")
        save(fig, "div", "correlation_heatmap")
    return made
