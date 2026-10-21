"""Fine-class (L3, 세분류) land cover shares on the SGIS 100 m national grid (EPSG:5179).

The 1:5,000 sheets are kept zipped on the NAS. They are processed per 1:50,000 block (the first
5 digits of the sheet number, about 70 sheets): the block's zips are extracted to a local scratch
folder, merged, rasterized to 10 m cells, and the 10 m subcell counts per class group are added to
national 100 m arrays. Adding is exact because the 10 m lattice is aligned to the 100 m grid and
each subcell centre falls in one polygon of one block.

Same frame, cell size and group logic as grid_lc_share.py; output data_work/grid100/l3_{year}.npz
(uint8 share %, 0-100, per group) and l3_{year}_urb.tif. Progress is checkpointed to
data_work/grid100/l3_{year}_partial.npz so an interrupted run resumes.

The source coordinate system is labelled PCS_ITRF2000_TM; its parameters equal EPSG:5186, so it
is defined as 5186 and projected to 5179 without a datum transformation.

Run with ArcGIS Pro Python:  propy.bat code\\02_grid\\grid_l3_share.py 2019   (or 2025)
"""
import os
import shutil
import sys
import tempfile
import time

import arcpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "01_landcover"))
import paths
from unzip_l3 import extract_sheets, zip_dir

sys.stdout.reconfigure(encoding="utf-8")
arcpy.env.overwriteOutput = True

SR_OUT, SR_SRC = arcpy.SpatialReference(5179), arcpy.SpatialReference(5186)
FINE, CELL = 10, 100
K = CELL // FINE
OUT = os.path.join(paths.WORK, "grid100")

# L3 code -> groups (a code may feed several groups, e.g. 112 -> urb, res, apt)
GROUPS = {
    "urb": lambda c: 100 <= c < 200,
    "res": lambda c: c in (111, 112), "det": lambda c: c == 111, "apt": lambda c: c == 112,
    "ind": lambda c: c == 121, "com": lambda c: c in (131, 132), "mix": lambda c: c == 132,
    "cul": lambda c: c == 141, "tra": lambda c: 151 <= c <= 155, "road": lambda c: c == 154,
    "pub": lambda c: 161 <= c <= 163,
    "agr": lambda c: 200 <= c < 300, "for": lambda c: 300 <= c < 400, "grs": lambda c: 400 <= c < 500,
    "wet": lambda c: 500 <= c < 600, "bar": lambda c: 600 <= c < 700, "wat": lambda c: 700 <= c < 800,
}


def frame():
    z = np.load(os.path.join(OUT, "l1_2009.npz"))
    nrow, ncol = z["urb"].shape
    return int(z["x0"]), int(z["y0"]), nrow, ncol


def merge_block(year, block, tmp):
    sheets = {f.split("_")[1] for f in os.listdir(zip_dir(year)) if f.endswith(".zip") and f.split("_")[1][:5] == block}
    shps = extract_sheets(year, os.path.join(tmp, "x"), sheets)
    gdb = os.path.join(tmp, "b.gdb")
    if not arcpy.Exists(gdb):
        arcpy.management.CreateFileGDB(tmp, "b.gdb")
    fms = arcpy.FieldMappings()
    fm = arcpy.FieldMap()
    for s in shps:
        fm.addInputField(s, "L3_CODE")
    fms.addFieldMap(fm)
    fc = os.path.join(gdb, "m")
    # the rasterization step sets outputCoordinateSystem to 5179; clear it so Merge keeps the source
    # coordinates (otherwise Merge projects to 5179 and DefineProjection then mislabels them)
    arcpy.env.outputCoordinateSystem = None
    arcpy.env.extent = None
    arcpy.management.Merge(shps, fc, fms)
    arcpy.management.DefineProjection(fc, SR_SRC)
    return fc, len(shps)


