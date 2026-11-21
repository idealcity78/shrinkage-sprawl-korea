"""Figures for paper 1 (supply, sprawl and planning; Economic Geography). English labels.

  fig1_groups.png     study units: the 162 시군 by group (registered population change 2000-19), with the eight
                      non-capital regions and the capital region outlined (shrink_sprawl_sigun.csv: group, region)
  fig2_map.png        시군 maps: registered population change 2009-19 (%) and urban land change 2009-19 (%)
                      (shrink_sprawl_sigun.csv: g_rp_0919, g_urb_post), with the shrinking-and-expanding 시군 outlined
  fig3_plan_trend.png planned annual growth against the prior five-year trend, plan vintages adopted 2000+
                      (plan_vintages.csv), non-capital 도 시군 by group
  fig4_event.png      event-study coefficients, k = -3..5 (plan_event_coefs.csv): new plan / plan enlarging the
                      reserve -> urban-use zoning and land-form-change permits, full sample
  fig5_routes.png     new urban land 2009-19 and dwellings added 2015-24 (cells gaining >= 5) by 2026 zoning route,
                      by group (zoning_route_sigun.csv, zoning_route_robust_grid.csv)

Every value plotted is read from the output files named above; nothing is typed in.
The 시군 polygons (data_work/boundary/sigun_sgis2020.shp, simplified to 100 m for drawing) and their dissolve by analysis region are read with arcpy and saved as
vertex arrays in outputs/partA/geometry_sigun.npz and geometry_region.npz; with "models" the figures start from
those files and need no arcpy.
Output: outputs/paper1/
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\paper1_figures.py   (add "models" to skip arcpy)
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PolyCollection

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

A = os.path.join(paths.OUTPUTS, "partA")
OUT = os.path.join(paths.OUTPUTS, "paper1")
GROUPS = {"감소": "Shrinking", "정체": "Stagnant", "성장": "Growing", "광역시": "Metropolitan",
          "수도권": "Capital region"}
COL = {"감소": "#b2182b", "정체": "#ef8a62", "성장": "#2166ac", "광역시": "#7f7f7f", "수도권": "#4d4d4d"}
plt.rcParams.update({"font.family": "Arial", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def map_shp():
    """The 시군 polygons simplified to 100 m for drawing (the analysis uses the full boundary); far below one pixel."""
    import arcpy
    arcpy.env.overwriteOutput = True
    shp = os.path.join(paths.WORK, "boundary", "sigun_sgis2020.shp")
    return arcpy.cartography.SimplifyPolygon(shp, r"memory\sigun_map", "POINT_REMOVE", "100 Meters",
                                             collapsed_point_option="NO_KEEP")[0]


def polygons_arcpy():
    import arcpy
    shp = map_shp()
    out = {}
    with arcpy.da.SearchCursor(shp, ["sigun", "SHAPE@"]) as cur:
        for name, g in cur:
            rings = []
            for part in g:
                ring = []
                for p in part:
                    if p is None:            # interior ring separator
                        if ring:
                            rings.append(np.array(ring))
                        ring = []
                    else:
                        ring.append((p.X, p.Y))
                if ring:
                    rings.append(np.array(ring))
            out.setdefault(name, []).extend(rings)
    return out


def rings_of(g):
    rings = []
    for part in g:
        ring = []
        for p in part:
            if p is None:
                if ring:
                    rings.append(np.array(ring))
                ring = []
            else:
                ring.append((p.X, p.Y))
        if ring:
            rings.append(np.array(ring))
    return rings


def regions_arcpy(t):
    """Dissolve the 시군 polygons by analysis region (eight non-capital regions and the capital region)."""
    import arcpy
    arcpy.env.overwriteOutput = True
    shp = os.path.join(paths.WORK, "boundary", "sigun_sgis2020.shp")
    tmp = arcpy.management.CopyFeatures(shp, r"memory\sigun_tmp")
    arcpy.management.AddField(tmp, "region", "TEXT", field_length=20)
    reg = dict(zip(t.sigun, t.region))
    with arcpy.da.UpdateCursor(tmp, ["sigun", "region"]) as cur:
        for name, _ in cur:
            cur.updateRow([name, reg.get(name, "")])
    # the 시군 are dissolved from the same 읍면동 polygons, so they share edges exactly and dissolve without slivers
    dis = arcpy.management.Dissolve(tmp, r"memory\region_full", "region")
    dis = arcpy.cartography.SimplifyPolygon(dis, r"memory\region_tmp", "POINT_REMOVE", "100 Meters",
                                            collapsed_point_option="NO_KEEP")[0]
    out = {}
    with arcpy.da.SearchCursor(dis, ["region", "SHAPE@"]) as cur:
        for name, g in cur:
            if name:
                out[name] = rings_of(g)
    return out


def save_rings(path, d):
    keys, offs, xy = [], [0], []
    for k, rings in d.items():
        for r in rings:
            keys.append(k)
            xy.append(r)
            offs.append(offs[-1] + len(r))
    np.savez_compressed(path, keys=np.array(keys), offs=np.array(offs), xy=np.concatenate(xy))


def load_rings(path):
    z = np.load(path)
    keys, offs, xy = z["keys"], z["offs"], z["xy"]          # read each array once (NpzFile decompresses per access)
    out = {}
    for k, a, b in zip(keys, offs[:-1], offs[1:]):
        out.setdefault(str(k), []).append(xy[a:b])
    return out


def polygons():
    return load_rings(os.path.join(A, "geometry_sigun.npz"))


def region_outlines(t):
    return load_rings(os.path.join(A, "geometry_region.npz"))


def fig1_groups():
    t = pd.read_csv(os.path.join(A, "shrink_sprawl_sigun.csv"))
    polys = polygons()
    regs = region_outlines(t)
    fill = {"감소": "#d6604d", "정체": "#f4a582", "성장": "#4393c3", "광역시": "#8c8c8c", "수도권": "#d9d9d9"}
    fig, ax = plt.subplots(figsize=(4.6, 5.4))
    for g in GROUPS:
        verts = [ring for name in t[t.group == g].sigun for ring in polys.get(name, [])]
        ax.add_collection(PolyCollection(verts, facecolors=fill[g], edgecolors="white", linewidths=0.2))
    verts = [ring for rr in regs.values() for ring in rr]
    ax.add_collection(PolyCollection(verts, facecolors="none", edgecolors="black", linewidths=0.6))
    en = {"강원": "Gangwon", "충북": "Chungbuk", "충남": "Chungnam", "전북": "Jeonbuk", "전남": "Jeonnam",
          "경북": "Gyeongbuk", "경남": "Gyeongnam", "제주": "Jeju", "수도권": "Capital region"}
    for name, rr in regs.items():
        big = max(rr, key=len)
        x, y = big.mean(axis=0)
        ax.text(x, y, en.get(name, name), fontsize=6.5, ha="center", va="center",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=0.6))
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")
    n = t.group.value_counts()
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=fill[g], edgecolor="grey", linewidth=0.3) for g in GROUPS]
    labels = [f"{GROUPS[g]} ({n.get(g, 0)})" for g in GROUPS]
    ax.legend(handles, labels, frameon=False, fontsize=7, loc="lower right",
              title="Group (si/gun)", title_fontsize=7)
    fig.text(0.01, 0.01, "Groups of non-capital provincial si/gun by registered population change 2000-19: "
             "shrinking < -5%, stagnant -5 to +5%, growing > +5%.\nBold lines: analysis regions (each metropolitan "
             "city is grouped with the surrounding province).", fontsize=6)
    fig.savefig(os.path.join(OUT, "fig1_groups.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)
    return n.reindex(list(GROUPS)).to_dict()


def fig1():
    t = pd.read_csv(os.path.join(A, "shrink_sprawl_sigun.csv"))
    polys = polygons()
    t["both"] = (t.g_rp_0919 < 0) & (t.g_urb_post > 0) & t.group.isin(["감소", "정체", "성장"])
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 4.6))
    specs = [("g_rp_0919", "a. Registered population change, 2009-19 (%)", "RdBu", (-20, 20)),
             ("g_urb_post", "b. Urban land change, 2009-19 (%)", "Reds", (0, 80))]
    for ax, (col, title, cmap, (lo, hi)) in zip(axes, specs):
        verts, vals, edge = [], [], []
        for _, r in t.iterrows():
            for ring in polys.get(r.sigun, []):
                verts.append(ring)
                vals.append(r[col])
                edge.append(bool(r.both))
        pc = PolyCollection(verts, array=np.array(vals, float), cmap=cmap, edgecolors="white", linewidths=0.15)
        pc.set_clim(lo, hi)
        ax.add_collection(pc)
        both = [v for v, e in zip(verts, edge) if e]
        ax.add_collection(PolyCollection(both, facecolors="none", edgecolors="black", linewidths=0.35))
        ax.autoscale_view()
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(title, fontsize=9, loc="left")
        # arrows mark values beyond the colour range (urban land fell in a few units)
        fig.colorbar(pc, ax=ax, shrink=0.55, orientation="horizontal", pad=0.02, extend="both")
    n_both = int(t.both.sum())
    n_dec = int(((t.g_rp_0919 < 0) & t.group.isin(["감소", "정체", "성장"])).sum())
    fig.text(0.01, 0.01, f"Outlined: population fell and urban land grew, 2009-19 "
             f"({n_both} of {n_dec} non-capital provincial si/gun with falling population).", fontsize=7)
    fig.savefig(os.path.join(OUT, "fig2_map.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)
    return n_both, n_dec


def fig2():
    v = pd.read_csv(os.path.join(A, "plan_vintages.csv"))
    v = v[(v.y0 >= 2000) & v.group.isin(["감소", "정체", "성장"])].dropna(subset=["plan_g", "trend_g"])
    # fitted line: plan-on-trend model of Table S8, Panel C (region fixed effects, unit-clustered), drawn through the
    # prediction at zero trend averaged over regions; slope = 1 is the "plans follow the trend" benchmark
    m = pd.read_csv(os.path.join(A, "plan_pop_models.csv"))
    m = m[m.block == "plan_on_trend"].set_index("term")
    b, se, a = m.at["trend_g", "coef"], m.at["trend_g", "se"], m.at["pred_zero_trend", "coef"]
    r = np.corrcoef(v.trend_g, v.plan_g)[0, 1]
    rho = v.trend_g.rank().corr(v.plan_g.rank())
    xl, yl = (-5, 6), (-5, 12)
    out = (v.trend_g < xl[0]) | (v.trend_g > xl[1]) | (v.plan_g < yl[0]) | (v.plan_g > yl[1])
    stats = (f"Figure 3: {len(v)} plan vintages, {int(out.sum())} outside the axes; Pearson r = {r:.3f}, "
             f"Spearman rho = {rho:.3f}; fitted slope {b:.3f} (s.e. {se:.3f}), t against slope 1 = {(1 - b) / se:.1f}; "
             f"prediction at zero trend {a:.3f}")
    with open(os.path.join(OUT, "fig3_stats.txt"), "w", encoding="utf-8") as fh:
        fh.write(stats + "\n")
    fig, ax = plt.subplots(figsize=(3.6, 5.4))
    for g in ["성장", "정체", "감소"]:
        d = v[v.group == g]
        ax.scatter(d.trend_g.clip(*xl), d.plan_g.clip(*yl), s=10, alpha=0.6, color=COL[g],
                   label=f"{GROUPS[g]} (n={len(d)})", marker=None)
        o = d[out[d.index]]
        # vintages beyond the axes: drawn at the edge, pointing the way they lie
        for mk, sel in [("^", o.plan_g > yl[1]), ("v", o.plan_g < yl[0]), (">", o.trend_g > xl[1]), ("<", o.trend_g < xl[0])]:
            ax.scatter(o[sel].trend_g.clip(*xl), o[sel].plan_g.clip(*yl), s=24, color=COL[g], marker=mk,
                       edgecolors="black", linewidths=0.4, zorder=3, clip_on=False)
    ax.plot(xl, xl, color="black", lw=0.7, ls="--")
    ax.plot(xl, [a + b * x for x in xl], color="black", lw=1.0)
    ax.axhline(0, color="grey", lw=0.5)
    ax.axvline(0, color="grey", lw=0.5)
    ax.set_xlim(*xl)
    ax.set_ylim(*yl)
    ax.set_aspect("equal")
    ax.set_xlabel("Population growth in the five years\nbefore adoption (%/yr)")
    ax.set_ylabel("Planned population growth to target year (%/yr)")
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    ax.text(5.8, 5.2, "planned = trend", fontsize=7, ha="right", va="top", rotation=45, rotation_mode="anchor")
    ax.text(-4.8, a + b * -4.8 + 0.3, f"fitted, slope {b:.2f}", fontsize=7, ha="left", va="bottom")
    ax.text(5.8, 11.6, f"r = {r:.2f}\nrank r = {rho:.2f}", fontsize=7, ha="right", va="top")
    fig.savefig(os.path.join(OUT, "fig3_plan_trend.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(stats)
    return len(v)


def fig3():
    c = pd.read_csv(os.path.join(A, "plan_event_coefs.csv"))
    c = c[(c["sample"] == "전체") & ~c.k.isin(["cum0_5", "pre_F_p"])].copy()
    c["k"] = c.k.astype(int)
    c = c[c.k.between(-3, 5)]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharex=True)
    for ax, (y, lab) in zip(axes, [("zone", "a. Urban-use zoning (change)"), ("devp", "b. Land-form-change permits")]):
        for tr, name, off, colr in [("adopt", "Any new plan", -0.12, "#4d4d4d"),
                                    ("res_up", "New plan enlarging the reserve", 0.12, "#b2182b")]:
            d = c[(c.treat == tr) & (c.y == y)].sort_values("k")
            ks = list(d.k) + [-1]
            b = list(d.coef) + [0.0]
            s = list(d.se) + [0.0]
            o = np.argsort(ks)
            ks, b, s = np.array(ks)[o], np.array(b)[o], np.array(s)[o]
            ax.errorbar(ks + off, b, yerr=1.96 * s, fmt="o", ms=3, lw=0.8, capsize=0, color=colr, label=name)
        ax.axhline(0, color="black", lw=0.6)
        ax.axvline(-0.5, color="grey", lw=0.5, ls=":")
        ax.set_title(lab, fontsize=8.5, loc="left")
        ax.set_ylabel("% of zoned urban area per year")
        ax.set_xlabel("Years since the new plan took effect")
    axes[1].legend(frameon=False, fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig4_event.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig4():
    t = pd.read_csv(os.path.join(A, "zoning_route_sigun.csv"))
    R = {"A": "Residential/commercial/industrial zones (planned route)", "B": "Natural green",
         "C": "Other green, unsubdivided urban", "D": "Planned management", "E": "Production/conservation management",
         "F": "Agricultural/natural conservation, other"}
    cols = ["#2166ac", "#a6d96a", "#d9ef8b", "#fdae61", "#f46d43", "#bdbdbd"]
    s = t.groupby("group")[[f"new_{r}" for r in R]].sum().reindex(list(GROUPS))
    sh = s.div(s.sum(axis=1), axis=0) * 100
    # (b) dwellings added outside the old core 2015-24, cells gaining at least 5 (zoning_route_robust.py)
    d = pd.read_csv(os.path.join(A, "zoning_route_robust_grid.csv"))
    d["group"] = d.SG_ID.map(t.set_index("SG_ID").group)
    dh = d.groupby("group")[[f"ge5_{r}" for r in R]].sum().reindex(list(GROUPS))
    dh = dh.div(dh.sum(axis=1), axis=0) * 100
    fig, axes = plt.subplots(2, 1, figsize=(6.4, 4.6), sharex=True)
    for ax, (tab, pre, title) in zip(axes, [(sh, "new", "(a) New urban land 2009-19"),
                                            (dh, "ge5", "(b) Dwellings added outside the old core 2015-24 "
                                                        "(cells gaining at least 5)")]):
        left = np.zeros(len(tab))
        for (r, lab), cc in zip(R.items(), cols):
            ax.barh([GROUPS[g] for g in tab.index], tab[f"{pre}_{r}"], left=left, color=cc, label=lab, height=0.6)
            left += tab[f"{pre}_{r}"].values
        for i, g in enumerate(tab.index):
            ax.text(101, i, f"{100 - tab.loc[g, f'{pre}_A']:.1f}% outside", va="center", fontsize=7)
        ax.set_xlim(0, 118)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=8, loc="left")
    axes[1].set_xlabel("Share by 2026 zoning (%)")
    axes[1].legend(frameon=False, fontsize=6.5, ncol=2, loc="upper center", bbox_to_anchor=(0.45, -0.3))
    fig.savefig(os.path.join(OUT, "fig5_routes.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)
    return sh


def main():
    os.makedirs(OUT, exist_ok=True)
    if "models" not in sys.argv[1:]:
        save_rings(os.path.join(A, "geometry_sigun.npz"), polygons_arcpy())
        save_rings(os.path.join(A, "geometry_region.npz"),
                   regions_arcpy(pd.read_csv(os.path.join(A, "shrink_sprawl_sigun.csv"))))
    print("fig1 groups:", fig1_groups())
    n_both, n_dec = fig1()
    n2 = fig2()
    fig3()
    sh = fig4()
    print(f"fig1: {n_both} of {n_dec} non-capital provincial si/gun with falling population expanded urban land")
    print(f"fig2: {n2} plan vintages")
    print("fig4 outside planned route (%):", (100 - sh.new_A).round(1).to_dict())


if __name__ == "__main__":
    main()
