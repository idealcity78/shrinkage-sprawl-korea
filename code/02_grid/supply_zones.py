"""Innovation and enterprise city zones on the 100 m frame.

Sources
  V-World 연속주제 (국토교통부, 2026-10, EPSG:5186): UB811 혁신도시개발예정지구, UB601 기업도시, UB611 기업도시
  개발구역. Current-vintage files only (old 시도 names 강원/전남 are earlier copies of the same polygons).
  Missing from the 개발예정지구 layer (lifted after completion): 울산우정, 전북 전주·완주, 제주서귀포, 부산대연,
  부산문현. The first three are taken from V-World UQ161 지구단위계획구역(현황) (dsId 30115), which has no names;
  polygons were chosen by location, registration date and area against the designated area (PRESENT_SN in UQ161).
  If a polygon is not found, the zone falls back to the L1 new-development patches (2009 < 10 % -> 2019 >= 50 %)
  near a point inside the zone. Busan 대연 and 문현 (0.17 and 0.11 km2, redevelopment inside the existing city)
  are left out.

Output
  data_work/supply_zones.gdb/zones        polygons (V-World) with zone name, type, 시군, designation date, source
  data_work/grid100/newcity_zone.npz      zone id per 100 m cell (0 = none), names, types
  outputs/partA/newcity_zones.csv         zone area on the grid against the designated area
Run with ArcGIS Pro Python:  propy.bat code\\02_grid\\supply_zones.py
"""
import csv
import glob
import os
import sys
import tempfile

import arcpy
import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
VW = os.path.join(paths.SUPPLY, "vworld", "shp")
DESIG = os.path.join(paths.L1_SUPPLY, "new_city_gosi", "new_city_designations.csv")
CURRENT = ["UB811_강원특별자치도", "UB811_경남", "UB811_경북", "UB811_대구", "UB811_부산", "UB811_전남광주통합특별시",
           "UB811_충북", "UB601_충남", "UB611_강원특별자치도", "UB611_전남광주통합특별시", "UB611_충북"]
# (layer prefix, 시군구 code, rule on area km2) -> zone name in new_city_designations.csv
NAMES = [
    ("UB811", "51130", None, "강원원주 혁신도시"), ("UB811", "48170", None, "경남진주 혁신도시"),
    ("UB811", "47150", None, "경북김천 혁신도시"), ("UB811", "27140", None, "대구신서 혁신도시"),
    ("UB811", "26200", None, "부산동삼 혁신도시"), ("UB811", "26350", None, "부산센텀 혁신도시"),
    ("UB811", "12170", None, "광주·전남 공동혁신도시"), ("UB811", "43750", None, "충북 진천·음성 혁신도시"),
    ("UB811", "43770", None, "충북 진천·음성 혁신도시"), ("UB601", "44825", None, "태안 관광레저형 기업도시"),
    ("UB611", "51130", None, "원주 지식기반형 기업도시"), ("UB611", "43130", None, "충주 지식기반형 기업도시"),
    ("UB611", "12790", None, "영암·해남 기업도시 구성지구"),
    ("UB611", "12800", lambda a: a > 6, "영암·해남 기업도시 삼호지구"),
    ("UB611", "12800", lambda a: a <= 6, "영암·해남 기업도시 삼포지구"),
]
UQ161 = os.path.join(VW, "UQ161_전국", "C_UQ161.shp")
UQ161_ZONES = {  # 지구단위계획구역 polygons (PRESENT_SN) making up each zone
    "울산우정 혁신도시": ["31110UQ161PS200709031000"],                                   # 2.99 km2, registered 2007-09
    "전북 전주·완주 혁신도시": ["45110UQ161PS201610060094", "45710UQ161PS202210300002"],  # 전주 3.32 + 완주 6.72 km2
    "제주서귀포 혁신도시": ["50000UQ161PS201704100121"],                                  # 1.15 km2
}
# fallback: point inside the zone (WGS84 lon, lat)
APPROX = {"울산우정 혁신도시": (129.300, 35.565), "전북 전주·완주 혁신도시": (127.062, 35.835),
          "제주서귀포 혁신도시": (126.515, 33.258)}


