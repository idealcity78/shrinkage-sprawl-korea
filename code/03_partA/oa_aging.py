"""Aging of 기성시가지 from census-block (집계구) age tables, 2000-2024, by 시군.

Each 집계구 (2025 Q2 boundaries) is placed at an inside point on the 100 m frame. A 집계구 is 기성시가지 when
that cell is L1 2009 urban >= 50 %; its 시군 is the cell's 시군. Age items (성연령별인구):
in_age_001-021 total by 5-year band (0-4 ... 100+), 031-051 male, 061-081 female. N/A cells are set to 2.

Per 시군 and area type (기성시가지 / other) and year: population, 65+ share, women 20-39 and the
extinction-risk index (women 20-39 / 65+).

Output: outputs/partA/oa_aging_by_sigun.csv (long), outputs/partA/oa_aging_wide.csv (one row per 시군)
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\oa_aging.py
"""
import csv
import os
import sys
import tempfile

import arcpy
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "02_grid"))
import paths
import sigun

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partA")
OA = os.path.join(paths.SGIS, "oa_stats", "bnd_oa_00_2025_2Q", "bnd_oa_00_2025_2Q.shp")
CSV = os.path.join(paths.SGIS, "oa_stats", "csv", "2025년기준_{}년_성연령별인구.csv")
YEARS = [2000, 2005, 2010, 2015, 2019, 2020, 2022, 2024]
TOTAL = [f"in_age_{i:03d}" for i in range(1, 22)]
OLD65 = [f"in_age_{i:03d}" for i in range(14, 22)]
F2039 = [f"in_age_{i:03d}" for i in range(65, 69)]
NA_VALUE = 2


def oa_cells(x0, y0, nrow, ncol):
    tmp = tempfile.mkdtemp(prefix="oa_")
    pts = os.path.join(arcpy.management.CreateFileGDB(tmp, "o.gdb")[0], "pts")
    arcpy.env.outputCoordinateSystem = None
    arcpy.env.extent = None
    arcpy.management.FeatureToPoint(OA, pts, "INSIDE")
    ytop = y0 + nrow * 100
    out = {}
    with arcpy.da.SearchCursor(pts, ["TOT_OA_CD", "SHAPE@XY"]) as cur:
        for code, (x, y) in cur:
            r, c = int((ytop - y) // 100), int((x - x0) // 100)
            if 0 <= r < nrow and 0 <= c < ncol:
                out[code] = (r, c)
    return out


def read_age(year):
    tot, o65, f = {}, {}, {}
    with open(CSV.format(year), encoding="cp949") as fh:
        for line in fh:
            p = line.rstrip("\n").split(",")
            if len(p) < 4:
                continue
            code, item, v = p[1], p[2], p[3]
            v = NA_VALUE if not v.isdigit() else int(v)
            if item in TOTAL:
                tot[code] = tot.get(code, 0) + v
                if item in OLD65:
                    o65[code] = o65.get(code, 0) + v
            elif item in F2039:
                f[code] = f.get(code, 0) + v
    return tot, o65, f


def main():
    os.makedirs(OUT, exist_ok=True)
    l1 = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(l1["x0"]), int(l1["y0"])
    nrow, ncol = l1["urb"].shape
    sg, names, cap = sigun.raster(x0, y0, nrow, ncol)
    old = l1["urb"] >= 50
    cells = oa_cells(x0, y0, nrow, ncol)
    meta = {k: (int(sg[r, c]), bool(old[r, c])) for k, (r, c) in cells.items()}
    n_old = sum(1 for s, o in meta.values() if o and s and s not in cap)
    print(f"집계구 placed: {len(meta):,}; 비수도권 기성시가지 집계구 {n_old:,}")

    rows = []
    for year in YEARS:
        tot, o65, f = read_age(year)
        acc = {}
        miss = 0
        for code, t in tot.items():
            if code not in meta:
                miss += 1
                continue
            s, o = meta[code]
            if not s or s in cap:
                continue
            a = acc.setdefault((s, "old" if o else "other"), [0, 0, 0])
            a[0] += t
            a[1] += o65.get(code, 0)
            a[2] += f.get(code, 0)
        print(f"{year}: {len(tot):,} 집계구 in table, {miss:,} not placed")
        for (s, area), (t, o, w) in acc.items():
            rows.append([s, names[s], year, area, t, o, w, o / t if t else None, w / o if o else None])
    d = pd.DataFrame(rows, columns=["SG_ID", "sigun", "year", "area", "pop", "p65", "f2039", "share65", "er"])
    d.sort_values(["SG_ID", "year", "area"]).to_csv(os.path.join(OUT, "oa_aging_by_sigun.csv"), index=False, encoding="utf-8-sig")
    w = d.pivot_table(index=["SG_ID", "sigun"], columns=["area", "year"], values=["share65", "er", "pop"])
    w.columns = [f"{a}_{v}_{y}" for v, a, y in w.columns]
    w.reset_index().to_csv(os.path.join(OUT, "oa_aging_wide.csv"), index=False, encoding="utf-8-sig")
    s = d.groupby(["year", "area"])[["pop", "p65", "f2039"]].sum()
    s["share65"] = s.p65 / s["pop"]
    s["er"] = s.f2039 / s.p65
    print(s.round(3).to_string())


if __name__ == "__main__":
    main()
