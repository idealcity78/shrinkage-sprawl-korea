"""Are old-core dwellings older and smaller than dwellings in new residential land?  (paper 2, section 3)

집계구 (census-block) housing tables by construction year (ho_yr_*) and floor area (ho_ar_*), 2022 and 2024, placed
on the 100 m frame at an inside point (oa_aging.oa_cells). A 집계구 is
  old core   its cell is 기성시가지 (L1 2009 urban >= 50 %, >= 5 dwellings in 2000, outside the new-city zones)
  new        its cell had < 5 dwellings in 2000 and >= 5 in 2024 (outside the zones)
  other      anything else
Codes (data_raw/sgis/codes/README.md): the ho_yr items run from oldest to newest - ho_yr_001 before 1980, 002 the
1980s, 003 the 1990s, 004 2000-04, 005 2005-09, then one item per year from 2010 (the national shares confirm it:
the 1990s item is the largest and the oldest item shrinks over time). Pre-2000 = ho_yr_001-003.
ho_ar_001-009 = floor-area classes 01-09 (SGIS HouseAreaCode): 001-003 up to 60 m2, 004 60-85 m2, 005-009 over 85 m2.
N/A cells (fewer than 5 dwellings) are set to 2, as in oa_aging.py.
Scope: 시군 of the non-capital 도 (groups 감소, 정체, 성장 of shrink_sprawl_sigun.csv), and by group.

Output: outputs/partB/old_core_housing.txt, old_core_housing.csv
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\old_core_housing.py
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
for p in (CODE, os.path.join(CODE, "02_grid"), os.path.join(CODE, "03_partA")):
    sys.path.insert(0, p)
import paths
from oa_aging import oa_cells
from shrink_sprawl import sgis

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
CSV = os.path.join(paths.SGIS, "oa_stats", "csv", "2025년기준_{year}년_{item}.csv")
OUT = os.path.join(paths.OUTPUTS, "partB")
NA_VALUE = 2


def n_year_items(base):
    """Number of ho_yr items: three decades before 2000, two 2000s half-decades, one item per year 2010..base."""
    return 3 + 2 + (base - 2010 + 1)


def read(year, item):
    t = pd.read_csv(CSV.format(year=year, item=item), header=None, names=["y", "oa", "item", "v"],
                    dtype={"oa": str, "item": str, "v": str}, encoding="cp949")
    t["v"] = pd.to_numeric(t.v, errors="coerce").fillna(NA_VALUE)
    return t.pivot_table(index="oa", columns="item", values="v", aggfunc="sum").fillna(0)


def main():
    import sigun
    z = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(z["x0"]), int(z["y0"])
    shape = z["urb"].shape
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    h00, h24 = sgis("house", 2000, shape, na=0), sgis("house", 2024, shape, na=0)
    old = (z["urb"] >= 50) & (h00 >= 5) & ~zone
    new = (h00 < 5) & (h24 >= 5) & ~zone & ~old
    sg, names, _ = sigun.raster(x0, y0, *shape)
    cells = oa_cells(x0, y0, *shape)
    info = pd.read_csv(os.path.join(paths.OUTPUTS, "partA", "shrink_sprawl_sigun.csv"))[["sigun", "group"]]
    oa = pd.DataFrame([(k, r, c) for k, (r, c) in cells.items()], columns=["oa", "r", "c"])
    oa["type"] = np.where(old[oa.r, oa.c], "old core", np.where(new[oa.r, oa.c], "new", "other"))
    oa["sigun"] = pd.Series(sg[oa.r, oa.c]).map(names).values
    oa = oa.merge(info, on="sigun", how="left")

    rows, lines = [], []

    def say(s=""):
        print(s)
        lines.append(s)

    say("원도심 대 신규 주거지 집계구의 주택: 건축연도와 연건평 (SGIS 집계구, 2025년 경계)")
    for year in (2022, 2024):
        yr = read(year, "건축년도별주택")
        assert yr.shape[1] == n_year_items(year), (year, yr.shape[1])
        pre = ["ho_yr_001", "ho_yr_002", "ho_yr_003"]
        d = pd.DataFrame({"tot_yr": yr.sum(axis=1), "pre2000": yr[pre].sum(axis=1)})
        if year == 2022:
            ar = read(year, "연건평별주택")
            d = d.join(pd.DataFrame({"tot_ar": ar.sum(axis=1),
                                     "le60": ar[["ho_ar_001", "ho_ar_002", "ho_ar_003"]].sum(axis=1),
                                     "gt85": ar[[f"ho_ar_{k:03d}" for k in range(5, 10)]].sum(axis=1)}), how="outer")
        m = oa.merge(d, left_on="oa", right_index=True, how="inner")
        for scope, sel in [("비수도권 도 시군", m.group.isin(["감소", "정체", "성장"])), ("감소", m.group == "감소"),
                           ("성장", m.group == "성장"), ("광역시·수도권", m.group.isin(["광역시", "수도권"]))]:
            g = m[sel].groupby("type").sum(numeric_only=True)
            for t in ["old core", "new", "other"]:
                if t not in g.index:
                    continue
                r = dict(year=year, scope=scope, type=t, oa=int((m[sel].type == t).sum()),
                         dwellings=int(g.at[t, "tot_yr"]), pre2000=g.at[t, "pre2000"] / g.at[t, "tot_yr"] * 100)
                if year == 2022:
                    r["le60"] = g.at[t, "le60"] / g.at[t, "tot_ar"] * 100
                    r["gt85"] = g.at[t, "gt85"] / g.at[t, "tot_ar"] * 100
                rows.append(r)
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, "old_core_housing.csv"), index=False, encoding="utf-8-sig")
    for year in (2022, 2024):
        say(f"\n{year}년 (집단 합계; 2000년 전 주택 비중 %, 60㎡ 이하·85㎡ 초과 비중 %는 2022년만)")
        cols = ["oa", "dwellings", "pre2000"] + (["le60", "gt85"] if year == 2022 else [])
        say(t[t.year == year].set_index(["scope", "type"])[cols].round(1).to_string())
    with open(os.path.join(OUT, "old_core_housing.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
