"""Grid bridge to Part B: where new development lands, and how 기성시가지 population changes with distance
to new supply, within 시군 (비수도권).

1. Sprawl gradient: L1 new-urban cells 2009 -> 2019 (< 10 % to >= 50 %) by distance to the 2009 urban
   edge (기성시가지 = L1 2009 urban >= 50 %), with their 2019 population and employees.
2. Exposure of 기성시가지 to new supply, on 500 m blocks of 기성시가지 cells (block population summed over
   기성시가지 cells only; blocks with >= 100 such residents in the base year):
     dist_ic   km to the nearest industrial-complex cell designated 2001-2015 (ic_share.npz)
     dist_nd   km to the nearest large new-development patch 2009 -> 2019 (>= 50 ha, 8-connected)
   Outcome: block population change 2010 -> 2019 and 2015 -> 2024 (register period).
   Model: change ~ distance bands (0-2, 2-5, 5-10 km; > 10 km reference) + log base population, with 시군
   fixed effects and errors clustered by 시군. Negative band coefficients = 기성시가지 near new supply
   loses more population than 기성시가지 far from it in the same 시군.

Output: outputs/partA/grid_sprawl_gradient.csv, grid_distance_models.csv, grid_distance.txt
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\grid_distance.py
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "02_grid"))
import paths
import sigun

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partA")
NA_VALUE = 2.5
BLOCK = 5            # 100 m cells per 500 m block side
PATCH_MIN = 50       # cells (50 ha)
BANDS = [0, 2, 5, 10]
L1_SAME = ["김천시", "영주시"]


def sgis(item, year, shape):
    z = np.load(os.path.join(GRID, f"sgis_{item}.npz"))
    a = np.zeros(shape[0] * shape[1], np.float32)
    v = z[f"y{year}_val"]
    a[z[f"y{year}_idx"]] = np.where(v < 0, NA_VALUE, v)
    return a.reshape(shape)


def dist_km(mask):
    return (ndimage.distance_transform_edt(~mask) * 0.1).astype(np.float32)


def band(dkm):
    labels = [f"d{a}_{b}" for a, b in zip(BANDS[:-1], BANDS[1:])] + [f"d{BANDS[-1]}p"]
    return pd.cut(dkm, BANDS + [np.inf], right=False, labels=labels)


def blocksum(a):
    r, c = a.shape[0] // BLOCK, a.shape[1] // BLOCK
    return a[:r * BLOCK, :c * BLOCK].reshape(r, BLOCK, c, BLOCK).sum(axis=(1, 3))


def main():
    os.makedirs(OUT, exist_ok=True)
    a, b = np.load(os.path.join(GRID, "l1_2009.npz")), np.load(os.path.join(GRID, "l1_2019.npz"))
    x0, y0 = int(a["x0"]), int(a["y0"])
    shape = a["urb"].shape
    sg, names, cap = sigun.raster(x0, y0, *shape)
    keep_sg = [i for i in names if i not in cap and names[i] not in L1_SAME]
    nc = np.isin(sg, keep_sg)
    old = a["urb"] >= 50
    new = (a["urb"] < 10) & (b["urb"] >= 50)
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    # 1) sprawl gradient
    d_old = dist_km(old)
    pop19, emp19 = sgis("pop", 2019, shape), sgis("emp", 2019, shape)
    m = new & nc
    g = pd.DataFrame({"dist": d_old[m], "pop19": pop19[m], "emp19": emp19[m]})
    g["band"] = pd.cut(g.dist, [0, 0.15, 0.5, 1, 2, 5, np.inf], right=False,
                       labels=["인접(<150m)", "150-500m", "0.5-1km", "1-2km", "2-5km", "5km+"])
    t = g.groupby("band", observed=False).agg(km2=("dist", "size"), pop19=("pop19", "sum"), emp19=("emp19", "sum"))
    t["km2"] = t.km2 * 0.01
    t["share_area"] = t.km2 / t.km2.sum()
    t["pop_per_km2"] = t.pop19 / t.km2
    t.round(3).to_csv(os.path.join(OUT, "grid_sprawl_gradient.csv"), encoding="utf-8-sig")
    say("== 1) 신규 시가지(2009->2019)의 기성시가지 경계로부터 거리 (비수도권, 김천·영주 제외)")
    say(t.round(3).to_string())

    # 2) exposure of 기성시가지 blocks
    ic = np.load(os.path.join(GRID, "ic_share.npz"))
    ic_new = (ic["ic_0110"] > 0) | (ic["ic_1115"] > 0)
    lab, _ = ndimage.label(new, structure=np.ones((3, 3)))
    size = np.bincount(lab.ravel())
    size[0] = 0
    big = size[lab] >= PATCH_MIN
    say(f"\n신규 산업단지 셀(2001-2015 지정) {ic_new.sum() * 0.01:,.0f} km2; 대규모 신규개발 덩어리(>=50 ha) "
        f"{int((size >= PATCH_MIN).sum()):,}개, {big.sum() * 0.01:,.0f} km2")
    dist_ic, dist_nd = dist_km(ic_new), dist_km(big)

    rows = {}
    oldnc = old & nc
    for y in (2010, 2015, 2019, 2024):
        rows[f"pop{y}"] = blocksum(sgis("pop", y, shape) * oldnc).ravel()
    n_old = blocksum(oldnc.astype(np.int32)).ravel()
    # block attributes at the block's 기성시가지-weighted centre: use the minimum distance over its 기성시가지 cells
    big_val = np.float32(1e6)

    def blockmin(dm):
        v = np.where(oldnc, dm, big_val)
        r, c = shape[0] // BLOCK, shape[1] // BLOCK
        return v[:r * BLOCK, :c * BLOCK].reshape(r, BLOCK, c, BLOCK).min(axis=(1, 3)).ravel()

    sgb = sg[:shape[0] // BLOCK * BLOCK:BLOCK, :shape[1] // BLOCK * BLOCK:BLOCK]  # top-left cell 시군
    # 시군 of a block = most common 시군 among its 기성시가지 cells
    r, c = shape[0] // BLOCK, shape[1] // BLOCK
    sgv = np.where(oldnc, sg, 0)[:r * BLOCK, :c * BLOCK].reshape(r, BLOCK, c, BLOCK).max(axis=(1, 3)).ravel()
    df = pd.DataFrame({"sg": sgv, "n_old": n_old, "dist_ic": blockmin(dist_ic), "dist_nd": blockmin(dist_nd), **rows})
    df = df[(df.n_old > 0) & (df.sg > 0)]
    say(f"기성시가지 500m 블록 {len(df):,}개")

    res = []
    for base, end in ((2010, 2019), (2015, 2024)):
        s = df[df[f"pop{base}"] >= 100].copy()
        s["chg"] = s[f"pop{end}"] / s[f"pop{base}"] - 1
        s["chg"] = s.chg.clip(-1, 3)
        s["lpop"] = np.log(s[f"pop{base}"])
        for dv in ("dist_ic", "dist_nd"):
            s["band"] = band(s[dv])
            desc = s.groupby("band", observed=False).agg(n=("chg", "size"), pop_base=(f"pop{base}", "sum"), pop_end=(f"pop{end}", "sum"))
            desc["chg_total"] = desc.pop_end / desc.pop_base - 1
            say(f"\n== 2) 기성시가지 블록 인구 변화 {base}->{end}, {dv} 거리대별 (합계 기준)")
            say(desc.round(3).to_string())
            mdl = smf.ols(f"chg ~ C(band, Treatment('d{BANDS[-1]}p')) + lpop + C(sg)", data=s).fit(
                cov_type="cluster", cov_kwds={"groups": s.sg})
            say(f"   시군 고정효과 모형 (n={int(mdl.nobs):,}, 시군 {s.sg.nunique()}):")
            for k in mdl.params.index:
                if k.startswith("C(band"):
                    nm = k.split("[T.")[1].rstrip("]")
                    p = mdl.pvalues[k]
                    star = "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""
                    say(f"     {nm:>7} {mdl.params[k]:+.4f} ({mdl.bse[k]:.4f}){star}")
                    res.append([f"{base}-{end}", dv, nm, mdl.params[k], mdl.bse[k], p, int(mdl.nobs)])
    pd.DataFrame(res, columns=["period", "distance", "band", "coef", "se", "p", "n"]).to_csv(
        os.path.join(OUT, "grid_distance_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "grid_distance.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
