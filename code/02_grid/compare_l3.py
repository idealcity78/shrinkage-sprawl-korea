"""Fine-class (L3) 2019 -> 2025 on the 100 m grid: link to the large-class series and describe change.

1. Level check: urban area of L3 2019 against L1 2019 (same year, different maps) at several
   thresholds, and how often a cell is urban in both - can the two series be chained?
2. L3 change 2019 -> 2025 by group (share-weighted km2 and cells over thresholds), 비수도권.
3. Use of L1 new development (2009 < 10 %, 2019 >= 50 %) seen in L3 2019 (fine classes, e.g.
   detached vs apartment housing), compared with the L2 2022 view.
4. 시군 table of L3 change by group.
5. New-development patches: cells going from < 10 % to >= 50 % urban, 8-connected, >= 10 cells.
   The two L3 editions are drawn at different detail (2025 has 3-5x more polygons, roads split
   out of lots), so group areas do not compare; whole patches of non-urban turning urban do.
   Checked against the L1 2009 -> 2019 net gain by 시군 (Spearman).

Inputs : data_work/grid100/{l1_2009, l1_2019, l2_2022, l3_2019, l3_2025}.npz
Outputs: outputs/grid100_check/l3_levels.csv, l3_change.csv, l3_newdev_use.csv, l3_sigun_change.csv,
         l3_patch_gain.csv

Run with ArcGIS Pro Python:  propy.bat code\\02_grid\\compare_l3.py
"""
import csv
import os
import sys

import numpy as np
from scipy import ndimage, stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
import sigun

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "grid100_check")
THRESHOLDS = [10, 30, 50]
PATCH_MIN = 10  # cells (10 ha)
CELL_KM2 = 0.01
L3_GROUPS = ["urb", "res", "det", "apt", "ind", "com", "mix", "cul", "tra", "road", "pub",
             "agr", "for", "grs", "wet", "bar", "wat"]


