"""Part A 시군 table: land, population and supply for the 비수도권 시군 (130).

Land (large class L1, share-weighted on the 100 m grid):
  urb09, urb19         urban km2 in 2009 and 2019
  new_urb              km2 of cells going from < 10 % (2009) to >= 50 % (2019)
  leap_share           share of new_urb cells with no 2009 urban cell (>= 50 %) among the 8 neighbours
  l3_patch             fine-class new-development patches 2019 -> 2025 (outputs/grid100_check/l3_patch_gain.csv)
Population (SGIS 100 m grid, suppressed cells = 2.5):
  pop{year}            2000, 2005, 2010, 2015, 2019, 2024
  old_pop{year}        population on 기성시가지 cells (L1 2009 urban >= 50 %)
  new_pop{year}        population on new_urb cells
  emp{year}            employees 2010, 2019, 2024
  pcu10, pcu19         urban m2 per person (urb09 / pop2010, urb19 / pop2019)
  decouple             urban grew while population did not (2010 -> 2019)
Supply:
  ic_pre, ic_0110, ic_1115, ic_1624   industrial complex area (km2) by designation year: <= 2000, 2001-2010,
                                      2011-2015, 2016-2024 (earliest year where complexes overlap)
  inno, inno_km2, ent, ent_km2        innovation / enterprise city designated in the 시군 (split evenly where
                                      a city spans two 시군, as in the previous project)
Context:
  er2005                extinction-risk index 2005 (previous project; missing for 제주시, 서귀포시, 울릉군)
  si, metro             시 (vs 군), 광역시

Also writes data_work/grid100/ic_share.npz: industrial complex share (%) of each 100 m cell by the same
designation windows, for the grid analysis.

Output: outputs/partA/sigun_panel.csv
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\sigun_panel.py
"""
import csv
import os
import sys
import tempfile

import arcpy
import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "02_grid"))
import paths
import sigun

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partA")
IC = os.path.join(paths.L1, "ugm_national", "supply", "industrial_complex_tm.shp")
NEW_CITY = os.path.join(paths.L1_SUPPLY, "new_city_gosi", "new_city_designations.csv")
ER = os.path.join(paths.L1, "ugm_national", "extinction_risk_by_city.csv")
PATCH = os.path.join(paths.OUTPUTS, "grid100_check", "l3_patch_gain.csv")
POP_YEARS = [2000, 2005, 2010, 2015, 2019, 2024]
EMP_YEARS = [2010, 2019, 2024]
IC_WINDOWS = {"ic_pre": (0, 2000), "ic_0110": (2001, 2010), "ic_1115": (2011, 2015), "ic_1624": (2016, 2024)}
NA_VALUE = 2.5
SUB = 2  # 50 m sub-cells per 100 m side


def sgis(item, year, n):
    z = np.load(os.path.join(GRID, f"sgis_{item}.npz"))
    a = np.zeros(n, np.float32)
    v = z[f"y{year}_val"]
    a[z[f"y{year}_idx"]] = np.where(v < 0, NA_VALUE, v)
    return a


def ic_years(x0, y0, nrow, ncol):
    """Designation year of the earliest complex on a 50 m lattice aligned to the frame (0 = none)."""
    tmp = tempfile.mkdtemp(prefix="ic_")
    fc = os.path.join(arcpy.management.CreateFileGDB(tmp, "i.gdb")[0], "ic")
    arcpy.env.outputCoordinateSystem = None
    arcpy.env.extent = None
    arcpy.management.Project(IC, fc, arcpy.SpatialReference(5179))
    if "prio" not in [f.name.lower() for f in arcpy.ListFields(fc)]:
        arcpy.management.AddField(fc, "prio", "SHORT")
    arcpy.management.CalculateField(fc, "PRIO", "3000 - !appn_yr! if !appn_yr! and !appn_yr! > 0 else 0", "PYTHON3")
    arcpy.env.extent = arcpy.Extent(x0, y0, x0 + ncol * 100, y0 + nrow * 100)
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(5179)
    out = os.path.join(tmp, "ic.tif")
    arcpy.conversion.PolygonToRaster(fc, "appn_yr", out, "CELL_CENTER", "PRIO", 100 / SUB)
    a = arcpy.RasterToNumPyArray(out, arcpy.Point(x0, y0), ncol * SUB, nrow * SUB, nodata_to_value=0)
    arcpy.env.extent = None
    arcpy.env.outputCoordinateSystem = None
    return a.astype(np.int16)


