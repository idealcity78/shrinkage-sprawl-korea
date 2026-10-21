"""Part B (redesigned): 시군 x period panel of old-core change on the location of new housing supply.

Treatment is no longer "parent city of an innovation city" but how much housing each 시군 added, and where:
  s_old        inside the 기성시가지 (redevelopment, infill)
  s_zone       inside innovation / enterprise city zones
  s_b1..s_b4   elsewhere, by distance to the main old core: 0-0.5, 0.5-2, 2-5, > 5 km
each as housing-unit increase / 시군 housing units at the start, per year (%).

기성시가지 here = L1 2009 urban >= 50 % cells that already had >= 5 housing units in 2000 (SGIS grid), outside the
zones. The 2000 filter keeps land built 2000-2009 out of the old core, so the definition fits every period.
Main old core (for distance) = 8-connected patches of it with >= 50 cells (0.5 km2); small village patches
still count in the outcome and in s_old.

Periods: 2000-05, 2005-10 (full census), 2015-19, 2019-24 (register census). The 2010 -> 2015 method break
falls between periods; flows are always measured within one method.

Outcomes (per year)
  g_old      기성시가지 population growth (%)
  rel_old    g_old minus 시군 population growth (pp): shift out of the old core
  d_old65    기성시가지 65+ share change (pp per year; 집계구 placed by inside point)
Model: outcome on supply terms + 시군 FE + region x period FE (8 regions: 도, with each 광역시 / 세종 joined to
its 도), errors clustered by 시군. Sample: 비수도권 시군 with >= 1,000 old-core residents in 2000; main without
세종, then with it. Variants: lagged supply (previous period, same method), shrinking 시군 interaction (시군
population fell 2000 -> 2005), new residential land (km2 per old-core km2) instead of units, old core = L1 2009
only (Part A definition).

Input : data_work/grid100 (l1_2009, newcity_zone, sgis_pop, sgis_hh, sgis_house); SGIS 집계구 boundaries and
        성연령별 인구 (oa_aging.py paths)
Output: outputs/partB/supply_panel.csv, supply_panel_models.csv, supply_panel.txt
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\supply_panel.py
"""
import os
import sys
from collections import Counter

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "02_grid"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "03_partA"))
import paths
import sigun
from oa_aging import oa_cells, read_age

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partB")
PERIODS = [(2000, 2005), (2005, 2010), (2015, 2019), (2019, 2024)]
YEARS = sorted({y for p in PERIODS for y in p})
NA_VALUE = 2.5
CORE_MIN = 50  # cells
BANDS = {"s_b1": (0, 5), "s_b2": (5, 20), "s_b3": (20, 50), "s_b4": (50, 1e9)}  # distance in cells (100 m)
NEW_FROM, NEW_TO = 5, 10
# 시도 code (first two digits of the 집계구 code) -> region; 광역시 and 세종 join their 도
REGION = {"21": "경남", "26": "경남", "38": "경남", "22": "경북", "37": "경북", "24": "전남", "36": "전남",
          "25": "충남", "29": "충남", "34": "충남", "33": "충북", "32": "강원", "51": "강원",
          "35": "전북", "52": "전북", "39": "제주", "50": "제주"}


