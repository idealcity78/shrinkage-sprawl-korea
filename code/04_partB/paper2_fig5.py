"""Figure 5 of paper 2: case-city maps on the 100 m grid for three innovation-city hosts (Jinju, Jeonju, Naju).

Cell classes (same definitions as shrink_sprawl.py / the flow allocation):
  old core      L1 2009 urban >= 50 % and >= 5 dwellings in 2000, outside the new-town zones
  new-town zone innovation/enterprise-city zone (data_work/grid100/newcity_zone.npz)
  new land      < 5 dwellings in 2000 and >= 5 in 2024, outside the zones and the old core
  other urban   L1 2019 urban >= 50 % not in the classes above
Each panel title gives the share of the zone's in-movers (2011-2025 annual mean) who came from the same city's old
core, computed from the table "신도시 전입자 출신" in outputs/flows/mdis_old_core.txt (old / total).

Output: outputs/paper2/fig5_case_cities.png, fig5_case_cities.txt (cell counts and shares)
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\paper2_fig5.py
"""
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
for p in (CODE, os.path.join(CODE, "02_grid"), os.path.join(CODE, "03_partA")):
    sys.path.insert(0, p)
import paths
from shrink_sprawl import sgis

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "paper2")
CASES = [("진주시", "Jinju"), ("전주시", "Jeonju"), ("나주시", "Naju")]
COLORS = ["#ffffff", "#f1f0ec", "#d6d4cc", "#52514e", "#2a78d6", "#eb6834"]   # outside, land, other urban, old, new, zone
LABELS = ["Other urban (2019)", "Old core", "New residential land (2000-2024)", "Innovation-city zone"]
plt.rcParams.update({"font.family": "Arial", "font.size": 9})


def origin_shares():
    t = open(os.path.join(paths.OUTPUTS, "flows", "mdis_old_core.txt"), encoding="utf-8").read()
    block = t.split("신도시 전입자 출신")[1]
    out = {}
    for name, _ in CASES:
        m = re.search(rf"\n{name}\s+([\d.]+)\s+(?:[\dNaN.]+\s+){{7}}([\d.]+)", block)
        out[name] = (float(m.group(1)), float(m.group(2)))
    return out


def main():
    import sigun
    l09, l19 = np.load(os.path.join(GRID, "l1_2009.npz")), np.load(os.path.join(GRID, "l1_2019.npz"))
    x0, y0 = int(l09["x0"]), int(l09["y0"])
    shape = l09["urb"].shape
    sg, names, _ = sigun.raster(x0, y0, *shape)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    h00, h24 = sgis("house", 2000, shape, na=0), sgis("house", 2024, shape, na=0)
    old = (l09["urb"] >= 50) & (h00 >= 5) & ~zone
    new = (h00 < 5) & (h24 >= 5) & ~zone & ~old
    urb = (l19["urb"] >= 50) & ~old & ~new & ~zone
    ids = {v: k for k, v in names.items()}
    shares = origin_shares()
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.3))
    lines = []
    for ax, (name, en) in zip(axes, CASES):
        own = sg == ids[name]
        if name == "전주시":                      # the Jeonju zone straddles the Wanju border: show both
            own = own | (sg == ids["완주군"])
        rr, cc = np.where(own)
        r0, r1, c0, c1 = rr.min(), rr.max() + 1, cc.min(), cc.max() + 1
        cls = np.zeros((r1 - r0, c1 - c0), np.uint8)
        o = own[r0:r1, c0:c1]
        cls[o] = 1
        cls[o & urb[r0:r1, c0:c1]] = 2
        cls[o & old[r0:r1, c0:c1]] = 3
        cls[o & new[r0:r1, c0:c1]] = 4
        cls[o & zone[r0:r1, c0:c1]] = 5
        ax.imshow(cls, cmap=ListedColormap(COLORS), vmin=0, vmax=5, interpolation="nearest")
        ax.set_axis_off()
        old_n, tot_n = shares[name]
        ax.set_title(f"{en}" + (" (with Wanju)" if name == "전주시" else "") +
                     f"\n{old_n / tot_n * 100:.1f}% of new-town in-movers\nfrom own old core", fontsize=8.5, loc="left")
        n = {k: int((cls == i).sum()) for i, k in [(3, "old"), (4, "new"), (5, "zone"), (2, "urban")]}
        lines.append(f"{name}: cells old {n['old']}, new {n['new']}, zone {n['zone']}, other urban {n['urban']}; "
                     f"new-town in-movers from own old core {old_n:.0f}/{tot_n:.0f} = {old_n / tot_n * 100:.1f}%")
    fig.legend(handles=[Patch(color=c, label=l) for c, l in zip(COLORS[2:], LABELS)], loc="lower center", ncol=4,
               frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(bottom=0.12, wspace=0.05)
    fig.savefig(os.path.join(OUT, "fig5_case_cities.png"), dpi=300, bbox_inches="tight")
    with open(os.path.join(OUT, "fig5_case_cities.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
