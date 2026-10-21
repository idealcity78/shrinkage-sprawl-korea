"""Check the SGIS grid statistics against the land cover grid, 비수도권.

1. Placement: share of population and businesses that falls on L1 urban cells (should be high).
2. Suppressed (N/A) cells by area type: 기성시가지 (L1 2009 urban >= 50 %), L1 new development
   (2009 < 10 %, 2019 >= 50 %), other cells. Suppressed cells are counted at 2.5 (midpoint of 1-4).
3. Population, households, housing and businesses by area type over the years.

Inputs : data_work/grid100/{l1_2009, l1_2019}.npz, sgis_{pop, hh, house, biz, emp}.npz
Output : outputs/grid100_check/sgis_by_area.csv

Run with ArcGIS Pro Python:  propy.bat code\\02_grid\\check_sgis.py
"""
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
import sigun

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "grid100_check")
ITEMS = ["pop", "hh", "house", "biz", "emp"]
NA_VALUE = 2.5


def dense(z, year, n):
    a = np.zeros(n, np.float32)
    na = np.zeros(n, bool)
    idx, val = z[f"y{year}_idx"], z[f"y{year}_val"]
    a[idx] = np.where(val < 0, NA_VALUE, val)
    na[idx] = val < 0
    return a, na


def main():
    os.makedirs(OUT, exist_ok=True)
    l1a, l1b = np.load(os.path.join(GRID, "l1_2009.npz")), np.load(os.path.join(GRID, "l1_2019.npz"))
    x0, y0 = int(l1a["x0"]), int(l1a["y0"])
    nrow, ncol = l1a["urb"].shape
    sg, _, cap = sigun.raster(x0, y0, nrow, ncol)
    noncap = ((sg > 0) & ~np.isin(sg, list(cap))).ravel()
    u09, u19 = l1a["urb"].ravel(), l1b["urb"].ravel()
    areas = {
        "기성시가지": noncap & (u09 >= 50),
        "신규시가지": noncap & (u09 < 10) & (u19 >= 50),
        "그 외": noncap & ~(u09 >= 50) & ~((u09 < 10) & (u19 >= 50)),
    }
    n = nrow * ncol
    rows = []
    for item in ITEMS:
        z = np.load(os.path.join(GRID, f"sgis_{item}.npz"))
        years = sorted(int(k[1:5]) for k in z.files if k.endswith("_idx"))
        for year in years:
            a, na = dense(z, year, n)
            tot = a[noncap].sum()
            if year in (2010, 2019, 2024):
                on_urban = a[noncap & (u19 >= 50)].sum() / tot
                print(f"{item} {year}: 비수도권 {tot:,.0f}, on L1 2019 urban cells {on_urban:.0%}")
            for name, m in areas.items():
                cells = (a[m] > 0).sum()
                rows.append([item, year, name, round(float(a[m].sum())), int(cells), int(na[m].sum()),
                             round(float(na[m].sum() / max(cells, 1)), 3), round(float(a[m].sum() / tot), 3)])
    with open(os.path.join(OUT, "sgis_by_area.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["item", "year", "area", "total", "cells", "suppressed_cells", "suppressed_share", "share_of_noncap"])
        w.writerows(rows)
    print("\nitem year area total cells suppressed_share share_of_noncap")
    for r in rows:
        if r[1] in (2000, 2010, 2015, 2019, 2024):
            print(f"{r[0]:>5} {r[1]} {r[2]:<6} {r[3]:>12,} {r[4]:>9,} {r[6]:6.1%} {r[7]:6.1%}")


if __name__ == "__main__":
    main()