def new_cities(names):
    out = {i: {"inno": 0, "inno_km2": 0.0, "ent": 0, "ent_km2": 0.0} for i in names}
    by_name = {v: k for k, v in names.items()}
    with open(NEW_CITY, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["type"] not in ("innovation", "enterprise"):
                continue
            key = "inno" if r["type"] == "innovation" else "ent"
            parts = r["sigun_model"].split(";")
            for p in parts:
                if p in by_name:
                    i = by_name[p]
                    out[i][key] = 1
                    out[i][f"{key}_km2"] += float(r["area_m2"]) / 1e6 / len(parts)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    l1a, l1b = np.load(os.path.join(GRID, "l1_2009.npz")), np.load(os.path.join(GRID, "l1_2019.npz"))
    x0, y0 = int(l1a["x0"]), int(l1a["y0"])
    nrow, ncol = l1a["urb"].shape
    n = nrow * ncol
    sg, names, cap = sigun.raster(x0, y0, nrow, ncol)
    u09, u19 = l1a["urb"].astype(np.int16), l1b["urb"].astype(np.int16)
    old = u09 >= 50
    new = (u09 < 10) & (u19 >= 50)
    near_old = ndimage.binary_dilation(old, structure=np.ones((3, 3), bool))
    leap = new & ~near_old

    pops = {y: sgis("pop", y, n).reshape(nrow, ncol) for y in POP_YEARS}
    emps = {y: sgis("emp", y, n).reshape(nrow, ncol) for y in EMP_YEARS}

    yr = ic_years(x0, y0, nrow, ncol)
    sg50 = np.repeat(np.repeat(sg, SUB, axis=0), SUB, axis=1)
    ic_km2, ic_share = {}, {}
    for k, (a, b) in IC_WINDOWS.items():
        m = (yr >= max(a, 1)) & (yr <= b)
        ic_km2[k] = np.bincount(sg50[m].ravel(), minlength=sg.max() + 1) * (100 / SUB) ** 2 / 1e6
        ic_share[k] = (m.reshape(nrow, SUB, ncol, SUB).sum(axis=(1, 3)) * 100 // SUB ** 2).astype(np.uint8)
    np.savez_compressed(os.path.join(GRID, "ic_share.npz"), x0=x0, y0=y0, cell=100, **ic_share)
    print("industrial complexes on the frame, km2: " + ", ".join(f"{k} {v.sum():,.0f}" for k, v in ic_km2.items()))

    nc = new_cities(names)
    er = {}
    with open(ER, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            er[int(r["SG_ID"])] = float(r["ER_2005"]) if r["ER_2005"] else ""
    patch = {}
    with open(PATCH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            patch[int(r["SG_ID"])] = float(r["l3_patch_gain_2019_2025_km2"])

    # per-시군 sums in one pass
    lab = sg.ravel().astype(np.int64)
    k = sg.max() + 1

    def by(a, mask=None):
        w = a.ravel().astype(np.float64)
        if mask is not None:
            w = w * mask.ravel()
        return np.bincount(lab, weights=w, minlength=k)

    land = by(np.ones_like(u09)) * 0.01
    urb09, urb19 = by(u09) / 100 * 0.01, by(u19) / 100 * 0.01
    new_km2, leap_km2 = by(new) * 0.01, by(leap) * 0.01
    pop = {y: by(pops[y]) for y in POP_YEARS}
    old_pop = {y: by(pops[y], old) for y in POP_YEARS}
    new_pop = {y: by(pops[y], new) for y in POP_YEARS}
    emp = {y: by(emps[y]) for y in EMP_YEARS}

    header = (["SG_ID", "sigun", "si", "metro", "land_km2", "urb09", "urb19", "new_urb", "leap_share", "l3_patch"]
              + [f"pop{y}" for y in POP_YEARS] + [f"old_pop{y}" for y in POP_YEARS] + [f"new_pop{y}" for y in POP_YEARS]
              + [f"emp{y}" for y in EMP_YEARS] + ["pcu10", "pcu19", "decouple"] + list(IC_WINDOWS)
              + ["inno", "inno_km2", "ent", "ent_km2", "er2005"])
    rows = []
    for i in sorted(names):
        if i in cap or land[i] == 0:
            continue
        nm = names[i]
        pcu10 = urb09[i] * 1e6 / pop[2010][i] if pop[2010][i] else ""
        pcu19 = urb19[i] * 1e6 / pop[2019][i] if pop[2019][i] else ""
        rows.append([i, nm, int(nm.endswith("시") or nm == "세종시"), int(nm.endswith("광역시")), round(land[i], 2),
                     round(urb09[i], 3), round(urb19[i], 3), round(new_km2[i], 2),
                     round(leap_km2[i] / new_km2[i], 3) if new_km2[i] else "", patch.get(i, "")]
                    + [round(pop[y][i]) for y in POP_YEARS] + [round(old_pop[y][i]) for y in POP_YEARS]
                    + [round(new_pop[y][i]) for y in POP_YEARS] + [round(emp[y][i]) for y in EMP_YEARS]
                    + [round(pcu10, 1), round(pcu19, 1), int(urb19[i] > urb09[i] and pop[2019][i] <= pop[2010][i])]
                    + [round(ic_km2[w][i], 3) for w in IC_WINDOWS]
                    + [nc[i]["inno"], round(nc[i]["inno_km2"], 3), nc[i]["ent"], round(nc[i]["ent_km2"], 3), er.get(i, "")])
    with open(os.path.join(OUT, "sigun_panel.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"{len(rows)} 비수도권 시군 -> {os.path.join(OUT, 'sigun_panel.csv')}")


if __name__ == "__main__":
    main()