def write(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def km2(a, m):
    return float(a[m].astype(np.int64).sum()) / 100 * CELL_KM2


def main():
    os.makedirs(OUT, exist_ok=True)
    d = {n: np.load(os.path.join(GRID, f"{n}.npz")) for n in ("l1_2009", "l1_2019", "l2_2022", "l3_2019", "l3_2025")}
    z = d["l1_2009"]
    x0, y0 = int(z["x0"]), int(z["y0"])
    nrow, ncol = z["urb"].shape
    sg, names, cap = sigun.raster(x0, y0, nrow, ncol)
    noncap = (sg > 0) & ~np.isin(sg, list(cap))
    # cells fully covered by both L3 years and by L1 (L3 was requested for 비수도권 only)
    m = noncap & (d["l3_2019"]["cov"] >= 90) & (d["l3_2025"]["cov"] >= 90) & (d["l1_2019"]["cov"] >= 50)
    print(f"비수도권 cells {noncap.sum():,}; covered by L3 both years and L1: {m.sum():,} ({m.sum() / noncap.sum():.1%})")

    # 1) level check, same year
    rows = [["share-weighted", round(km2(d["l1_2019"]["urb"], m), 1), round(km2(d["l3_2019"]["urb"], m), 1), "", ""]]
    print("\n1) Urban area 2019, L1 vs L3 (km2) and cell agreement")
    print(f"   share-weighted: L1 {rows[0][1]:,.0f}  L3 {rows[0][2]:,.0f}")
    for t in THRESHOLDS:
        u1, u3 = (d["l1_2019"]["urb"] >= t) & m, (d["l3_2019"]["urb"] >= t) & m
        both = (u1 & u3).sum()
        rows.append([f">={t}%", round(u1.sum() * CELL_KM2, 1), round(u3.sum() * CELL_KM2, 1),
                     round(both / max(u1.sum(), 1), 3), round(both / max(u3.sum(), 1), 3)])
        print(f"   >={t}%: L1 {u1.sum() * CELL_KM2:,.0f}  L3 {u3.sum() * CELL_KM2:,.0f}  "
              f"L1-urban also L3-urban {rows[-1][3]:.0%}, L3-urban also L1-urban {rows[-1][4]:.0%}")
    write("l3_levels.csv", ["measure", "L1_2019_km2", "L3_2019_km2", "share_L1_also_L3", "share_L3_also_L1"], rows)

    # 2) L3 change by group
    rows = []
    print("\n2) L3 2019 -> 2025, 비수도권 (share-weighted km2)")
    for g in L3_GROUPS:
        a, b = km2(d["l3_2019"][g], m), km2(d["l3_2025"][g], m)
        rows.append([g, round(a, 1), round(b, 1), round(b - a, 1), round((b - a) / a * 100, 1) if a else ""])
        print(f"   {g:>5}: {a:9,.1f} -> {b:9,.1f}  ({b - a:+,.1f}, {rows[-1][4]}%)")
    for t in THRESHOLDS:
        ua, ub = (d["l3_2019"]["urb"] >= t) & m, (d["l3_2025"]["urb"] >= t) & m
        g_, l_ = (~ua & ub).sum(), (ua & ~ub).sum()
        rows.append([f"urb cells >={t}%: gained / lost / net", round(g_ * CELL_KM2, 1), round(l_ * CELL_KM2, 1), round((g_ - l_) * CELL_KM2, 1), ""])
        print(f"   urban cells >={t}%: gained {g_ * CELL_KM2:,.0f}, lost {l_ * CELL_KM2:,.0f}, net {(g_ - l_) * CELL_KM2:+,.0f} km2")
    write("l3_change.csv", ["group", "km2_2019", "km2_2025", "change_km2", "change_pct"], rows)

    # 3) use of L1 new development
    nw = m & (d["l1_2009"]["urb"] < 10) & (d["l1_2019"]["urb"] >= 50)
    rows = []
    print(f"\n3) L1 new development 2009->2019 ({nw.sum() * CELL_KM2:,.0f} km2): mean share in L3 2019 / L3 2025")
    for g in L3_GROUPS:
        rows.append([g, round(float(d["l3_2019"][g][nw].mean()), 1), round(float(d["l3_2025"][g][nw].mean()), 1)])
    for g in ["urb", "res", "ind", "com", "cul", "tra", "pub", "agr", "grs", "bar"]:
        rows.append([f"L2_2022 {g}", round(float(d["l2_2022"][g][nw].mean()), 1), ""])
    write("l3_newdev_use.csv", ["group", "L3_2019_mean_pct", "L3_2025_mean_pct"], rows)
    print("   " + ", ".join(f"{r[0]} {r[1]}/{r[2]}" for r in rows[:11]))

    # 4) 시군 change
    rows = []
    for i in sorted(names):
        if i in cap:
            continue
        mi = m & (sg == i)
        if not mi.any():
            continue
        rows.append([i, names[i]] + [round(km2(d["l3_2025"][g], mi) - km2(d["l3_2019"][g], mi), 2) for g in L3_GROUPS])
    write("l3_sigun_change.csv", ["SG_ID", "sigun"] + [f"d_{g}_km2" for g in L3_GROUPS], rows)
    print(f"\n4) 시군 table: {len(rows)} 비수도권 시군 -> {OUT}")

    # 5) new-development patches
    a, b = d["l3_2019"], d["l3_2025"]
    gain = m & (a["urb"] < 10) & (b["urb"] >= 50)
    lab, _ = ndimage.label(gain, structure=np.ones((3, 3)))
    size = np.bincount(lab.ravel())
    size[0] = 0
    patch = size[lab] >= PATCH_MIN
    n_patch = int((size >= PATCH_MIN).sum())
    print(f"\n5) New-development patches >= {PATCH_MIN} cells: {n_patch:,}, {patch.sum() * CELL_KM2:,.0f} km2 "
          f"(all gain cells {gain.sum() * CELL_KM2:,.0f} km2)")
    print("   2019 cover " + ", ".join(f"{g} {a[g][patch].mean():.1f}" for g in ("agr", "for", "grs", "bar")))
    print("   2025 use   " + ", ".join(f"{g} {b[g][patch].mean():.1f}" for g in ("road", "det", "apt", "ind", "com", "pub", "cul")))
    rows, r1, r3 = [], [], []
    for i in sorted(names):
        if i in cap:
            continue
        mi = m & (sg == i)
        if not mi.any():
            continue
        l1 = (d["l1_2019"]["urb"][mi].astype(np.int64).sum() - d["l1_2009"]["urb"][mi].astype(np.int64).sum()) / 100 * CELL_KM2
        p = patch[mi].sum() * CELL_KM2
        rows.append([i, names[i], round(p, 2), round(l1, 2)])
        r1.append(l1)
        r3.append(p)
    write("l3_patch_gain.csv", ["SG_ID", "sigun", "l3_patch_gain_2019_2025_km2", "l1_net_2009_2019_km2"], rows)
    print(f"   시군 Spearman, patch gain vs L1 2009-2019 net: {stats.spearmanr(r1, r3)[0]:.2f}")


if __name__ == "__main__":
    main()