def designations():
    out = {}
    with open(DESIG, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["type"] in ("innovation", "enterprise"):
                out[r["name"]] = r
    return out


def name_of(layer, code, area):
    for p, c, rule, n in NAMES:
        if layer.startswith(p) and code == c and (rule is None or rule(area)):
            return n
    return None


def main():
    des = designations()
    z = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(z["x0"]), int(z["y0"])
    nrow, ncol = z["urb"].shape
    ytop = y0 + nrow * 100
    gdb = os.path.join(paths.WORK, "supply_zones.gdb")
    if not arcpy.Exists(gdb):
        arcpy.management.CreateFileGDB(paths.WORK, "supply_zones.gdb")
    arcpy.env.overwriteOutput = True
    fc = os.path.join(gdb, "zones")
    sr = arcpy.SpatialReference(5179)
    arcpy.management.CreateFeatureclass(gdb, "zones", "POLYGON", spatial_reference=sr)
    for fld, t in (("zone", "TEXT"), ("ztype", "TEXT"), ("sigun", "TEXT"), ("designated", "TEXT"), ("source", "TEXT"), ("zid", "SHORT")):
        arcpy.management.AddField(fc, fld, t)
    names = sorted(des)
    zid = {n: i + 1 for i, n in enumerate(names)}
    with arcpy.da.InsertCursor(fc, ["SHAPE@", "zone", "ztype", "sigun", "designated", "source", "zid"]) as ins:
        for layer in CURRENT:
            for shp in glob.glob(os.path.join(VW, layer, "*.shp")):
                with arcpy.da.SearchCursor(shp, ["SHAPE@", "COL_ADM_SE"]) as cur:
                    for g, code in cur:
                        n = name_of(layer, str(code), g.area / 1e6)
                        if n is None:
                            print("unmatched", layer, code, round(g.area / 1e6, 2))
                            continue
                        d = des[n]
                        ins.insertRow([g.projectAs(sr), n, d["type"], d["sigun_model"], d["designated"],
                                       f"V-World {layer.split('_')[0]}", zid[n]])
        want = {sn: n for n, sns in UQ161_ZONES.items() for sn in sns}
        with arcpy.da.SearchCursor(UQ161, ["SHAPE@", "PRESENT_SN"]) as cur:
            for g, sn in cur:
                if sn in want:
                    n = want.pop(sn)
                    d = des[n]
                    ins.insertRow([g.projectAs(sr), n, d["type"], d["sigun_model"], d["designated"],
                                   "V-World UQ161 지구단위계획구역", zid[n]])
        for sn, n in want.items():
            print("UQ161 polygon not found:", n, sn)

    # rasterise V-World zones (cell centre)
    tmp = tempfile.mkdtemp(prefix="zn_")
    arcpy.env.extent = arcpy.Extent(x0, y0, x0 + ncol * 100, y0 + nrow * 100)
    arcpy.env.outputCoordinateSystem = sr
    r = os.path.join(tmp, "z.tif")
    arcpy.conversion.PolygonToRaster(fc, "zid", r, "MAXIMUM_AREA", "", 100)
    zone = arcpy.RasterToNumPyArray(r, arcpy.Point(x0, y0), ncol, nrow, nodata_to_value=0).astype(np.int16)
    arcpy.env.extent = None
    arcpy.env.outputCoordinateSystem = None

    # approximate missing zones from L1 new-development patches
    b = np.load(os.path.join(GRID, "l1_2019.npz"))
    new = (z["urb"] < 10) & (b["urb"] >= 50)
    lab, _ = ndimage.label(new, structure=np.ones((3, 3)))
    rr, cc = np.indices((nrow, ncol), sparse=True)
    source = {n: ("V-World UQ161 지구단위계획구역" if n in UQ161_ZONES else "V-World") for n in names if (zone == zid[n]).any()}
    for n, (lon, lat) in APPROX.items():
        if n in source:
            continue
        p = arcpy.PointGeometry(arcpy.Point(lon, lat), arcpy.SpatialReference(4326)).projectAs(sr).firstPoint
        r0, c0 = int((ytop - p.Y) // 100), int((p.X - x0) // 100)
        area = float(des[n]["area_m2"]) / 1e6
        rad = 1.5 * np.sqrt(area / np.pi) * 10  # cells
        win = np.s_[max(r0 - 60, 0):r0 + 61, max(c0 - 60, 0):c0 + 61]
        lw = lab[win]
        ids = np.unique(lw[lw > 0])
        if not len(ids):
            print("no patch near", n)
            continue
        dist = ndimage.distance_transform_edt(lw == 0)
        # patch whose nearest cell is closest to the point, then all patches within the radius
        ri, ci = r0 - win[0].start, c0 - win[1].start
        near = (np.hypot(*np.indices(lw.shape) - np.array([[[ri]], [[ci]]])) <= rad) & (lw > 0)
        keep = np.isin(lab, np.unique(lw[near])) & (np.hypot(rr - r0, cc - c0) <= rad)
        zone[keep & (zone == 0)] = zid[n]
        source[n] = f"근사 (대분류 신규개발 덩어리, 반경 {rad / 10:.1f} km)"
    np.savez_compressed(os.path.join(GRID, "newcity_zone.npz"), zone=zone, x0=x0, y0=y0, cell=100,
                        names=np.array(names), types=np.array([des[n]["type"] for n in names]))

    rows = []
    for n in names:
        cells = int((zone == zid[n]).sum())
        a = float(des[n]["area_m2"]) / 1e6
        rows.append([zid[n], n, des[n]["type"], des[n]["sigun_model"], des[n]["designated"], round(a, 3),
                     round(cells * 0.01, 2), round(cells * 0.01 / a, 2) if a else "", source.get(n, "없음")])
        print(f"{n:<24} 고시 {a:6.2f} km2  격자 {cells * 0.01:6.2f} km2  {source.get(n, '없음')}")
    os.makedirs(os.path.join(paths.OUTPUTS, "partA"), exist_ok=True)
    with open(os.path.join(paths.OUTPUTS, "partA", "newcity_zones.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["zid", "zone", "type", "sigun", "designated", "area_gosi_km2", "area_grid_km2", "ratio", "source"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
