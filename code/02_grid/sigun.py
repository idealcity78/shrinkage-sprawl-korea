"""시군 boundaries on the SGIS 100 m frame, shared by the grid scripts.

Boundaries: landcover_L1_30m_korea/sigun_1208_2022_tm.shp (2022 시군, KGD2002 TM).
Ids follow ugm_national/sigun_id.csv (SG_ID 1-159). That table leaves out 제주시, 서귀포시 and 울릉군,
which the previous model excluded; here they get ids 160 upward in name order and count as 비수도권.
Capital-region membership comes from ugm_national/sma_zone_by_city.csv (zone other than 비수도권).
"""
import csv
import os
import tempfile

import arcpy
import numpy as np

import paths

SHP = os.path.join(paths.L1, "sigun_1208_2022_tm.shp")


def ids_and_zones():
    ids, cap = {}, set()
    with open(os.path.join(paths.L1, "ugm_national", "sigun_id.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ids[r["sigun"]] = int(r["SG_ID"])
    with open(os.path.join(paths.L1, "ugm_national", "sma_zone_by_city.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["sma_zone"] != "비수도권":
                cap.add(int(r["SG_ID"]))
    with arcpy.da.SearchCursor(SHP, ["sigun"]) as cur:
        extra = sorted({n for (n,) in cur if n not in ids})
    for k, n in enumerate(extra, start=max(ids.values()) + 1):
        ids[n] = k
    return ids, cap


def raster(x0, y0, nrow, ncol):
    """(시군 id array on the frame, {id: name}, set of capital-region ids). 0 outside any 시군."""
    ids, cap = ids_and_zones()
    tmp = tempfile.mkdtemp(prefix="sg_")
    fc = os.path.join(arcpy.management.CreateFileGDB(tmp, "s.gdb")[0], "sigun")
    arcpy.env.outputCoordinateSystem = None
    arcpy.env.extent = None
    arcpy.management.Project(SHP, fc, arcpy.SpatialReference(5179))
    arcpy.management.AddField(fc, "sg_id", "SHORT")
    with arcpy.da.UpdateCursor(fc, ["sigun", "sg_id"]) as cur:
        for name, _ in cur:
            cur.updateRow([name, ids[name]])
    arcpy.env.extent = arcpy.Extent(x0, y0, x0 + ncol * 100, y0 + nrow * 100)
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(5179)
    out = os.path.join(tmp, "sg.tif")
    arcpy.conversion.PolygonToRaster(fc, "sg_id", out, "MAXIMUM_AREA", "", 100)
    a = arcpy.RasterToNumPyArray(out, arcpy.Point(x0, y0), ncol, nrow, nodata_to_value=0)
    arcpy.env.extent = None
    arcpy.env.outputCoordinateSystem = None
    return a.astype(np.int16), {v: k for k, v in ids.items()}, cap
