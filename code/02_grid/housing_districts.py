"""Housing-site development districts (택지개발지구 and similar) on the 100 m frame.

Source (read from the UGM project, not copied): ugm_national/supply_raw/housing_district, the national development
district files of 2026-09-30 (지구정보 BLS5_DSTRC_INFO, 지구단계정보 BLS5_DSTRC_MASTER, 지구경계 EPSG:5186; code
list bls_Code_Info_v1.1.xlsx). One row per district: designation number, public / private / joint, area, planned
population, planned units, designation / development-plan / implementation-plan / completion dates, governing law.

Housing districts = those under the Housing Site Development Promotion Act (택지개발촉진법), the Urban Development
Act (도시개발법), the Special Act on Public Housing (공공주택 특별법) and the Private Rental Housing Act
(민간임대주택법). Industrial, innovation-city, enterprise-city, free-economic-zone and other districts are left out
(industrial complexes and the new-city zones have their own files).

Each district polygon is put on the 100 m grid (largest-area rule, as for the industrial complexes); a cell inside
an innovation / enterprise city zone stays with the zone. The 시군 of a district is the one holding most of its
cells.

Output
  data_work/housing_district/       the three tables and the boundary, unpacked
  data_work/grid100/hd_zone.npz     district id per 100 m cell (0 = none)
  outputs/partA/hd_districts.csv    one row per housing district: attributes, cells, 시군
Run with ArcGIS Pro Python:  propy.bat code\\02_grid\\housing_districts.py
"""
import os
import sys
import tempfile
import zipfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
SRC = os.path.join(paths.L1_SUPPLY, "housing_district")
DST = os.path.join(paths.WORK, "housing_district")
OUT = os.path.join(paths.OUTPUTS, "partA")
ZIPS = ["지구정보_전국_20260930.zip", "지구단계정보_전국_20260930.zip", "지구경계_전국_20260930_5186.zip"]
LAWS = {"택지개발촉진법": "taekji", "도시개발법": "urbandev", "공공주택 특별법": "public", "민간임대주택법": "rental"}
DATES = {"지구지정일자": "desig", "개발계획승인일자": "devplan", "실시계획승인일자": "implplan", "준공일자": "done"}


def unpack():
    os.makedirs(DST, exist_ok=True)
    for zname in ZIPS:
        with zipfile.ZipFile(os.path.join(SRC, zname)) as z:
            for i in z.infolist():
                n = i.filename if i.flag_bits & 0x800 else i.filename.encode("cp437").decode("cp949")
                with open(os.path.join(DST, os.path.basename(n)), "wb") as fh:
                    fh.write(z.read(i))


def table():
    info = pd.read_csv(os.path.join(DST, "BLS5_DSTRC_INFO.csv"), encoding="cp949", dtype=str)
    mast = pd.read_csv(os.path.join(DST, "BLS5_DSTRC_MASTER.csv"), encoding="cp949", dtype=str)
    t = info.merge(mast[["지구지정번호", "법령코드명1", "단계코드명"]], on="지구지정번호", how="left")
    t = t[t["법령코드명1"].isin(LAWS)].copy()
    out = pd.DataFrame({"code": t["지구지정번호"], "name": t["지구명"], "law": t["법령코드명1"].map(LAWS),
                        "owner": t["택지구분코드명"], "stage": t["단계코드명"], "location": t["위치명"],
                        "area_km2": pd.to_numeric(t["면적"], errors="coerce") / 1e6,
                        "plan_pop": pd.to_numeric(t["계획인구수"], errors="coerce"),
                        "plan_units": pd.to_numeric(t["건설호수"], errors="coerce")})
    for c, n in DATES.items():
        d = pd.to_datetime(t[c], format="%Y%m%d", errors="coerce")
        out[f"{n}_yr"] = d.dt.year.values
    # a district designated before the oldest recorded step keeps the earliest date it has
    out["start_yr"] = out[["desig_yr", "devplan_yr", "implplan_yr"]].min(axis=1)
    return out.reset_index(drop=True)


def rasterize(t, x0, y0, nrow, ncol):
    import arcpy
    tmp = tempfile.mkdtemp(prefix="hd_")
    fc = os.path.join(arcpy.management.CreateFileGDB(tmp, "h.gdb")[0], "hd")
    arcpy.env.outputCoordinateSystem = None
    arcpy.env.extent = None
    arcpy.management.Project(os.path.join(DST, "the_geom.shp"), fc, arcpy.SpatialReference(5179))
    arcpy.management.AddField(fc, "hid", "LONG")
    ids = dict(zip(t.code, t.index + 1))
    poly = {}
    with arcpy.da.UpdateCursor(fc, ["zoneCode", "SHAPE@AREA", "hid"]) as cur:
        for code, area, _ in cur:
            hid = ids.get(code, 0)
            if hid:
                poly[hid] = poly.get(hid, 0) + area / 1e6
            cur.updateRow([code, area, hid])
    arcpy.env.extent = arcpy.Extent(x0, y0, x0 + ncol * 100, y0 + nrow * 100)
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(5179)
    lyr = arcpy.management.MakeFeatureLayer(fc, "hd_lyr", "hid > 0")
    out = os.path.join(tmp, "h.tif")
    arcpy.conversion.PolygonToRaster(lyr, "hid", out, "MAXIMUM_AREA", "", 100)
    a = arcpy.RasterToNumPyArray(out, arcpy.Point(x0, y0), ncol, nrow, nodata_to_value=0)
    arcpy.env.extent = None
    arcpy.env.outputCoordinateSystem = None
    return a.astype(np.int32), poly


def main():
    import sigun
    unpack()
    t = table()
    b = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(b["x0"]), int(b["y0"])
    nrow, ncol = b["urb"].shape
    hid, poly = rasterize(t, x0, y0, nrow, ncol)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    hid[zone] = 0
    np.savez_compressed(os.path.join(GRID, "hd_zone.npz"), hid=hid, x0=x0, y0=y0, cell=100)
    t.insert(0, "hid", t.index + 1)
    t["poly_km2"] = t.hid.map(poly)
    lab = hid.ravel().astype(np.int64)
    t["cells"] = np.bincount(lab, minlength=len(t) + 1)[1:]
    sg, names, cap = sigun.raster(x0, y0, nrow, ncol)
    m = lab > 0
    pair = pd.DataFrame({"hid": lab[m], "SG_ID": sg.ravel()[m]})
    top = pair.groupby(["hid", "SG_ID"]).size().reset_index(name="c").sort_values("c").groupby("hid").tail(1)
    t = t.merge(top[["hid", "SG_ID"]], on="hid", how="left")
    t["sigun"] = t.SG_ID.map(names)
    t["capital"] = t.SG_ID.isin(cap).astype(int)
    t.to_csv(os.path.join(OUT, "hd_districts.csv"), index=False, encoding="utf-8-sig")
    print(f"주택 지구 {len(t)}개 (경계 있음 {t.poly_km2.notna().sum()}, 격자 셀 있음 {(t.cells > 0).sum()}), "
          f"비수도권 {(t.capital == 0).sum()}개")
    print(t.groupby(["law", "capital"]).agg(n=("hid", "size"), km2=("area_km2", "sum"), cells=("cells", "sum"),
                                             units=("plan_units", "sum")).round(1).to_string())


if __name__ == "__main__":
    main()
