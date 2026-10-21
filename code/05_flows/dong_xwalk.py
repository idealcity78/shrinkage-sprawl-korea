"""Crosswalk the 10-digit 읍면동 codes of the MDIS migration data (2001-2025) to places on the 100 m grid.

Every code that appears in moves_mdis.sqlite in a year is given the 읍면동 boundary valid in that year and is
rasterised onto the 100 m frame. Through the grid each code-year is then
  * classified like dong_class.py (share of population on 기성시가지 cells / in new-city zones), and
  * split over the SGIS 2020 행정동 used elsewhere in the study, with population weights.
Dongs that were split, merged or renamed between 2001 and 2025 can therefore be followed as the same ground.

Inputs
  data_raw/admin_codes/mois_jscode20261012/   행정안전부 KIKcd_H (말소코드 포함): 행정동코드, 시도·시군구·읍면동명,
                                              생성일자, 말소일자 for every code since 1988
  data_raw/admin_boundary/admdongkor/         vuski/admdongkor 읍면동 boundaries (EPSG:5179) with the 10-digit code
                                              (emdcd), one snapshot per year end plus a few mid-year ones
  data_work/flows/mdis/moves_mdis.sqlite      codes seen per year (flows_dong)
  data_work/grid100                           frame, SGIS population grid, 기성시가지 and zone masks
Boundary choice (match): 'year' = the snapshot of that year end holds the code; 'near' = the code is only in a
neighbouring snapshot (created or abolished during the year); 'name' = the boundary file numbers this 읍면동
differently in early years (제주 before 2006, 수원 before 2003 ...), matched by 시도·시군구·읍면동 name in the
snapshot nearest the year end; 'none' = no boundary (출장소·지소 and a few short-lived codes).
Population weights use the SGIS grid year nearest to the MDIS year (2000, 2005, 2010, 2015, 2019-2024).

Outputs (data_work/flows/mdis/)
  code_year.csv   year, cd, sido, sgg, emd, created, abolished, snap, match, cells, pop, old_share, zone_share, cls,
                  SG_ID, sigun, capital
  dong_xwalk.csv  year, cd, adm_cd2020, pop_w, cell_w   (weights sum to 1 over adm_cd2020 for each year and cd)

Run with ArcGIS Pro Python:  propy.bat code\\05_flows\\dong_xwalk.py
"""
import glob
import os
import re
import sqlite3
import sys
import tempfile
from datetime import date

import arcpy
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "02_grid"))
sys.path.insert(0, HERE)
import paths
import sigun
from dong_class import OLD_MIN, ZONE_MIN, dong_raster, sgis

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
MDIS = os.path.join(paths.WORK, "flows", "mdis")
KIK = glob.glob(os.path.join(paths.RAW, "admin_codes", "mois_jscode*", "extract", "*", "KIKcd_H*.xlsx"))
ADK = os.path.join(paths.RAW, "admin_boundary", "admdongkor")
POP_YEARS = [2000, 2005, 2010, 2015, 2019, 2020, 2021, 2022, 2023, 2024]


def names():
    if len(KIK) != 1:
        raise SystemExit(f"expected one KIKcd_H xlsx, found {KIK}")
    h = pd.read_excel(KIK[0], dtype=str)
    h.columns = ["cd", "sido", "sgg", "emd", "created", "abolished"]
    return h.set_index("cd")


def snapshots():
    s = {}
    for f in sorted(glob.glob(os.path.join(ADK, "emd_*.parquet"))):
        d = os.path.basename(f)[4:12]
        s[d] = f
    return s


SIDO_NOW = {"42": "51", "45": "52", "49": "50"}


def key(sido_cd, sgg, emd):
    """Name key for codes that the boundary file numbers differently: 시도 code (current) + 시군구 + 읍면동 name,
    without spaces and punctuation (칠금.금능동 = 칠금·금능동, 수원시 권선구 = 수원시권선구)."""
    norm = lambda s: re.sub(r"[\s.·・,()]", "", str(s or ""))
    return SIDO_NOW.get(sido_cd, sido_cd) + "|" + norm(sgg) + "|" + norm(emd)


def snap_raster(f, x0, y0, nrow, ncol):
    """Rasterise one admdongkor snapshot; return (label array, list of codes by label - 1, name keys by label - 1)."""
    t = pq.read_table(f, columns=["emdcd", "emdnm", "sggnm", "sidocd", "geom"]).to_pandas()
    tmp = tempfile.mkdtemp(prefix="adk_")
    gdb = arcpy.management.CreateFileGDB(tmp, "a.gdb")[0]
    sr = arcpy.SpatialReference(5179)
    fc = arcpy.management.CreateFeatureclass(gdb, "emd", "POLYGON", spatial_reference=sr)[0]
    arcpy.management.AddField(fc, "lab", "LONG")
    codes = []
    with arcpy.da.InsertCursor(fc, ["SHAPE@", "lab"]) as cur:
        for cd, g in zip(t.emdcd, t.geom):
            codes.append(cd)
            cur.insertRow([arcpy.FromWKB(bytearray(g), sr), len(codes)])
    arcpy.env.extent = arcpy.Extent(x0, y0, x0 + ncol * 100, y0 + nrow * 100)
    arcpy.env.outputCoordinateSystem = sr
    out = os.path.join(tmp, "a.tif")
    arcpy.conversion.PolygonToRaster(fc, "lab", out, "MAXIMUM_AREA", "", 100)
    a = arcpy.RasterToNumPyArray(out, arcpy.Point(x0, y0), ncol, nrow, nodata_to_value=0)
    arcpy.env.extent = None
    arcpy.env.outputCoordinateSystem = None
    keys = [key(s, g, e) for s, g, e in zip(t.sidocd, t.sggnm, t.emdnm)]
    return a.astype(np.int32), codes, keys


