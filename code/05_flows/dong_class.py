"""Classify 행정동 (읍면동) by how much of their population lives in the old core or in a new-city zone.

Boundaries: SGIS 행정동 2020 4Q (data_raw/sgis/admin_boundary). Rasterised onto the 100 m frame; each cell
goes to the 동 that covers most of it. Per 동, from the SGIS grid (suppressed cells = 2.5):
  pop2015, pop2024            total population
  old_share                   share of 2024 population on 기성시가지 cells (supply_panel.py definition:
                              L1 2009 urban >= 50 % with >= 5 housing units in 2000, outside the zones)
  zone_share                  share of 2024 population inside innovation / enterprise city zones
  cls                         old (old_share >= 0.6), zone (zone_share >= 0.5), other
Each 동 is also given the 시군 (frame id) holding most of its cells, to match API names.

Output: data_work/flows/dong_class.csv
Run with ArcGIS Pro Python:  propy.bat code\\05_flows\\dong_class.py
"""
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
OUT = os.path.join(paths.WORK, "flows")
DONG = os.path.join(paths.SGIS, "admin_boundary", "bnd_dong_00_2020_4Q", "bnd_dong_00_2020_4Q.shp")
OLD_MIN, ZONE_MIN = 0.6, 0.5


def sgis(item, year, shape, na=2.5):
    z = np.load(os.path.join(GRID, f"sgis_{item}.npz"))
    a = np.zeros(shape[0] * shape[1], np.float32)
    v = z[f"y{year}_val"]
    a[z[f"y{year}_idx"]] = np.where(v < 0, na, v)
    return a.reshape(shape)


def dong_raster(x0, y0, nrow, ncol):
    tmp = tempfile.mkdtemp(prefix="dong_")
    fc = os.path.join(arcpy.management.CreateFileGDB(tmp, "d.gdb")[0], "dong")
    arcpy.env.outputCoordinateSystem = None
    arcpy.env.extent = None
    arcpy.management.Project(DONG, fc, arcpy.SpatialReference(5179))
    arcpy.management.AddField(fc, "did", "LONG")
    codes = []
    with arcpy.da.UpdateCursor(fc, ["ADM_DR_CD", "ADM_DR_NM", "did"]) as cur:
        for cd, nm, _ in cur:
            codes.append((cd, nm))
            cur.updateRow([cd, nm, len(codes)])
    arcpy.env.extent = arcpy.Extent(x0, y0, x0 + ncol * 100, y0 + nrow * 100)
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(5179)
    out = os.path.join(tmp, "d.tif")
    arcpy.conversion.PolygonToRaster(fc, "did", out, "MAXIMUM_AREA", "", 100)
    a = arcpy.RasterToNumPyArray(out, arcpy.Point(x0, y0), ncol, nrow, nodata_to_value=0)
    arcpy.env.extent = None
    arcpy.env.outputCoordinateSystem = None
    return a.astype(np.int32), codes


def main():
    os.makedirs(OUT, exist_ok=True)
    a = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(a["x0"]), int(a["y0"])
    shape = a["urb"].shape
    sg, names, cap = sigun.raster(x0, y0, *shape)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    old = (a["urb"] >= 50) & (sgis("house", 2000, shape, na=0) >= 5) & ~zone
    did, codes = dong_raster(x0, y0, *shape)
    lab = did.ravel().astype(np.int64)
    k = len(codes) + 1

    def by(v, m=None):
        w = v.ravel().astype(np.float64)
        if m is not None:
            w = w * m.ravel()
        return np.bincount(lab, weights=w, minlength=k)

    p15, p24 = sgis("pop", 2015, shape), sgis("pop", 2024, shape)
    P15, P24, O24, Z24 = by(p15), by(p24), by(p24, old), by(p24, zone)
    cells = np.bincount(lab, minlength=k)
    # 시군 holding most cells of each 동
    pair = lab * 1000 + sg.ravel().astype(np.int64)
    u, n = np.unique(pair[lab > 0], return_counts=True)
    best = {}
    for p, c in zip(u, n):
        d, s = divmod(int(p), 1000)
        if s and c > best.get(d, (0, 0))[1]:
            best[d] = (s, c)
    rows = []
    for i, (cd, nm) in enumerate(codes, start=1):
        s = best.get(i, (0, 0))[0]
        os_ = O24[i] / P24[i] if P24[i] else 0
        zs = Z24[i] / P24[i] if P24[i] else 0
        rows.append(dict(adm_cd=cd, dong=nm, SG_ID=s, sigun=names.get(s, ""), capital=int(s in cap),
                         cells=int(cells[i]), pop2015=round(P15[i]), pop2024=round(P24[i]),
                         old_share=round(os_, 3), zone_share=round(zs, 3),
                         cls="zone" if zs >= ZONE_MIN else "old" if os_ >= OLD_MIN else "other"))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "dong_class.csv"), index=False, encoding="utf-8-sig")
    nc = df[(df.capital == 0) & (df.SG_ID > 0)]
    print(f"행정동 {len(df):,}, 비수도권 {len(nc):,}")
    print(nc.groupby("cls").agg(n=("dong", "size"), pop2024=("pop2024", "sum")).to_string())
    print(nc[nc.cls == "zone"][["sigun", "dong", "pop2024", "zone_share", "old_share"]].to_string())


if __name__ == "__main__":
    main()
