"""Figures for paper 2 (old-core migration paths) from existing outputs. Static PNGs for the manuscript.

  fig1_destinations.png  where old-core movers go, 2001-2025 in five-year periods: share of old-core out-moves (moves between old-core
                         동 excluded) to new residential land in the same 시군, innovation/enterprise-city zones and the
                         capital region; all other destinations in grey (outputs/flows/mdis_old_core_flows.csv)
  fig2_age_paths.png     share of each age group's old-core out-moves going to new land + zones (left) and to the
                         capital region (right), five-year periods (same source; flows_age.py tables)
  fig3_zone_event.png    event study of new-town move-in: old core -> zone moves and old-core net migration per 1,000
                         old-core residents, years -8..+8 around onset, 95 % CI (outputs/partB/zone_event.csv)
  fig4_bound.png         supply coefficients of near peripheral supply (0-0.5 km, 0.5-2 km) on old-core net
                         migration: observed, minus the same-dong upper bound, minus the bound net of expected natural
                         increase; register-census periods (outputs/partB/same_dong_bound_vital_models.csv)
Palette: categorical slots 1-3 of the reference palette (blue, orange, aqua), others grey; one axis per panel.

Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\paper2_figures.py
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
OUT = os.path.join(paths.OUTPUTS, "paper2")
FLOWS = os.path.join(paths.OUTPUTS, "flows")
PB = os.path.join(paths.OUTPUTS, "partB")
C1, C2, C3, GREY, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#a3a29c", "#0b0b0b", "#52514e", "#e6e5e0"
AGES = {"a00_14": "0–14", "a15_24": "15–24", "a25_39": "25–39", "a40_64": "40–64", "a65p": "65+"}

plt.rcParams.update({"font.family": "Arial", "axes.unicode_minus": False, "font.size": 9,
                     "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "axes.axisbelow": True, "figure.dpi": 200, "savefig.bbox": "tight"})


def old_out():
    r = pd.read_csv(os.path.join(FLOWS, "mdis_old_core_flows.csv"))
    return r[(r.side == "out") & (r.part == "old") & ~r.other.isin(["old", "unknown"])]


def label_end(ax, x, y, text, color):
    ax.annotate(text, (x, y), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8, color=INK)


PLAB = ["2001–05", "2006–10", "2011–15", "2016–20", "2021–25"]


def fig1():
    # five-year periods: new residential land is fixed at the grid years (2000, 2005, 2010, ...), so the annual
    # series steps up when the next grid year applies (0 % in 2001-02); period shares avoid reading those steps
    o = old_out().copy()
    o["period"] = pd.cut(o.year, [2000, 2005, 2010, 2015, 2020, 2025], labels=PLAB)
    t = o.groupby(["period", "other"], observed=True).pers.sum().unstack(fill_value=0)
    sh = t.div(t.sum(axis=1), axis=0) * 100
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    x = list(range(len(sh)))
    for i, col in enumerate(["same_do", "rest", "metro", "elsewhere"]):
        ax.plot(x, sh[col], color=GREY, lw=1, marker="o", ms=3,
                label="Other destinations (other si/gun in the province, rest of the same si/gun, adjacent metro city, elsewhere)" if i == 0 else None)
    for col, lab, c in [("new", "New residential land, same si/gun", C1), ("capital", "Capital region", C2), ("zone", "Innovation/enterprise-city zones", C3)]:
        ax.plot(x, sh[col], color=c, lw=2, marker="o", ms=4, label=lab)
    ax.set_xticks(x, sh.index, fontsize=8)
    ax.set_ylabel("Share of old-core out-moves (%)")
    ax.legend(frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2)
    ax.set_title("Destinations of old-core out-movers, si/gun of the eight non-capital provinces", loc="left", fontsize=10, color=INK)
    fig.savefig(os.path.join(OUT, "fig1_destinations.png"))
    plt.close(fig)
    return sh.round(1)


def fig2():
    o = old_out().copy()
    o["period"] = pd.cut(o.year, [2000, 2005, 2010, 2015, 2020, 2025],
                         labels=["2001–05", "2006–10", "2011–15", "2016–20", "2021–25"])
    o["dest"] = np.where(o.other.isin(["new", "zone"]), "new", np.where(o.other == "capital", "capital", "other"))
    t = o.groupby(["period", "dest"], observed=True)[list(AGES)].sum()
    tot = t.groupby(level=0).sum()
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.2), sharey=True)
    for ax, dest, title in [(axs[0], "new", "a. To new residential land and new towns"), (axs[1], "capital", "b. To the capital region")]:
        sh = t.xs(dest, level=1) / tot * 100
        for a, lab in AGES.items():
            c = {"a00_14": C1, "a15_24": C2, "a25_39": C3}.get(a, GREY)
            ax.plot(range(len(sh)), sh[a], color=c, lw=2 if c != GREY else 1, marker="o", ms=4)
            label_end(ax, len(sh) - 1, sh[a].iloc[-1], lab, c)
        ax.set_xticks(range(len(sh)), sh.index, fontsize=8)
        ax.set_xlim(-0.3, len(sh) - 0.2)
        ax.set_title(title, loc="left", fontsize=10, color=INK)
    axs[0].set_ylabel("Share of the age group's old-core out-moves (%)")
    fig.savefig(os.path.join(OUT, "fig2_age_paths.png"))
    plt.close(fig)
    return (t.xs("new", level=1) / tot * 100).round(1)


def fig3():
    z = pd.read_csv(os.path.join(PB, "zone_event.csv"))
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0))
    for ax, y, title, c in [(axs[0], "out_zone", "a. Old core to new-town zone", C1), (axs[1], "net_old", "b. Old-core net migration", C2)]:
        d = z[z.y == y].sort_values("k")
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.axvline(-0.5, color=GRID, lw=1, ls="--")
        ax.fill_between(d.k, d.coef - 1.96 * d.se, d.coef + 1.96 * d.se, color=c, alpha=.15, lw=0)
        ax.plot(d.k, d.coef, color=c, lw=2, marker="o", ms=4)
        ax.set_xlabel("Years since move-in onset")
        ax.set_title(title, loc="left", fontsize=10, color=INK)
    axs[0].set_ylabel("Per 1,000 old-core residents per year")
    fig.savefig(os.path.join(OUT, "fig3_zone_event.png"))
    plt.close(fig)


def fig4():
    m = pd.read_csv(os.path.join(PB, "same_dong_bound_vital_models.csv"))
    m = m[m["sample"].str.startswith("등록센서스") & m.term.isin(["s_b1", "s_b2"])]
    specs = [("net_old 관측", "Observed net migration", GREY), ("net_old - H_ub (기존)", "Minus same-dong upper bound", C1),
             ("net_old - H_v (자연증가 반영)", "Minus bound net of natural increase", C2)]
    fig, ax = plt.subplots(figsize=(6.0, 2.8))
    terms = {"s_b1": "Supply 0–0.5 km", "s_b2": "Supply 0.5–2 km"}
    for i, (t, tl) in enumerate(terms.items()):
        for j, (y, lab, c) in enumerate(specs):
            r = m[(m.term == t) & (m.y == y)].iloc[0]
            pos = i - 0.22 + j * 0.22
            ax.errorbar(r.coef, pos, xerr=1.96 * r.se, fmt="o", color=c, ms=6, lw=1.5, capsize=0,
                        label=lab if i == 0 else None)
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_yticks(range(len(terms)), list(terms.values()))
    ax.invert_yaxis()
    ax.set_xlabel("Coefficient on old-core net migration (per 1,000 per year, per 1 pp/yr supply; 95% CI)")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.grid(axis="y", visible=False)
    ax.set_title("Peripheral supply and old-core net migration, same-dong correction, 2015–2024", loc="left", fontsize=10, color=INK)
    fig.savefig(os.path.join(OUT, "fig4_bound.png"))
    plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    sh = fig1()
    print("fig1 행선지 비중 (%)\n" + sh.to_string())
    print("\nfig2 신규개발지·신도시로 간 비중 (%)\n" + fig2().to_string())
    fig3()
    fig4()
    print("\nfigures:", sorted(f for f in os.listdir(OUT) if f.endswith(".png")))


if __name__ == "__main__":
    main()