def block_counts(fc, x0, y0, ytop, tmp):
    """Rasterize the block to 10 m in EPSG:5179 over its extent snapped to the 100 m grid.
    Returns (row offset, col offset, {group: counts (r, c) uint8})."""
    ext = arcpy.Describe(fc).extent.projectAs(SR_OUT)
    xmin = int(ext.XMin // CELL * CELL)
    ymin = int(ext.YMin // CELL * CELL)
    xmax = int(-(-ext.XMax // CELL) * CELL)
    ymax = int(-(-ext.YMax // CELL) * CELL)
    arcpy.env.outputCoordinateSystem = SR_OUT
    arcpy.env.extent = arcpy.Extent(xmin, ymin, xmax, ymax)
    arcpy.env.cellSize = FINE
    ras = os.path.join(tmp, "r.tif")
    arcpy.conversion.PolygonToRaster(fc, "L3_CODE", ras, "CELL_CENTER", "", FINE)
    lut = {}
    with arcpy.da.SearchCursor(ras, ["Value", "L3_CODE"]) as cur:
        for v, code in cur:
            try:
                lut[v] = int(code)
            except (TypeError, ValueError):
                lut[v] = 0
    a = arcpy.RasterToNumPyArray(ras, arcpy.Point(xmin, ymin), (xmax - xmin) // FINE, (ymax - ymin) // FINE, nodata_to_value=0)
    m = np.zeros(int(a.max()) + 1, dtype=np.int16)
    for v, code in lut.items():
        m[v] = code
    codes = m[a]
    r, c = codes.shape[0] // K, codes.shape[1] // K
    blk = codes.reshape(r, K, c, K)
    out = {"cov": (blk > 0).sum(axis=(1, 3)).astype(np.uint8)}
    uniq = np.unique(codes)
    for g, test in GROUPS.items():
        vals = [int(u) for u in uniq if u > 0 and test(int(u))]
        out[g] = np.isin(blk, vals).sum(axis=(1, 3)).astype(np.uint8) if vals else np.zeros((r, c), np.uint8)
    return (ytop - ymax) // CELL, (xmin - x0) // CELL, out


def run(year):
    x0, y0, nrow, ncol = frame()
    ytop = y0 + nrow * CELL
    names = ["cov"] + list(GROUPS)
    part = os.path.join(OUT, f"l3_{year}_partial.npz")
    if os.path.exists(part):
        z = np.load(part, allow_pickle=True)
        acc = {g: z[g] for g in names}
        done = set(z["done"].tolist())
        print(f"resuming {year}: {len(done)} blocks already done", flush=True)
    else:
        acc = {g: np.zeros((nrow, ncol), np.uint16) for g in names}
        done = set()
    blocks = sorted({f.split("_")[1][:5] for f in os.listdir(zip_dir(year)) if f.endswith(".zip")})
    t0 = time.time()
    for i, b in enumerate(blocks, 1):
        if b in done:
            continue
        t = time.time()
        tmp = tempfile.mkdtemp(prefix=f"l3_{year}_")
        try:
            fc, n = merge_block(year, b, tmp)
            r0, c0, cnt = block_counts(fc, x0, y0, ytop, tmp)
            # blocks at the coast can reach beyond the national frame; add only the part inside it
            h, w = cnt["cov"].shape
            ra, rb = max(r0, 0), min(r0 + h, nrow)
            ca, cb = max(c0, 0), min(c0 + w, ncol)
            total = int(cnt["cov"].astype(np.int64).sum())
            added = 0
            if ra < rb and ca < cb:
                before = int(acc["cov"][ra:rb, ca:cb].astype(np.int64).sum())
                for grp, arr in cnt.items():
                    acc[grp][ra:rb, ca:cb] += arr[ra - r0:rb - r0, ca - c0:cb - c0]
                added = int(acc["cov"][ra:rb, ca:cb].astype(np.int64).sum()) - before
            if added != total:
                print(f"    block {b}: {total - added} of {total} subcells not added (outside the national frame); "
                      f"r0={r0} c0={c0} h={h} w={w} rows {ra}-{rb} cols {ca}-{cb} frame {nrow}x{ncol}", flush=True)
        finally:
            arcpy.env.extent = None
            shutil.rmtree(tmp, ignore_errors=True)
        done.add(b)
        print(f"  l3_{year} {i:3d}/{len(blocks)} block {b}: {n} sheets, urban cells {int((cnt['urb'] > 0).sum()):,}, {time.time() - t:.0f} s", flush=True)
        if len(done) % 10 == 0:
            np.savez(part, done=np.array(sorted(done)), **acc)
    over = int((acc["cov"] > 100).sum())
    if over:
        print(f"  note: {over} cells with more than 100 subcells (overlapping sheet edges), capped at 100")
    nat = {g: np.minimum(a, 100).astype(np.uint8) for g, a in acc.items()}
    np.savez_compressed(os.path.join(OUT, f"l3_{year}.npz"), x0=x0, y0=y0, cell=CELL, **nat)
    r = arcpy.NumPyArrayToRaster(nat["urb"], arcpy.Point(x0, y0), CELL, CELL)
    arcpy.management.DefineProjection(r, SR_OUT)
    r.save(os.path.join(OUT, f"l3_{year}_urb.tif"))
    if os.path.exists(part):
        os.remove(part)
    print(f"l3_{year}: done in {(time.time() - t0) / 60:.1f} min; urban area (share-weighted) "
          f"{nat['urb'].astype(np.int64).sum() / 100 * 0.01:,.0f} km2", flush=True)


if __name__ == "__main__":
    for y in sys.argv[1:] or ["2019", "2025"]:
        run(y)
