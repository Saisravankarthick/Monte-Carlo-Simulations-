"""Shared colours and chart styling, so every figure reads the same way (AI-assisted code)."""

from __future__ import annotations

# one colour per sleeve, used everywhere a sleeve appears
SLEEVE = {"growth": "#2E8B57", "matching": "#3B6EA8", "flex": "#E0A030"}
# one colour per scenario, in the order the scenarios appear in the config
SCENARIO = ["#3B6EA8", "#C8553D", "#7B5EA7", "#2A9D8F", "#8C6D46"]
# outcome zones against the reserve
ZONE = {"short": "#D1495B", "thin": "#EDAE49", "ok": "#66A182"}
REGIME = {"Bear": "#D1495B", "Sideways": "#9AA5B1", "Bull": "#66A182"}
INK = "#2B2B2B"
MUTED = "#6B6B6B"


def setup():
    """Import matplotlib in headless mode with the house style and return pyplot."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.facecolor": "white", "axes.facecolor": "white", "axes.edgecolor": "#BBBBBB",
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#E6E6E6",
        "grid.linewidth": 0.8, "axes.axisbelow": True, "axes.titleweight": "bold", "axes.titlesize": 12,
        "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK, "font.size": 10,
        "legend.frameon": False, "legend.fontsize": 9,
    })
    return plt


def money(v: float, _pos=None) -> str:
    """Axis label in thousands of dollars, e.g. $450k."""
    sign = "−" if v < 0 else ""
    return f"{sign}${abs(v) / 1000:,.0f}k"


def usd(x: float) -> str:
    return f"${x:,.0f}" if x >= 0 else f"−${-x:,.0f}"
