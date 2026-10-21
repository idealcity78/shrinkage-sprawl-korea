"""Zoning (용도지역, V-World 연속주제, base month 2026-10) class shares on the SGIS 100 m national grid (EPSG:5179).

Sources: data_raw/supply/vworld/shp/UQ111_{시도} (도시지역) and UQ112_{시도} (관리지역), organised by
00_data/organize_vworld_zoning.py. The zoning class is characters 21-26 of MNUM:
  res   UQA1xx 주거지역          com   UQA2xx 상업지역          ind   UQA3xx 공업지역
  gnat  UQA430 자연녹지지역       gprd  UQA420 생산녹지지역       gcon  UQA410 보전녹지지역
  uund  UQA01x, UQA500 도시지역 미세분
  mpln  UQB100 계획관리지역       mprd  UQB200 생산관리지역       mcon  UQB300 보전관리지역
  (checked against KOSIS TX_315_2009_H1443, 2024 national: 계획관리 12,085, 생산관리 5,030, 보전관리 10,211 km2;
   rasterized UQB100 12,124, UQB200 5,026, UQB300 10,114)
Cells outside both layers are 농림지역, 자연환경보전지역 or water. The layers carry no reliable designation date
(NTFDATE is empty for 75-94 % of the area; the year in MNUM is the database entry year), so this is the
zoning in force in 2026.

Each 시도 is copied to a scratch geodatabase, given an integer class field, and rasterized to 10 m in 50 km tiles
aligned to the 100 m grid; subcell counts per class are added to national arrays (overlaps between the two layers
go to whichever polygon the rasterizer keeps). The source files are EPSG:5186 (GRS80 TM 중부) and are projected
to 5179 without a datum transformation.

Output: data_work/grid100/zoning.npz (uint8 share %, 0-100, per class, plus cov)
Run with ArcGIS Pro Python:  propy.bat code\\02_grid\\grid_zoning.py
"""
import glob
import os
import shutil
import sys
import tempfile
import time

import arcpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
arcpy.env.overwriteOutput = True

SR_OUT, SR_SRC = arcpy.SpatialReference(5179), arcpy.SpatialReference(5186)
FINE, CELL, TILE = 10, 100, 50000
K = CELL // FINE
OUT = os.path.join(paths.WORK, "grid100")
SHP = os.path.join(paths.SUPPLY, "vworld", "shp")
CLASSES = ["res", "com", "ind", "gnat", "gprd", "gcon", "uund", "mpln", "mprd", "mcon"]


def zclass(mnum):
    c = (mnum or "")[20:26]
    if c.startswith("UQA1"):
        return 1
    if c.startswith("UQA2"):
        return 2
    if c.startswith("UQA3"):
        return 3
    return {"UQA430": 4, "UQA420": 5, "UQA410": 6, "UQB100": 8, "UQB200": 9, "UQB300": 10}.get(
        c, 7 if c.startswith("UQA01") or c == "UQA500" else 0)


def frame():
    z = np.load(os.path.join(OUT, "l1_2009.npz"))
    nrow, ncol = z["urb"].shape
    return int(z["x0"]), int(z["y0"]), nrow, ncol


def prepare(folder, tmp):
    shp = glob.glob(os.path.join(SHP, folder, "*.shp"))[0]
    gdb = os.path.join(tmp, "z.gdb")
    if not arcpy.Exists(gdb):
        arcpy.management.CreateFileGDB(tmp, "z.gdb")
    arcpy.env.outputCoordinateSystem = None
    arcpy.env.extent = None
    fc = os.path.join(gdb, folder.split("_")[0])
    arcpy.conversion.ExportFeatures(shp, fc)
    arcpy.management.DefineProjection(fc, SR_SRC)
    arcpy.management.AddField(fc, "ZC", "SHORT")
    n = {}
    with arcpy.da.UpdateCursor(fc, ["MNUM", "ZC"]) as cur:
        for m, _ in cur:
            z = zclass(m)
            n[z] = n.get(z, 0) + 1
            cur.updateRow([m, z])
    return fc, n


