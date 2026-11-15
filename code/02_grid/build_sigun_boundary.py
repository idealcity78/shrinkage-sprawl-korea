"""Study 시군 boundaries from the SGIS census boundaries (읍면동, 2020 4th quarter).

Until 2026-11-15 the study used sigun_1208_2022_tm.shp, a file merged from 시도 files in 2022 whose source was not
recorded. Rasterised on the 100 m frame it left out most islands and reclaimed land (신안 lost 92% of its cells,
통영 56%, 여수 27%) and carried three capital-region polygons under the wrong name (the 과천 polygon was named 안양,
군포 was named 의왕 and 의왕 was named 과천). This script replaces it with a boundary whose source is documented.

Units are those of the study (ugm_national/sigun_id.csv plus 제주시, 서귀포시, 울릉군): 광역시 and 세종 as one unit
except 울주군 (and 군위군, a 경북 county until 2023); the 구 of a 시 are merged into the 시; 군포 is kept inside
안양, as in the registered-population series (regpop.py). The SGIS 시군구 code (first five digits of ADM_DR_CD) is
mapped to the unit by the rule in unit(); the result is written to code/02_grid/sgis2020_sgg_units.csv.

Input   data_raw/sgis/admin_boundary/bnd_dong_00_2020_4Q/bnd_dong_00_2020_4Q.shp  (SGIS request 88035, EPSG:5179)
        data_work/flows/mdis/code_year.csv, dong_xwalk.csv  (MOIS 시군구 name of each SGIS code, for the table only)
Output  data_work/boundary/sigun_sgis2020.shp  (field sigun, EPSG:5179)
        code/02_grid/sgis2020_sgg_units.csv
Run with ArcGIS Pro Python:  propy.bat code\\02_grid\\build_sigun_boundary.py
"""
import csv
import os
import sys

import arcpy
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

SRC = os.path.join(paths.RAW, "sgis", "admin_boundary", "bnd_dong_00_2020_4Q", "bnd_dong_00_2020_4Q.shp")
OUT_DIR = os.path.join(paths.WORK, "boundary")
OUT = os.path.join(OUT_DIR, "sigun_sgis2020.shp")
TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sgis2020_sgg_units.csv")
METRO = {"11": "서울특별시", "21": "부산광역시", "22": "대구광역시", "23": "인천광역시", "24": "광주광역시",
         "25": "대전광역시", "26": "울산광역시", "29": "세종시"}


def unit(code, sido, name):
    if code == "26310":
        return "울주군"
    if code[:2] in METRO:
        return METRO[code[:2]]
    if name == "고성군":
        return "강원고성군" if sido == "강원도" else "경남고성군"
    if name == "군포시":
        return "안양시"
    return name.split(" ")[0]           # 수원시 장안구 -> 수원시


def names():
    """MOIS 시도·시군구 name of each SGIS 2020 시군구 code (dominant 10-digit code of its 읍면동 in 2020)."""
    w = os.path.join(paths.WORK, "flows", "mdis")
    x = pd.read_csv(os.path.join(w, "dong_xwalk.csv"), dtype={"cd": str, "adm_cd2020": str})
    c = pd.read_csv(os.path.join(w, "code_year.csv"), dtype={"cd": str})
    x = x[x.year == 2020].merge(c[c.year == 2020][["cd", "sido", "sgg"]], on="cd")
    x["code"] = x.adm_cd2020.str[:5]
    x = x.groupby(["code", "sido", "sgg"]).cell_w.sum().reset_index().sort_values("cell_w").groupby("code").last()
    x.loc["29010", ["sido", "sgg"]] = ["세종특별자치시", "세종특별자치시"]
    return x


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with arcpy.da.SearchCursor(SRC, ["ADM_DR_CD"]) as cur:
        codes = sorted({str(c)[:5] for (c,) in cur})
    nm = names()
    rows = [(k, nm.loc[k, "sido"], nm.loc[k, "sgg"], unit(k, nm.loc[k, "sido"], nm.loc[k, "sgg"])) for k in codes]
    with open(TABLE, "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows([("sgg_cd", "sido", "sgg_nm", "sigun")] + rows)
    to_unit = {k: u for k, _, _, u in rows}

    arcpy.env.overwriteOutput = True
    tmp = arcpy.management.CopyFeatures(SRC, r"memory\dong")
    arcpy.management.AddField(tmp, "sigun", "TEXT", field_length=20)
    with arcpy.da.UpdateCursor(tmp, ["ADM_DR_CD", "sigun"]) as cur:
        for c, _ in cur:
            cur.updateRow([c, to_unit[str(c)[:5]]])
    arcpy.management.Dissolve(tmp, OUT, "sigun")
    n = int(arcpy.management.GetCount(OUT)[0])
    print(f"{len(codes)} SGIS 시군구 codes -> {n} units; written {OUT} and {TABLE}")


if __name__ == "__main__":
    main()
