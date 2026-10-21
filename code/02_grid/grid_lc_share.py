"""Land cover class shares on the SGIS 100 m national grid (EPSG:5179).

Each source is rasterized to 10 m cells inside one SGIS 100 km sheet at a time; every 100 m cell
then holds 10 x 10 subcells, and the share of a class group is the count of its subcells (0-100 %).
Working sheet by sheet keeps memory small (10,000 x 10,000 cells per sheet).

Sources
  l2_2007, l2_2022   middle-class land cover, data_work/landcover_l2.gdb (field lc_code)
  l1_1999, l1_2009, l1_2019   large-class 30 m land cover of the previous project (lc1990s, lc2000s, lc2010s;
                     imagery late 1990s, 2008-2010 and 2018-2019), values 1-7, 1 = 시가화건조지역
All are GRS80 transverse Mercator (EPSG:5186 parameters), so they are projected to EPSG:5179
without a datum transformation.

Output: data_work/grid100/{source}.npz with one uint8 array per group (share %, 0-100) on the
national 100 m frame, plus x0, y0 (lower-left corner) and cell size; and {source}_urb.tif
(urban share) for viewing.

Run with ArcGIS Pro Python:  propy.bat code\\02_grid\\grid_lc_share.py [source ...]
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
arcpy.CheckOutExtension("Spatial")

SR = arcpy.SpatialReference(5179)
FINE, CELL = 10, 100          # subcell and grid cell size (m)
K = CELL // FINE              # subcells per cell side
OUT = os.path.join(paths.WORK, "grid100")
SHEETS = sorted(glob.glob(os.path.join(paths.SGIS, "grid_boundary", "shp", "grid_*_100K.shp")))

L2_GDB = os.path.join(paths.WORK, "landcover_l2.gdb")
SOURCES = {
    "l2_2007": ("vector", os.path.join(L2_GDB, "lc_l2_2007")),
    "l2_2022": ("vector", os.path.join(L2_GDB, "lc_l2_2022")),
    "l1_1999": ("raster", os.path.join(paths.L1, "lc1990s.tif")),
    "l1_2009": ("raster", os.path.join(paths.L1, "lc2000s.tif")),
    "l1_2019": ("raster", os.path.join(paths.L1, "lc2010s.tif")),
}

# class groups -> codes (L2 harmonized lc_code as int; L1 values 1-7)
L2_GROUPS = {
    "urb": [110, 120, 130, 140, 150, 160], "res": [110], "ind": [120], "com": [130],
    "cul": [140], "tra": [150], "pub": [160],
    "agr": [210, 220, 230, 240, 250], "for": [310, 320, 330], "grs": [400],
    "wet": [510, 520], "bar": [600], "wat": [710, 720],
}
L1_GROUPS = {"urb": [1], "agr": [2], "for": [3], "grs": [4], "wet": [5], "bar": [6], "wat": [7]}


def sheet_extents():
    ext = []
    for s in SHEETS:
        e = arcpy.Describe(s).extent
        ext.append((os.path.basename(s).split("_")[1], int(e.XMin), int(e.YMin), int(e.XMax), int(e.YMax)))
    return ext


def fine_codes_vector(fc, xmin, ymin, xmax, ymax, tmp):
    """10 m class codes (int) for one sheet; 0 where there is no polygon."""
    arcpy.env.extent = arcpy.Extent(xmin, ymin, xmax, ymax)
    out = os.path.join(tmp, "v.tif")
    arcpy.conversion.PolygonToRaster(fc, "lc_code", out, "CELL_CENTER", "", FINE)
    lut = {}
    with arcpy.da.SearchCursor(out, ["Value", "lc_code"]) as cur:
        for v, code in cur:
            lut[v] = int(code) if code else 0
    a = arcpy.RasterToNumPyArray(out, arcpy.Point(xmin, ymin), (xmax - xmin) // FINE, (ymax - ymin) // FINE, nodata_to_value=0)
    m = np.zeros(int(a.max()) + 1, dtype=np.int16)
    for v, code in lut.items():
        m[v] = code
    return m[a]


SRC_CELL = 30  # L1 source cell size; projected once with cells aligned to multiples of 30 m


def prepare_raster(ras, tmp):
    """Project the national 30 m raster to EPSG:5179 once (cells aligned to the 30 m lattice from 0, 0)."""
    arcpy.env.extent = None
    out = os.path.join(tmp, "proj30.tif")
    arcpy.management.ProjectRaster(ras, out, SR, "NEAREST", SRC_CELL, "", "0 0")
    return out


def prepare_vector(fc, tmp):
    """Copy the feature class to a local file GDB (reading 8 million polygons from the NAS is slow)."""
    gdb = arcpy.management.CreateFileGDB(tmp, "src.gdb")[0]
    out = os.path.join(gdb, os.path.basename(fc))
    arcpy.management.Copy(fc, out)
    return out


def fine_codes_raster(ras, xmin, ymin, xmax, ymax, tmp):
    """10 m codes for one sheet from the pre-projected 30 m raster: each 30 m cell is split 3 x 3."""
    s, r = SRC_CELL, SRC_CELL // FINE
    xa, ya = xmin // s * s, ymin // s * s
    xb, yb = -(-xmax // s) * s, -(-ymax // s) * s
    a = arcpy.RasterToNumPyArray(ras, arcpy.Point(xa, ya), (xb - xa) // s, (yb - ya) // s, nodata_to_value=0)
    a = np.repeat(np.repeat(a.astype(np.int16), r, axis=0), r, axis=1)
    r0, c0 = (yb - ymax) // FINE, (xmin - xa) // FINE
    a = a[r0:r0 + (ymax - ymin) // FINE, c0:c0 + (xmax - xmin) // FINE]
    a[a > 7] = 0  # NoData value of the source (15)
    return a


def shares(codes, groups):
    """codes: (rows, cols) 10 m array, row 0 = north. Returns {group: (rows/K, cols/K) uint8 %}."""
    r, c = codes.shape[0] // K, codes.shape[1] // K
    blk = codes.reshape(r, K, c, K)
    out = {"cov": ((blk > 0).sum(axis=(1, 3))).astype(np.uint8)}
    for g, vals in groups.items():
        out[g] = np.isin(blk, vals).sum(axis=(1, 3)).astype(np.uint8)
    return out


def run(source):
    kind, path = SOURCES[source]
    groups = L2_GROUPS if source.startswith("l2") else L1_GROUPS
    sheets = sheet_extents()
    x0, y0 = min(s[1] for s in sheets), min(s[2] for s in sheets)
    x1, y1 = max(s[3] for s in sheets), max(s[4] for s in sheets)
    nrow, ncol = (y1 - y0) // CELL, (x1 - x0) // CELL
    nat = {g: np.zeros((nrow, ncol), np.uint8) for g in ["cov"] + list(groups)}
    tmp = tempfile.mkdtemp(prefix="g100_")
    t0 = time.time()
    path = prepare_vector(path, tmp) if kind == "vector" else prepare_raster(path, tmp)
    print(f"  {source}: source prepared in {time.time() - t0:.0f} s", flush=True)
    arcpy.env.outputCoordinateSystem = SR
    arcpy.env.cellSize = FINE
    for i, (name, xmin, ymin, xmax, ymax) in enumerate(sheets, 1):
        t = time.time()
        if kind == "vector":
            codes = fine_codes_vector(path, xmin, ymin, xmax, ymax, tmp)
        else:
            codes = fine_codes_raster(path, xmin, ymin, xmax, ymax, tmp)
        sh = shares(codes, groups)
        r0 = (y1 - ymax) // CELL  # array row 0 is the northern edge
        c0 = (xmin - x0) // CELL
        for g, a in sh.items():
            nat[g][r0:r0 + a.shape[0], c0:c0 + a.shape[1]] = a
        print(f"  {source} {i:2d}/{len(sheets)} {name}: urban cells {int((sh['urb'] > 0).sum()):,}, {time.time() - t:.0f} s", flush=True)
    os.makedirs(OUT, exist_ok=True)
    np.savez_compressed(os.path.join(OUT, f"{source}.npz"), x0=x0, y0=y0, cell=CELL, **nat)
    arcpy.env.extent = None
    r = arcpy.NumPyArrayToRaster(nat["urb"], arcpy.Point(x0, y0), CELL, CELL)
    arcpy.management.DefineProjection(r, SR)
    r.save(os.path.join(OUT, f"{source}_urb.tif"))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"{source}: done in {(time.time() - t0) / 60:.1f} min; urban area (share-weighted) "
          f"{nat['urb'].astype(np.int64).sum() / 100 * 0.01:,.0f} km2", flush=True)


if __name__ == "__main__":
    for s in sys.argv[1:] or list(SOURCES):
        run(s)
