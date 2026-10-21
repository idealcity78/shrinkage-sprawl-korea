"""Part A on the register-census period (2015 -> 2024), free of the 2010 -> 2015 census break.

Land in this period: fine-class new-development patches 2019 -> 2025 (l3_patch, km2), and SGIS urban-area grid
(도시 + 준도시 1 km cells, defined from population density) 2015 and 2024.
Population: grid totals 2015, 2019, 2024; 기성시가지 (L1 2009 urban) population; 집계구 aging (oa_aging.py).

Outcomes
  d_pop_1524, d_pop_1924      시군 population change
  old_d_1524, old_d_1924      기성시가지 population change
  patch_rate                  l3_patch / urb19
  decouple_r                  l3_patch >= 0.1 km2 and population 2019 -> 2024 not growing
  ua_growth                   urban-area grid km2 2024 / 2015 - 1
  d_old65                     기성시가지 65+ share, 2024 minus 2015 (percentage points)
  d_gap65                     same for (기성시가지 - other) 65+ share: positive = old core ages faster
Supply: industrial complexes 2001-2010 and 2011-2015 (km2), innovation city, enterprise city.
Controls: log population 2015, extinction risk 2005, 기성시가지 65+ share 2015, urban share 2009, 시, 광역시.

Input : outputs/partA/sigun_panel.csv, oa_aging_wide.csv; data_raw/sgis/urban_area_grid/shp
Output: outputs/partA/register_panel.csv, register_groups.csv, register_models.csv, register_period.txt
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\register_period.py
"""
import glob
import os
import sys
import tempfile

import arcpy
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "02_grid"))
import paths
import sigun

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partA")
UA = os.path.join(paths.SGIS, "urban_area_grid", "shp")
L1_SAME = ["김천시", "영주시"]


def urban_area_km2(year, x0, y0, nrow, ncol, sg):
    """km2 of 도시 + 준도시 1 km cells per 시군 id (100 m rasterisation, so partial 시군 overlaps count)."""
    tmp = tempfile.mkdtemp(prefix="ua_")
    acc = np.zeros(sg.max() + 1)
    arcpy.env.extent = arcpy.Extent(x0, y0, x0 + ncol * 100, y0 + nrow * 100)
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(5179)
    for k, f in enumerate(glob.glob(os.path.join(UA, f"도시화경계_{year}_*.shp"))):
        out = os.path.join(tmp, f"ua{year}_{k}.tif")
        arcpy.conversion.PolygonToRaster(f, "FID", out, "CELL_CENTER", "", 100)
        a = arcpy.RasterToNumPyArray(out, arcpy.Point(x0, y0), ncol, nrow, nodata_to_value=-1)
        acc += np.bincount(sg[a >= 0].ravel().astype(np.int64), minlength=sg.max() + 1) * 0.01
    arcpy.env.extent = None
    arcpy.env.outputCoordinateSystem = None
    return acc


def build():
    d = pd.read_csv(os.path.join(OUT, "sigun_panel.csv"))
    w = pd.read_csv(os.path.join(OUT, "oa_aging_wide.csv")).drop(columns="sigun")
    d = d.merge(w, on="SG_ID", how="left")
    z = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(z["x0"]), int(z["y0"])
    nrow, ncol = z["urb"].shape
    sg, _, _ = sigun.raster(x0, y0, nrow, ncol)
    for y in (2015, 2024):
        a = urban_area_km2(y, x0, y0, nrow, ncol, sg)
        d[f"ua{y}"] = d.SG_ID.map(lambda i: round(a[i], 2))
    d["d_pop_1524"] = d.pop2024 / d.pop2015 - 1
    d["d_pop_1924"] = d.pop2024 / d.pop2019 - 1
    d["old_d_1524"] = d.old_pop2024 / d.old_pop2015 - 1
    d["old_d_1924"] = d.old_pop2024 / d.old_pop2019 - 1
    d["patch_rate"] = d.l3_patch / d.urb19
    d["decouple_r"] = ((d.l3_patch >= 0.1) & (d.d_pop_1924 <= 0)).astype(int)
    d["ua_growth"] = np.where(d.ua2015 > 0, d.ua2024 / d.ua2015.where(d.ua2015 > 0) - 1, np.nan)
    d["old65_15"] = d.old_share65_2015 * 100
    d["d_old65"] = (d.old_share65_2024 - d.old_share65_2015) * 100
    d["d_gap65"] = ((d.old_share65_2024 - d.other_share65_2024) - (d.old_share65_2015 - d.other_share65_2015)) * 100
    d["lpop15"] = np.log(d.pop2015)
    d["urb_share09"] = d.urb09 / d.land_km2
    d["group"] = np.where(d.inno == 1, "혁신도시", np.where(d.ic_0110 >= 1, "산업단지 공급", "그 외"))
    d.to_csv(os.path.join(OUT, "register_panel.csv"), index=False, encoding="utf-8-sig")
    return d