def tile_counts(fc, xmin, ymin, xmax, ymax, tmp):
    arcpy.env.outputCoordinateSystem = SR_OUT
    arcpy.env.extent = arcpy.Extent(xmin, ymin, xmax, ymax)
    arcpy.env.cellSize = FINE
    ras = os.path.join(tmp, "r.tif")
    arcpy.conversion.PolygonToRaster(fc, "ZC", ras, "CELL_CENTER", "", FINE)
    a = arcpy.RasterToNumPyArray(ras, arcpy.Point(xmin, ymin), (xmax - xmin) // FINE, (ymax - ymin) // FINE,
                                 nodata_to_value=0)
    if a.shape != ((ymax - ymin) // FINE, (xmax - xmin) // FINE):
        b = np.zeros(((ymax - ymin) // FINE, (xmax - xmin) // FINE), a.dtype)
        b[:a.shape[0], :a.shape[1]] = a
        a = b
    r, c = a.shape[0] // K, a.shape[1] // K
    blk = a.reshape(r, K, c, K)
    out = {"cov": (blk > 0).sum(axis=(1, 3)).astype(np.uint8)}
    for i, g in enumerate(CLASSES, 1):
        out[g] = (blk == i).sum(axis=(1, 3)).astype(np.uint8)
    return out


def main():
    x0, y0, nrow, ncol = frame()
    ytop = y0 + nrow * CELL
    acc = {g: np.zeros((nrow, ncol), np.uint16) for g in ["cov"] + CLASSES}
    folders = sorted(os.path.basename(d) for d in glob.glob(os.path.join(SHP, "UQ11[12]_*")))
    t0 = time.time()
    for folder in folders:
        t = time.time()
        tmp = tempfile.mkdtemp(prefix="zone_")
        try:
            fc, n = prepare(folder, tmp)
            ext = arcpy.Describe(fc).extent.projectAs(SR_OUT)
            xa, ya = int(ext.XMin // CELL * CELL), int(ext.YMin // CELL * CELL)
            xb, yb = int(-(-ext.XMax // CELL) * CELL), int(-(-ext.YMax // CELL) * CELL)
            for tx in range(xa, xb, TILE):
                for ty in range(ya, yb, TILE):
                    tx1, ty1 = min(tx + TILE, xb), min(ty + TILE, yb)
                    cnt = tile_counts(fc, tx, ty, tx1, ty1, tmp)
                    r0, c0 = (ytop - ty1) // CELL, (tx - x0) // CELL
                    h, w = cnt["cov"].shape
                    ra, rb, ca, cb = max(r0, 0), min(r0 + h, nrow), max(c0, 0), min(c0 + w, ncol)
                    if ra < rb and ca < cb:
                        for g, arr in cnt.items():
                            acc[g][ra:rb, ca:cb] += arr[ra - r0:rb - r0, ca - c0:cb - c0]
        finally:
            arcpy.env.extent = None
            shutil.rmtree(tmp, ignore_errors=True)
        print(f"  {folder}: {sum(n.values()):,} polygons, unclassified {n.get(0, 0):,}, {time.time() - t:.0f} s", flush=True)
    over = int((acc["cov"] > 100).sum())
    nat = {g: np.minimum(a, 100).astype(np.uint8) for g, a in acc.items()}
    np.savez_compressed(os.path.join(OUT, "zoning.npz"), x0=x0, y0=y0, cell=CELL, **nat)
    km2 = {g: nat[g].astype(np.int64).sum() / 100 * 0.01 for g in CLASSES}
    print(f"zoning: done in {(time.time() - t0) / 60:.1f} min; cells with overlap {over:,}; km2 "
          + ", ".join(f"{g} {v:,.0f}" for g, v in km2.items()), flush=True)


if __name__ == "__main__":
    main()
