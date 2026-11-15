"""How much new development lies in the innovation and enterprise new towns (Supplementary Table S11, Panel B).

The old core excludes the 19 new-town districts (newcity_zone.npz), but most new development lies elsewhere. By group:
  dwellings added 2015-2024 outside the old core (SGIS 100 m grid, increases only) and the part inside the districts;
  new urban land 2009-2019 (urban share < 10 -> >= 50) and the part inside the districts.
Same grids and definitions as shrink_sprawl.py.

Output: outputs/partA/newcity_share_grid.csv (grid sums per 시군), newcity_share.csv
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\newcity_share.py   (add "models" to start from
newcity_share_grid.csv without the grids and arcpy)
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
from shrink_sprawl import GRID, ORDER, sgis

sys.stdout.reconfigure(encoding="utf-8")
OUT = os.path.join(paths.OUTPUTS, "partA")


def build():
    """Grid sums per 시군: dwellings added outside the old core and new urban land, all and inside the districts."""
    import sigun
    l = {y: np.load(os.path.join(GRID, f"l1_{y}.npz")) for y in (2009, 2019)}
    x0, y0 = int(l[2009]["x0"]), int(l[2009]["y0"])
    shape = l[2009]["urb"].shape
    u09, u19 = l[2009]["urb"].astype(np.int16), l[2019]["urb"].astype(np.int16)
    sg, _, _ = sigun.raster(x0, y0, *shape)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    old = (u09 >= 50) & (sgis("house", 2000, shape, na=0) >= 5) & ~zone
    dh = np.clip(sgis("house", 2024, shape, na=0) - sgis("house", 2015, shape, na=0), 0, None) * ~old
    new = (u09 < 10) & (u19 >= 50)
    lab = sg.ravel().astype(np.int64)
    k = int(sg.max()) + 1
    by = lambda w: np.bincount(lab, weights=np.asarray(w, np.float64).ravel(), minlength=k)
    t = pd.DataFrame({"SG_ID": np.arange(k), "dh_out": by(dh), "dh_out_newtown": by(dh * zone),
                      "new_km2": by(new) * 0.01, "new_newtown_km2": by(new & zone) * 0.01})
    return t[t.SG_ID > 0]


def main():
    if "models" not in sys.argv[1:]:
        build().to_csv(os.path.join(OUT, "newcity_share_grid.csv"), index=False, encoding="utf-8-sig")
    s = pd.read_csv(os.path.join(OUT, "newcity_share_grid.csv"))
    t = pd.read_csv(os.path.join(OUT, "shrink_sprawl_sigun.csv"))[["SG_ID", "group"]].merge(s, on="SG_ID")
    cols = ["dh_out", "dh_out_newtown", "new_km2", "new_newtown_km2"]
    rows = []
    for g in ORDER + ["전체"]:
        m = t if g == "전체" else t[t.group == g]
        rows.append({"group": g, **m[cols].sum().to_dict()})
    d = pd.DataFrame(rows)
    # areas are cell counts x 0.01 km2: round off the float noise of the sums so that ties print the same everywhere
    d[["new_km2", "new_newtown_km2"]] = d[["new_km2", "new_newtown_km2"]].round(2)
    d["dh_pct"] = d.dh_out_newtown / d.dh_out * 100
    d["new_pct"] = d.new_newtown_km2 / d.new_km2 * 100
    d.to_csv(os.path.join(OUT, "newcity_share.csv"), index=False, encoding="utf-8-sig")
    print(d.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