def main():
    d = build()
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    tot = d[["pop2015", "pop2019", "pop2024", "old_pop2015", "old_pop2019", "old_pop2024", "ua2015", "ua2024", "l3_patch"]].sum()
    say(f"비수도권 합계 (130 시군): 인구 {tot.pop2015:,.0f} -> {tot.pop2019:,.0f} -> {tot.pop2024:,.0f}; "
        f"기성시가지 인구 {tot.old_pop2015:,.0f} -> {tot.old_pop2019:,.0f} -> {tot.old_pop2024:,.0f}")
    say(f"도시화지역 격자(도시+준도시) {tot.ua2015:,.0f} -> {tot.ua2024:,.0f} km2; 세분류 신규개발 덩어리 2019-25 {tot.l3_patch:,.0f} km2")
    say(f"인구 감소 시군 2019->2024: {(d.d_pop_1924 < 0).sum()}개; 그중 신규개발 덩어리 0.1 km2 이상: {int(d.decouple_r.sum())}개")
    say(f"기성시가지 인구 감소 시군 2019->2024: {(d.old_d_1924 < 0).sum()}개 / 130")

    cols = {"n": ("sigun", "count"), "인구변화 19-24": ("d_pop_1924", "mean"), "기성시가지 인구변화 15-24": ("old_d_1524", "mean"),
            "기성시가지 인구변화 19-24": ("old_d_1924", "mean"), "신규개발 덩어리/2019시가지": ("patch_rate", "mean"),
            "탈동조화(19-24)": ("decouple_r", "mean"), "도시화지역 격자 증가율 15-24": ("ua_growth", "mean"),
            "기성시가지 65+ 2015 (%)": ("old65_15", "mean"), "기성시가지 65+ 증가 15-24 (%p)": ("d_old65", "mean"),
            "기성-그외 65+ 격차 변화 (%p)": ("d_gap65", "mean")}
    g = d.groupby("group").agg(**cols).round(3)
    g.to_csv(os.path.join(OUT, "register_groups.csv"), encoding="utf-8-sig")
    say("\n== 집단별 평균")
    say(g.T.to_string())

    ctrl = "lpop15 + er2005 + old65_15 + urb_share09 + si + metro"
    supply = "ic_0110 + ic_1115 + inno + ent"
    specs = [("patch_rate", f"{supply} + {ctrl}"), ("decouple_r", f"{supply} + {ctrl}"),
             ("d_pop_1924", f"{supply} + {ctrl}"), ("old_d_1524", f"{supply} + {ctrl}"),
             ("old_d_1924", f"{supply} + {ctrl}"), ("old_d_1924", f"{supply} + d_pop_1924 + {ctrl}"),
             ("old_d_1924", f"patch_rate + d_pop_1924 + {ctrl}"),
             ("d_old65", f"{supply} + {ctrl}"), ("d_gap65", f"{supply} + {ctrl}")]
    samples = {"all": d, "no 김천·영주": d[~d.sigun.isin(L1_SAME)], "no 김천·영주·세종": d[~d.sigun.isin(L1_SAME + ["세종시"])]}
    rows = []
    for y, x in specs:
        for sname, s in samples.items():
            s = s.dropna(subset=[y] + [v.strip() for v in x.split("+")])
            m = smf.ols(f"{y} ~ {x}", data=s).fit(cov_type="HC1")
            for v in m.params.index:
                rows.append([y, x, sname, int(m.nobs), round(m.rsquared, 3), v, m.params[v], m.bse[v], m.pvalues[v]])
            if sname == "no 김천·영주":
                say(f"\n== {y} ~ {x}   [{sname}, n={int(m.nobs)}, R2={m.rsquared:.2f}]")
                for v in m.params.index:
                    if v == "Intercept":
                        continue
                    star = "***" if m.pvalues[v] < .01 else "**" if m.pvalues[v] < .05 else "*" if m.pvalues[v] < .1 else ""
                    say(f"   {v:>12} {m.params[v]:+.4f} ({m.bse[v]:.4f}){star}")
    pd.DataFrame(rows, columns=["y", "x", "sample", "n", "r2", "term", "coef", "se", "p"]).to_csv(
        os.path.join(OUT, "register_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "register_period.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
