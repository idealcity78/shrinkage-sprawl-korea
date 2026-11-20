"""Robustness of the zoning routes (zoning_route.py) to how new dwellings and new urban land are measured.

Prompted by the mock review of 2026-11-21. zoning_route.py counts the dwellings added outside the old core as the sum
of cell increases, max(H_c,2024 - H_c,2015, 0). On the 100 m grid many rural cells move up and down between years
(suppressed counts of 1-4, register updates), so gross increases overstate net growth where cells also lose
dwellings. And "new urban land" (large class) includes roads, public facilities and other non-building land, which
are rarely zoned residential, commercial or industrial.

Per 시군 and zoning route (A = 주거·상업·공업지역 ... F, as zoning_route.py), outside the old core:
  dh_gross    sum of cell increases 2015 -> 2024 (as zoning_route.py; suppressed cells = 0)
  dh_net      net change (increases and decreases)
  dh_ge5      increases of at least 5 dwellings in a cell (above the suppression range)
New urban land 2009 -> 2019 (large class < 10 % -> >= 50 %), split by the urban classes of the national 2022
middle-class map in the cell (residential, industrial, commercial, cultural and leisure, transport, public
facilities; each cell's new urban area divided in proportion to them), and new urban land in cells that gained at
least one dwelling or employee 2015 -> 2024 (an indicator of building use). The 2019 detailed map covers only about
two-thirds of the cells and is not used.
Old core / unit totals of dwellings (gross and net, 2015 -> 2024) for the share of new dwellings outside the old core.

Output: outputs/partA/zoning_route_robust_grid.csv, zoning_route_robust.txt, zoning_route_robust_summary.csv
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\zoning_route_robust.py   (add "models" to skip the grid step)
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
for p in (CODE, os.path.join(CODE, "02_grid"), HERE):
    sys.path.insert(0, p)
import paths
from shrink_sprawl import sgis
from zoning_route import ORDER, ROUTES

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partA")
L2 = {"res": "Residential", "ind": "Industrial", "com": "Commercial", "cul": "Cultural and leisure", "tra": "Transport",
      "pub": "Public facilities"}
BLD = ["res", "ind", "com"]


def build():
    import sigun
    l09, l19 = np.load(os.path.join(GRID, "l1_2009.npz")), np.load(os.path.join(GRID, "l1_2019.npz"))
    x0, y0 = int(l09["x0"]), int(l09["y0"])
    shape = l09["urb"].shape
    u09, u19 = l09["urb"].astype(np.int16), l19["urb"].astype(np.int16)
    z = np.load(os.path.join(GRID, "zoning.npz"))
    share = {r: sum(z[g].astype(np.float32) for g in gs) / 100 for r, gs in ROUTES.items()}
    share["F"] = np.clip(1 - sum(share.values()), 0, 1)
    sg, names, _ = sigun.raster(x0, y0, *shape)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    old = (u09 >= 50) & (sgis("house", 2000, shape, na=0) >= 5) & ~zone
    lab = sg.ravel().astype(np.int64)
    k = int(sg.max()) + 1
    by = lambda w: np.bincount(lab, weights=np.asarray(w, np.float64).ravel(), minlength=k)
    h15, h24 = sgis("house", 2015, shape, na=0), sgis("house", 2024, shape, na=0)
    d = h24 - h15
    e15, e24 = sgis("emp", 2015, shape, na=0), sgis("emp", 2024, shape, na=0)
    used = (d > 0) | (e24 > e15)
    new = ((u09 < 10) & (u19 >= 50)).astype(np.float32)
    l2 = np.load(os.path.join(GRID, "l2_2022.npz"))
    tot = np.maximum(sum(l2[c].astype(np.float32) for c in L2), 1)
    cls = {c: l2[c] for c in L2}
    r = {"SG_ID": np.arange(k)}
    out = ~old
    for rt, s in share.items():
        r[f"gross_{rt}"] = by(np.clip(d, 0, None) * out * s)
        r[f"net_{rt}"] = by(d * out * s)
        r[f"ge5_{rt}"] = by(np.where(d >= 5, d, 0) * out * s)
        r[f"new_{rt}"] = by(new * s) * 0.01
        r[f"newused_{rt}"] = by(new * used * s) * 0.01
        for c, a in cls.items():
            r[f"new_{c}_{rt}"] = by(new * s * np.clip(a.astype(np.float32), 0, None) / tot) * 0.01
    r["gross_old"], r["net_old"] = by(np.clip(d, 0, None) * old), by(d * old)
    r["ge5_old"] = by(np.where(d >= 5, d, 0) * old)
    t = pd.DataFrame(r)
    t = t[t.SG_ID > 0]
    t["sigun"] = t.SG_ID.map(names)
    t.to_csv(os.path.join(OUT, "zoning_route_robust_grid.csv"), index=False, encoding="utf-8-sig")


def main():
    if "models" not in sys.argv[1:]:
        build()
    t = pd.read_csv(os.path.join(OUT, "zoning_route_robust_grid.csv"))
    grp = pd.read_csv(os.path.join(OUT, "zoning_route_sigun.csv")).set_index("SG_ID").group
    t["group"] = t.SG_ID.map(grp)
    t = t[t.group.isin(ORDER)]
    g = t.groupby("group").sum(numeric_only=True).reindex(ORDER)
    rts = list(ROUTES) + ["F"]
    lines, summ = [], []

    def say(s=""):
        print(s)
        lines.append(s)

    say("1. 기성시가지 밖 새 주택 2015 -> 2024: 측정 방식별 주거·상업·공업지역(A) 밖 비중 (%)")
    rows = {}
    for m, lab in [("gross", "셀 증가의 합 (본문)"), ("net", "순증가"), ("ge5", "5호 이상 증가 셀")]:
        tot = g[[f"{m}_{r}" for r in rts]].sum(axis=1)
        rows[lab] = (1 - g[f"{m}_A"] / tot) * 100
        rows[f"{lab} 합계 (호)"] = tot
    summ.append(("offplan_dwellings", pd.DataFrame(rows)))
    say(pd.DataFrame(rows).round(1).to_string())
    say("\n2. 새 주택 가운데 기성시가지 밖 비중 2015 -> 2024 (%)")
    rows = {}
    for m, lab in [("gross", "셀 증가의 합"), ("net", "순증가"), ("ge5", "5호 이상 증가 셀")]:
        outside = g[[f"{m}_{r}" for r in rts]].sum(axis=1)
        rows[lab] = outside / (outside + g[f"{m}_old"]) * 100
        rows[f"{lab}: 기성시가지 (호)"] = g[f"{m}_old"]
    summ.append(("outside_old_core", pd.DataFrame(rows)))
    say(pd.DataFrame(rows).round(1).to_string())
    say("\n3. 신규 시가지 2009 -> 2019: A 밖 비중 (%), 전체와 건물 용도·사용 셀만")
    rows = {}
    newtot = g[[f"new_{r}" for r in rts]].sum(axis=1)
    rows["전체 (본문)"] = (1 - g.new_A / newtot) * 100
    ut = g[[f"newused_{r}" for r in rts]].sum(axis=1)
    rows["2015-24 주택·종사자가 는 셀"] = (1 - g.newused_A / ut) * 100
    bt = sum(g[[f"new_{c}_{r}" for r in rts]].sum(axis=1) for c in BLD)
    rows["주거·공업·상업 용도 (2022 중분류)"] = (1 - sum(g[f"new_{c}_A"] for c in BLD) / bt) * 100
    rows["주거 용도만"] = (1 - g.new_res_A / g[[f"new_res_{r}" for r in rts]].sum(axis=1)) * 100
    rows["신규 시가지 km2"] = newtot
    summ.append(("offplan_land", pd.DataFrame(rows)))
    say(pd.DataFrame(rows).round(1).to_string())
    say("\n4. 신규 시가지 2009 -> 2019의 2022 중분류 구성 (%; 전체 / A 밖)")
    for part, cols in [("전체", rts), ("A 밖", rts[1:])]:
        den = sum(g[[f"new_{c}_{r}" for r in cols]].sum(axis=1) for c in L2)
        tab = pd.DataFrame({L2[c]: g[[f"new_{c}_{r}" for r in cols]].sum(axis=1) / den * 100 for c in L2})
        summ.append((f"composition_{'all' if part == '전체' else 'offplan'}", tab))
        say(f"   {part}")
        say(tab.round(1).to_string())
    pd.concat([d.rename_axis("group").reset_index().melt(id_vars="group", var_name="measure").assign(table=n)
               for n, d in summ])[["table", "measure", "group", "value"]].to_csv(
        os.path.join(OUT, "zoning_route_robust_summary.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "zoning_route_robust.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