def sgis(item, year, shape, na=NA_VALUE):
    z = np.load(os.path.join(GRID, f"sgis_{item}.npz"))
    a = np.zeros(shape[0] * shape[1], np.float32)
    v = z[f"y{year}_val"]
    a[z[f"y{year}_idx"]] = np.where(v < 0, na, v)
    return a.reshape(shape)


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def main():
    os.makedirs(OUT, exist_ok=True)
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    a = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(a["x0"]), int(a["y0"])
    shape = a["urb"].shape
    sg, names, cap = sigun.raster(x0, y0, *shape)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    h2000 = sgis("house", 2000, shape, na=0)
    masks = {"new": (a["urb"] >= 50) & (h2000 >= 5) & ~zone, "l1": (a["urb"] >= 50) & ~zone}
    del h2000
    lab = sg.ravel().astype(np.int64)
    k = sg.max() + 1

    def by(v, m=None):
        w = v.ravel().astype(np.float64)
        if m is not None:
            w = w * m.ravel()
        return np.bincount(lab, weights=w, minlength=k)

    land = by(np.ones(shape, np.float32))
    ids = [i for i in sorted(names) if i not in cap and land[i] > 0]

    # parts of each 시군 for each old-core definition
    parts = {}
    for d, old in masks.items():
        cl, n = ndimage.label(old, structure=np.ones((3, 3), bool))
        size = np.bincount(cl.ravel())
        core = (size[cl] >= CORE_MIN) & (cl > 0)
        dist = ndimage.distance_transform_edt(~core)
        rest = ~old & ~zone
        p = {"s_old": old, "s_zone": zone}
        for b, (lo, hi) in BANDS.items():
            p[b] = rest & (dist > lo) & (dist <= hi)
        parts[d] = p
        say(f"기성시가지 ({d}): {old.sum() / 100:,.0f} km2, 주 시가지 패치 {core.sum() / 100:,.0f} km2")
        del cl, size, core, dist

    lev = {}  # (year) -> dict of per-시군 arrays
    for y in YEARS:
        pop, hh, house = sgis("pop", y, shape), sgis("hh", y, shape), sgis("house", y, shape)
        L = {"pop": by(pop), "hh": by(hh), "house": by(house)}
        for d, p in parts.items():
            L[f"{d}_oldpop"] = by(pop, masks[d])
            for t, m in p.items():
                L[f"{d}_{t}"] = by(house, m)
        lev[y] = L
        del pop, hh, house
    newres = {}
    for t0, t1 in PERIODS:
        nc = (sgis("house", t0, shape, na=0) < NEW_FROM) & (sgis("house", t1, shape) >= NEW_TO)
        for d, p in parts.items():
            for t, m in p.items():
                newres[(t0, d, t)] = by(nc, m) * 0.01

    # aging on 집계구, both old-core definitions
    cells = oa_cells(x0, y0, *shape)
    oa_sg = {c: int(sg[r, cc]) for c, (r, cc) in cells.items()}
    oa_old = {d: {c: bool(m[r, cc]) for c, (r, cc) in cells.items()} for d, m in masks.items()}
    reg = {}
    for c, s in oa_sg.items():
        reg.setdefault(s, Counter())[str(c)[:2]] += 1
    region = {s: REGION.get(cnt.most_common(1)[0][0], "기타") for s, cnt in reg.items()}
    age = {}
    for y in YEARS:
        tot, o65, _ = read_age(y)
        for d in masks:
            t_, o_ = np.zeros(k), np.zeros(k)
            for c, v in tot.items():
                if c in oa_sg and oa_old[d][c]:
                    t_[oa_sg[c]] += v
                    o_[oa_sg[c]] += o65.get(c, 0)
            age[(y, d)] = np.where(t_ > 0, o_ / np.maximum(t_, 1) * 100, np.nan)

    rows = []
    for t0, t1 in PERIODS:
        L0, L1, n = lev[t0], lev[t1], t1 - t0
        for d in masks:
            for i in ids:
                nm = names[i]
                r = dict(SG_ID=i, sigun=nm, region=region.get(i, "기타"), defn=d, period=f"{t0}-{t1}", t0=t0,
                         old_pop0=L0[f"{d}_oldpop"][i], pop0=L0["pop"][i], house0=L0["house"][i],
                         g_pop=((L1["pop"][i] / L0["pop"][i]) ** (1 / n) - 1) * 100,
                         g_hh=((L1["hh"][i] / L0["hh"][i]) ** (1 / n) - 1) * 100,
                         g_old=((L1[f"{d}_oldpop"][i] / L0[f"{d}_oldpop"][i]) ** (1 / n) - 1) * 100
                         if L0[f"{d}_oldpop"][i] > 0 and L1[f"{d}_oldpop"][i] > 0 else np.nan,
                         d_old65=(age[(t1, d)][i] - age[(t0, d)][i]) / n)
                for t in parts[d]:
                    r[t] = (L1[f"{d}_{t}"][i] - L0[f"{d}_{t}"][i]) / L0["house"][i] / n * 100
                    r["a" + t[1:]] = newres[(t0, d, t)][i]
                rows.append(r)
    df = pd.DataFrame(rows)
    old_km2 = {d: by(m) * 0.01 for d, m in masks.items()}
    for d in masks:
        sel = df.defn == d
        km2 = df.loc[sel, "SG_ID"].map(lambda i: old_km2[d][i])
        for t in parts[d]:
            c = "a" + t[1:]
            df.loc[sel, c] = df.loc[sel, c] / km2 / (df.loc[sel, "period"].str[-4:].astype(int) - df.loc[sel, "t0"]) * 100
    df["rel_old"] = df.g_old - df.g_pop
    df["s_out"] = df[list(BANDS)].sum(axis=1)
    df["rp"] = df.region + "_" + df.period
    base = df[df.defn == "new"].set_index(["SG_ID", "t0"]).old_pop0
    keep_ids = {i for (i, t), v in base.items() if t == 2000 and v >= 1000}
    df = df[df.SG_ID.isin(keep_ids)].copy()
    shrink = df[(df.defn == "new") & (df.t0 == 2000)].set_index("SG_ID").g_pop < 0
    df["shrink"] = df.SG_ID.map(shrink).astype(int)
    lag = df.sort_values("t0").groupby(["defn", "SG_ID"]).s_out.shift()
    df["s_out_lag"] = np.where(df.t0.isin([2005, 2019]), lag, np.nan)
    df.to_csv(os.path.join(OUT, "supply_panel.csv"), index=False, encoding="utf-8-sig")

    S = "s_old + s_zone + s_b1 + s_b2 + s_b3 + s_b4"
    A = "a_old + a_zone + a_b1 + a_b2 + a_b3 + a_b4"
    mrows = []

    def model(g, y, x, label, test=True):
        g = g.dropna(subset=[y] + [v.strip() for v in x.replace("*", "+").split("+") if v.strip() in g])
        m = smf.ols(f"{y} ~ {x} + C(SG_ID) + C(rp)", data=g).fit(cov_type="cluster", cov_kwds={"groups": g.SG_ID})
        say(f"\n== {label}: {y} ~ {x} + 시군 FE + 권역x기간 FE  (n={int(m.nobs)}, 시군 {g.SG_ID.nunique()})")
        for v in m.params.index:
            if v.startswith("C(") or v == "Intercept":
                continue
            say(f"   {v:16s} {m.params[v]:+.4f} ({m.bse[v]:.4f}){stars(m.pvalues[v])}")
            mrows.append([label, y, v, m.params[v], m.bse[v], m.pvalues[v], int(m.nobs)])
        if test and "s_zone" in m.params:
            for o in ["s_b1", "s_b2"]:
                t = m.t_test(f"s_zone - {o} = 0")
                say(f"   s_zone = {o}: diff {float(t.effect[0]):+.4f}, p={float(t.pvalue):.3f}")
        return m

    main_ = df[(df.defn == "new") & (df.sigun != "세종시")]
    say(f"\n패널: 시군 {main_.SG_ID.nunique()}, 기간 {main_.period.nunique()}, 권역 {sorted(main_.region.unique())}")
    say("\n기간별 중앙값 (연율 %, 공급은 시군 주택 대비 %/년)")
    say(main_.groupby("period")[["g_pop", "g_old", "rel_old", "d_old65", "s_old", "s_zone", "s_b1", "s_b2",
                                 "s_b3", "s_b4"]].median().round(3).to_string())
    say("\n기간별 공급 합계 비중 (주택 증가분, 시군 합)")
    tot = main_.assign(**{t: main_[t] * main_.house0 for t in ["s_old", "s_zone"] + list(BANDS)})
    sh = tot.groupby("period")[["s_old", "s_zone"] + list(BANDS)].sum()
    say(sh.div(sh.sum(axis=1), axis=0).round(3).to_string())

    model(main_, "g_old", S, "M1 주모형")
    model(main_, "rel_old", S, "M2 시군 대비")
    model(main_, "d_old65", S, "M3 고령화")
    model(main_, "g_old", A, "M4 신규 주택지 면적", test=False)
    model(main_, "g_old", f"{S} + s_out_lag", "M5 시차 공급")
    model(main_, "g_old", "s_old + s_zone + s_out + s_out:shrink", "M6 축소 시군 상호작용", test=False)
    model(df[df.defn == "new"], "g_old", S, "R1 세종 포함")
    model(df[(df.defn == "l1") & (df.sigun != "세종시")], "g_old", S, "R2 기성시가지=L1 2009")
    model(main_[main_.t0 >= 2015], "g_old", S, "R3 등록센서스 기간만")

    pd.DataFrame(mrows, columns=["model", "y", "term", "coef", "se", "p", "n"]).to_csv(
        os.path.join(OUT, "supply_panel_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "supply_panel.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
