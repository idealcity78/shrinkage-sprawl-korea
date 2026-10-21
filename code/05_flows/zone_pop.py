"""Zone, old-core and rest population per 시군 and SGIS grid year (definitions of supply_panel.py).

zone_old_rest() -> {(시군 name, year): (zone, old, rest)} for every 시군 and the grid years 2000-2024.
Cached in data_work/flows/zone_pop.csv after the first call.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "02_grid"))
import paths

GRID = os.path.join(paths.WORK, "grid100")
CACHE = os.path.join(paths.WORK, "flows", "zone_pop.csv")
YEARS = [2000, 2005, 2010, 2015, 2019, 2020, 2021, 2022, 2023, 2024]


def sgis(item, year, shape, na=2.5):
    z = np.load(os.path.join(GRID, f"sgis_{item}.npz"))
    a = np.zeros(shape[0] * shape[1], np.float32)
    v = z[f"y{year}_val"]
    a[z[f"y{year}_idx"]] = np.where(v < 0, na, v)
    return a.reshape(shape)


def build():
    import sigun
    a = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(a["x0"]), int(a["y0"])
    shape = a["urb"].shape
    sg, names, cap = sigun.raster(x0, y0, *shape)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    old = (a["urb"] >= 50) & (sgis("house", 2000, shape, na=0) >= 5) & ~zone
    lab = sg.ravel().astype(np.int64)
    k = sg.max() + 1
    rows = []
    for y in YEARS:
        p = sgis("pop", y, shape).ravel().astype(np.float64)
        z = np.bincount(lab, weights=p * zone.ravel(), minlength=k)
        o = np.bincount(lab, weights=p * old.ravel(), minlength=k)
        t = np.bincount(lab, weights=p, minlength=k)
        for i, n in names.items():
            if t[i] > 0:
                rows.append((n, y, z[i], o[i], t[i] - z[i] - o[i]))
    df = pd.DataFrame(rows, columns=["sigun", "year", "zone", "old", "rest"])
    df.to_csv(CACHE, index=False, encoding="utf-8-sig")
    return df


def zone_old_rest():
    df = pd.read_csv(CACHE, encoding="utf-8-sig") if os.path.exists(CACHE) else build()
    return {(r.sigun, int(r.year)): (r.zone, r.old, r.rest) for r in df.itertuples()}
