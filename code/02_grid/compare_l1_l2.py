"""Check whether middle-class (L2) urban change 2007->2022 becomes comparable once it is measured as
"urban presence" in 100 m cells, using the consistent large-class (L1) 2009->2019 series as reference.

Inputs : data_work/grid100/{l1_2009, l1_2019, l2_2007, l2_2022}.npz  (grid_lc_share.py)
         시군 boundaries and capital-region zones via sigun.py (162 시군, 2022)
Outputs: outputs/grid100_check/
           levels.csv        urban area per source at each threshold (national, non-capital)
           change.csv        cells gained / lost / net between the two dates per series and threshold
           overlap.csv       cell-level agreement of new urban cells between the two series
           sigun_change.csv  net urban change per 시군, both series, each threshold
           sigun_corr.csv    correlation of the 시군 changes between the series
A cell counts as urban when its urban share (% of 10 m subcells in 110-160 or L1 class 1) >= t.

Run with ArcGIS Pro Python:  propy.bat code\\02_grid\\compare_l1_l2.py
"""
import csv
import os
import sys

import arcpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
import sigun

sys.stdout.reconfigure(encoding="utf-8")
arcpy.env.overwriteOutput = True

GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "grid100_check")
THRESHOLDS = [1, 10, 20, 30, 50]
CELL_KM2 = 0.01
SERIES = {"L1 2009-2019": ("l1_2009", "l1_2019"), "L2 2007-2022": ("l2_2007", "l2_2022")}


def load(name):
    z = np.load(os.path.join(GRID, f"{name}.npz"))
    return z