def main():
    nm = names()
    snaps = snapshots()
    sdates = {d: date(int(d[:4]), int(d[4:6]), int(d[6:])) for d in snaps}
    con = sqlite3.connect(os.path.join(MDIS, "moves_mdis.sqlite"))
    seen = pd.read_sql("SELECT DISTINCT year, in_cd cd FROM flows_dong UNION SELECT DISTINCT year, out_cd FROM flows_dong",
                       con)
    a = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(a["x0"]), int(a["y0"])
    shape = a["urb"].shape
    sg, sgnames, cap = sigun.raster(x0, y0, *shape)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    old = (a["urb"] >= 50) & (sgis("house", 2000, shape, na=0) >= 5) & ~zone
    d20, d20codes = dong_raster(x0, y0, *shape)
    d20 = d20.ravel().astype(np.int64)
    k20 = len(d20codes) + 1

    print("rasterising", len(snaps), "boundary snapshots", flush=True)
    rast, where, wname = {}, {}, {}
    for d, f in snaps.items():
        lab, codes, keys = snap_raster(f, x0, y0, *shape)
        rast[d] = (lab.ravel().astype(np.int64), {c: i + 1 for i, c in enumerate(codes)}, len(codes) + 1)
        for c, kk in zip(codes, keys):
            where.setdefault(c, []).append(d)
            wname.setdefault(kk, []).append((d, c))
        print(" ", d, len(codes), flush=True)

    pops = {}
    rows, xw = [], []
    for y, g in seen.groupby("year"):
        py = min(POP_YEARS, key=lambda p: (abs(p - y), p))
        if py not in pops:
            pops[py] = sgis("pop", py, shape).ravel().astype(np.float64)
        p = pops[py]
        end = date(y, 12, 31)
        near = lambda d: abs((sdates[d] - end).days)
        pick = {}  # cd -> (snapshot, code in that snapshot, how) or None
        for cd in g.cd:
            ds = where.get(cd)
            if ds:
                d = min(ds, key=near)
                pick[cd] = (d, cd, "year" if sdates[d].year == y or d == f"{y + 1}0101" else "near")
                continue
            r = nm.loc[cd] if cd in nm.index else None
            cand = wname.get(key(cd[:2], r.sgg, r.emd)) if r is not None else None
            pick[cd] = (lambda dc: (dc[0], dc[1], "name"))(min(cand, key=lambda dc: near(dc[0]))) if cand else None
        for d in sorted({v[0] for v in pick.values() if v}):
            lab, idx, k = rast[d]
            P = np.bincount(lab, weights=p, minlength=k)
            O = np.bincount(lab, weights=p * old.ravel(), minlength=k)
            Z = np.bincount(lab, weights=p * zone.ravel(), minlength=k)
            C = np.bincount(lab, minlength=k)
            pair = lab * k20 + d20
            PP = np.bincount(pair, weights=p, minlength=k * k20).reshape(k, k20)
            CC = np.bincount(pair, minlength=k * k20).reshape(k, k20)
            sgp = lab * 1000 + sg.ravel().astype(np.int64)
            u, n = np.unique(sgp[lab > 0], return_counts=True)
            best = {}
            for q, c in zip(u, n):
                i, s = divmod(int(q), 1000)
                if s and c > best.get(i, (0, 0))[1]:
                    best[i] = (s, c)
            for cd, (_, scd, how) in [(c, v) for c, v in pick.items() if v and v[0] == d]:
                i = idx[scd]
                os_ = O[i] / P[i] if P[i] else 0.0
                zs = Z[i] / P[i] if P[i] else 0.0
                s = best.get(i, (0, 0))[0]
                rows.append(dict(year=y, cd=cd, snap=d, match=how, cells=int(C[i]),
                                 pop=round(P[i]), old_share=round(os_, 3), zone_share=round(zs, 3),
                                 cls="zone" if zs >= ZONE_MIN else "old" if os_ >= OLD_MIN else "other",
                                 SG_ID=s, sigun=sgnames.get(s, ""), capital=int(s in cap)))
                tot_p, tot_c = PP[i].sum(), CC[i].sum()
                for j in np.nonzero(CC[i])[0]:
                    if j == 0:
                        continue
                    xw.append((y, cd, d20codes[j - 1][0], round(PP[i, j] / tot_p, 4) if tot_p else 0.0,
                               round(CC[i, j] / tot_c, 4)))
        for cd in [c for c, v in pick.items() if v is None]:
            rows.append(dict(year=y, cd=cd, snap="", match="none"))
        print(f"{y}: codes {len(g):,}  no boundary {sum(v is None for v in pick.values())}  pop grid {py}", flush=True)

    cy = pd.DataFrame(rows).join(nm, on="cd")
    cy = cy[["year", "cd", "sido", "sgg", "emd", "created", "abolished", "snap", "match", "cells", "pop", "old_share",
             "zone_share", "cls", "SG_ID", "sigun", "capital"]]
    cy.to_csv(os.path.join(MDIS, "code_year.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(xw, columns=["year", "cd", "adm_cd2020", "pop_w", "cell_w"]).to_csv(
        os.path.join(MDIS, "dong_xwalk.csv"), index=False, encoding="utf-8-sig")
    print(cy.groupby("match").size().to_string())
    print(cy[cy.match == "none"].groupby(["sido"]).size().to_string())


if __name__ == "__main__":
    main()
