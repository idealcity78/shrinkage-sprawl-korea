"""Merge the per-sheet middle-class (L2) land cover shapefiles into one feature class per map version.

Input : data_raw/landcover_mcee/L2_{year}/shp/*.shp   (one shapefile per 1:25,000 sheet)
Output: data_work/landcover_l2.gdb/lc_l2_2007, lc_l2_2022  (EPSG:5186)
        data_work/landcover_l2_area_by_class.csv        (national area by class, for checking)

Fields in the output
  sheet    1:25,000 sheet number
  l2_code  class code as published in that version
  l2_name  class name as published in that version
  lc_code  harmonized code, comparable between 2007 and 2022 (see HARMONIZE)
  lc_name  harmonized class name
  img_name, img_date  source image and date (2022 version only)

Coordinate system: the 2007 version is labelled PCS_ITRF2000_TM, whose parameters (GRS80, central
meridian 127, latitude of origin 38, false easting 200,000, false northing 600,000, scale 1.0) are
identical to Korea 2000 / Central Belt 2010 (EPSG:5186) used by the 2022 version; the same sheet's
extent agrees within 2 m. It is therefore defined as EPSG:5186 without a datum transformation.

The merge runs in a local scratch file GDB (much faster than on the NAS) and the result is copied
to data_work. Run with ArcGIS Pro Python:
    propy.bat code\\01_landcover\\merge_l2.py [2007|2022 ...]
"""
import csv
import glob
import os
import shutil
import sys
import tempfile
import time

import arcpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
arcpy.env.overwriteOutput = True

SR = arcpy.SpatialReference(5186)
OUT_GDB = os.path.join(paths.WORK, "landcover_l2.gdb")

# source field names per version
FIELDS = {
    "2007": {"sheet": "MAP_NUM", "l2_code": "LV2_CODE", "l2_name": "LV2_NAME"},
    "2022": {"sheet": "INX_NUM", "l2_code": "L2_CODE", "l2_name": "L2_NAME",
             "img_name": "IMG_NAME", "img_date": "IMG_DATE"},
}

# Classes whose codes keep the same meaning in both versions map to themselves.
# Grassland (400) and barren land (600) were reorganised between versions, so they are merged:
#   2007: 410 자연초지, 420 골프장, 430 기타초지, 610 채광지역, 620 기타나지
#   2022: 410 자연초지, 420 인공초지, 610 자연나지, 620 인공나지
LC_NAMES = {
    "110": "주거지역", "120": "공업지역", "130": "상업지역", "140": "문화·체육·휴양지역",
    "150": "교통지역", "160": "공공시설지역",
    "210": "논", "220": "밭", "230": "시설재배지", "240": "과수원", "250": "기타재배지",
    "310": "활엽수림", "320": "침엽수림", "330": "혼효림",
    "400": "초지", "510": "내륙습지", "520": "연안습지", "600": "나지",
    "710": "내륙수", "720": "해양수",
}


def harmonize(code):
    code = (code or "").strip()
    if code[:1] == "4":
        return "400"
    if code[:1] == "6":
        return "600"
    return code if code in LC_NAMES else None


def field_mappings(shps, year):
    fms = arcpy.FieldMappings()
    for out_name, src_name in FIELDS[year].items():
        fm = arcpy.FieldMap()
        for s in shps:
            fm.addInputField(s, src_name)
        of = fm.outputField
        of.name = of.aliasName = out_name
        fm.outputField = of
        fms.addFieldMap(fm)
    return fms


def merge_year(year, scratch):
    shps = sorted(glob.glob(os.path.join(paths.LANDCOVER, f"L2_{year}", "shp", "*.shp")))
    if not shps:
        raise SystemExit(f"no shapefiles for {year}")
    t = time.time()
    fc = os.path.join(scratch, f"lc_l2_{year}")
    # merge in batches so one call never holds hundreds of open shapefiles
    parts = []
    for i in range(0, len(shps), 100):
        part = os.path.join(scratch, f"part_{year}_{i // 100}")
        batch = shps[i:i + 100]
        arcpy.management.Merge(batch, part, field_mappings(batch, year))
        parts.append(part)
        print(f"  {year}: merged sheets {i + 1}-{i + len(batch)} of {len(shps)}", flush=True)
    arcpy.management.Merge(parts, fc)
    for p in parts:
        arcpy.management.Delete(p)
    if year == "2007":
        arcpy.management.DefineProjection(fc, SR)

    arcpy.management.AddField(fc, "lc_code", "TEXT", field_length=3)
    arcpy.management.AddField(fc, "lc_name", "TEXT", field_length=20)
    unknown = {}
    with arcpy.da.UpdateCursor(fc, ["l2_code", "lc_code", "lc_name"]) as cur:
        for row in cur:
            h = harmonize(row[0])
            if h is None:
                unknown[row[0]] = unknown.get(row[0], 0) + 1
            row[1], row[2] = h, LC_NAMES.get(h)
            cur.updateRow(row)
    n = int(arcpy.management.GetCount(fc)[0])
    print(f"  {year}: {len(shps)} sheets, {n:,} polygons, {time.time() - t:.0f} s; unknown codes: {unknown}", flush=True)
    return fc


def area_by_class(fc, year):
    area = {}
    with arcpy.da.SearchCursor(fc, ["lc_code", "l2_code", "l2_name", "SHAPE@AREA"]) as cur:
        for lc, code, name, a in cur:
            k = (lc, code, name)
            area[k] = area.get(k, 0.0) + a
    return [(year, lc, code, name, round(a / 1e6, 3)) for (lc, code, name), a in sorted(area.items(), key=lambda x: (x[0][0] or "", x[0][1] or ""))]


def main():
    years = sys.argv[1:] or ["2007", "2022"]
    scratch_dir = tempfile.mkdtemp(prefix="lc_l2_")
    scratch = arcpy.management.CreateFileGDB(scratch_dir, "scratch.gdb")[0]
    if not arcpy.Exists(OUT_GDB):
        arcpy.management.CreateFileGDB(paths.WORK, "landcover_l2.gdb")
    rows = []
    for year in years:
        fc = merge_year(year, scratch)
        rows += area_by_class(fc, year)
        out = os.path.join(OUT_GDB, f"lc_l2_{year}")
        arcpy.management.Copy(fc, out)
        print(f"  {year}: saved {out}", flush=True)
    csv_path = os.path.join(paths.WORK, "landcover_l2_area_by_class.csv")
    old = []
    if os.path.exists(csv_path):  # keep rows of years not rerun
        with open(csv_path, encoding="utf-8-sig") as f:
            old = [r for r in csv.reader(f)][1:]
        old = [r for r in old if r[0] not in years]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["year", "lc_code", "l2_code", "l2_name", "area_km2"])
        w.writerows(old + rows)
    print(f"area table: {csv_path}")
    shutil.rmtree(scratch_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
