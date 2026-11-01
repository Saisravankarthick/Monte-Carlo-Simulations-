"""Key numbers as CSV files, for spreadsheets and for checking by hand (AI-assisted code)."""

from __future__ import annotations

from pathlib import Path


def write_tables(assets: dict, corr, outdir: Path) -> list[str]:
    import pandas as pd

    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, a in assets.items():
        h = a["hist"]
        row = {"fund": name, "description": a["label"], "history_from": a["span"][0], "history_to": a["span"][1],
               "history_years": round(a["span"][2], 1), "hist_growth_a_year": round(h["cagr"], 4),
               "hist_volatility": round(h["vol"], 4), "hist_worst_fall": round(h["worst_fall"], 4), "regime_today": h["regime_now"]}
        for sc, s in a["sums"].items():
            row.update({f"{sc}_end_p{p}": round(v, 2) for p, v in s["end_pcts"].items()})
            row.update({f"{sc}_growth_median": round(s["growth_median"], 4), f"{sc}_chance_of_loss": round(s["p_loss"], 4),
                        f"{sc}_chance_to_double": round(s["p_double"], 4), f"{sc}_worst_fall_median": round(s["mdd_median"], 4),
                        f"{sc}_chance_fall_30": round(s["p_fall_30"], 4)})
            row.update({f"{sc}_{k}_days_share": round(v, 4) for k, v in zip(("bear", "sideways", "bull"), s["regime_share"])})
        rows.append(row)
    files = []
    p = outdir / "fund_summary.csv"
    pd.DataFrame(rows).sort_values("history_end_p50", ascending=False).to_csv(p, index=False)
    files.append(p.relative_to(outdir.parent).as_posix())
    if corr is not None:
        p = outdir / "correlation.csv"
        corr.round(3).to_csv(p)
        files.append(p.relative_to(outdir.parent).as_posix())
    return files