def write(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    data = {n: load(n) for n in ("l1_2009", "l1_2019", "l2_2007", "l2_2022")}
    z = data["l1_2009"]
    x0, y0 = int(z["x0"]), int(z["y0"])
    nrow, ncol = z["urb"].shape
    sg, names, cap = sigun.raster(x0, y0, nrow, ncol)
    land = sg > 0
    noncap = land & ~np.isin(sg, list(cap))
    # cells covered by all four sources, so coverage differences (sea, islands, sheet gaps) do not count
    common = land.copy()
    for d in data.values():
        common &= d["cov"] >= 50
    print(f"land cells {land.sum():,}, common coverage {common.sum():,} ({common.sum() / land.sum():.1%})")

    urb = {n: d["urb"] for n, d in data.items()}

    # 1) levels
    rows = []
    for n, a in urb.items():
        for region, m in (("전국", common), ("비수도권", common & noncap)):
            rows.append([n, region, "share-weighted", round(float(a[m].astype(np.int64).sum()) / 100 * CELL_KM2, 1)])
            for t in THRESHOLDS:
                rows.append([n, region, f">={t}%", round(float((a[m] >= t).sum()) * CELL_KM2, 1)])
    write("levels.csv", ["source", "region", "measure", "urban_km2"], rows)
    print("\nUrban area (km2), common coverage, 비수도권:")
    print(f"{'measure':>15}" + "".join(f"{n:>10}" for n in urb))
    for meas in ["share-weighted"] + [f">={t}%" for t in THRESHOLDS]:
        vals = [r[3] for r in rows if r[1] == "비수도권" and r[2] == meas]
        print(f"{meas:>15}" + "".join(f"{v:>10,.0f}" for v in vals))

    # 2) change and 3) overlap
    ch, ov = [], []
    print("\nChange in urban cells (km2), 비수도권: gained / lost / net")
    for t in THRESHOLDS:
        gains = {}
        line = f"  >={t:>2}%"
        for s, (a, b) in SERIES.items():
            ua, ub = urb[a] >= t, urb[b] >= t
            m = common & noncap
            g, l = (~ua & ub & m), (ua & ~ub & m)
            gains[s] = g
            ch.append([s, t, round(g.sum() * CELL_KM2, 1), round(l.sum() * CELL_KM2, 1), round((g.sum() - l.sum()) * CELL_KM2, 1)])
            line += f"   {s}: {g.sum() * CELL_KM2:,.0f} / {l.sum() * CELL_KM2:,.0f} / {(g.sum() - l.sum()) * CELL_KM2:+,.0f}"
        print(line)
        g1, g2 = gains["L1 2009-2019"], gains["L2 2007-2022"]
        both = (g1 & g2).sum()
        # 1 km blocks are more forgiving of small position differences between 30 m and 5 m maps
        b1 = g1[: nrow // 10 * 10, : ncol // 10 * 10].reshape(nrow // 10, 10, ncol // 10, 10).any(axis=(1, 3))
        b2 = g2[: nrow // 10 * 10, : ncol // 10 * 10].reshape(nrow // 10, 10, ncol // 10, 10).any(axis=(1, 3))
        ov.append([t, int(g1.sum()), int(g2.sum()), int(both),
                   round(both / max(g1.sum(), 1), 3), round(both / max(g2.sum(), 1), 3),
                   int(b1.sum()), int(b2.sum()), int((b1 & b2).sum()),
                   round((b1 & b2).sum() / max(b1.sum(), 1), 3), round((b1 & b2).sum() / max(b2.sum(), 1), 3)])
    write("change.csv", ["series", "threshold_pct", "gained_km2", "lost_km2", "net_km2"], ch)
    write("overlap.csv", ["threshold_pct", "L1_new_cells", "L2_new_cells", "both_cells", "share_of_L1_new_also_L2",
                          "share_of_L2_new_also_L1", "L1_new_1km", "L2_new_1km", "both_1km",
                          "share_of_L1_1km_also_L2", "share_of_L2_1km_also_L1"], ov)
    print("\nNew urban cells found by both series (비수도권): 100 m cells / 1 km blocks")
    for r in ov:
        print(f"  >={r[0]:>2}%  100m: {r[4]:.0%} of L1-new also L2-new, {r[5]:.0%} of L2-new also L1-new"
              f"   1km: {r[9]:.0%} / {r[10]:.0%}")

    # 4) 시군 comparison
    ids = sorted(names)
    srows, corr = [], []
    print("\n시군 net change correlation (비수도권 시군):")
    for t in THRESHOLDS:
        net = {}
        for s, (a, b) in SERIES.items():
            d = (urb[b] >= t).astype(np.int8) - (urb[a] >= t).astype(np.int8)
            d[~common] = 0
            net[s] = np.bincount(sg.ravel(), weights=d.ravel(), minlength=max(ids) + 1) * CELL_KM2
        for i in ids:
            srows.append([t, i, names[i], "비수도권" if i not in cap else "수도권",
                          round(net["L1 2009-2019"][i], 2), round(net["L2 2007-2022"][i], 2)])
        nc = [i for i in ids if i not in cap]
        v1 = np.array([net["L1 2009-2019"][i] for i in nc])
        v2 = np.array([net["L2 2007-2022"][i] for i in nc])
        r = float(np.corrcoef(v1, v2)[0, 1])
        rs = float(np.corrcoef(np.argsort(np.argsort(v1)), np.argsort(np.argsort(v2)))[0, 1])
        pos = float(((v1 > 0) == (v2 > 0)).mean())
        corr.append([t, len(nc), round(r, 3), round(rs, 3), round(pos, 3)])
        print(f"  >={t:>2}%  Pearson {r:.2f}, Spearman {rs:.2f}, same sign {pos:.0%} of {len(nc)} 시군")
    write("sigun_change.csv", ["threshold_pct", "SG_ID", "sigun", "zone", "L1_net_km2", "L2_net_km2"], srows)
    write("sigun_corr.csv", ["threshold_pct", "n_sigun", "pearson", "spearman", "same_sign_share"], corr)
    print(f"\ntables: {OUT}")


if __name__ == "__main__":
    main()
