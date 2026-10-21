"""Old-core decline against 시군 demand and all new housing supply, not only innovation / enterprise cities.

For each 비수도권 시군 and period (2005 -> 2010 full census; 2015 -> 2024 register census; the 2010 -> 2015
method break is skipped), split the 시군 into
  old    기성시가지: L1 2009 urban >= 50 % cells outside innovation / enterprise zones
  zone   innovation / enterprise city zones (newcity_zone.npz)
  other  everything else (new development around the old core, 읍면, etc.)
and measure
  d_pop, d_hh      시군 population and household change (rate)
  d_old            기성시가지 population change (rate)
  rel_old          (1 + d_old) / (1 + d_pop) - 1: old core against its own 시군
  s_old, s_zone, s_other   housing-unit increase in each part / 시군 housing units at the start
  excess           (housing increase - household increase) / households at the start: supply beyond demand
  newres_zone, newres_other  new residential land, km2: 100 m cells with < 5 units at the start (suppressed
                   cells count as < 5) and >= 10 units at the end
Models (OLS, HC1): d_old and rel_old on demand (d_hh), supply by part, log 2005 population, 시, 광역시;
test s_zone = s_other (is a unit of innovation-city housing different from other new housing?).
Samples: all, without 세종.

Input : data_work/grid100 (l1_2009, newcity_zone, sgis_pop, sgis_hh, sgis_house)
Output: outputs/partB/supply_decomp_panel.csv, supply_decomp_models.csv, supply_decomp.txt
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\supply_decomp.py
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "02_grid"))
import paths
import sigun

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partB")
PERIODS = [(2005, 2010), (2015, 2024)]
TREATED = ["원주시", "진주시", "김천시", "나주시", "진천군", "음성군", "전주시", "완주군", "서귀포시"]
NA_VALUE = 2.5
NEW_FROM, NEW_TO = 5, 10  # units per 100 m cell


def sgis(item, year, shape, na=NA_VALUE):
    z = np.load(os.path.join(GRID, f"sgis_{item}.npz"))
    a = np.zeros(shape[0] * shape[1], np.float32)
    v = z[f"y{year}_val"]
    a[z[f"y{year}_idx"]] = np.where(v < 0, na, v)
    return a.reshape(shape)


def fit(df, y, x, label, say, rows):
    m = smf.ols(f"{y} ~ {x}", data=df).fit(cov_type="HC1")
    say(f"\n== {label}: {y} ~ {x}  (n={int(m.nobs)}, R2={m.rsquared:.3f})")
    for k in m.params.index:
        if k == "Intercept":
            continue
        p = m.pvalues[k]
        star = "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""
        say(f"   {k:14s} {m.params[k]:+.4f} ({m.bse[k]:.4f}){star}")
        rows.append([label, y, k, m.params[k], m.bse[k], p, int(m.nobs), m.rsquared])
    if "s_zone" in m.params and "s_other" in m.params:
        t = m.t_test("s_zone - s_other = 0")
        say(f"   s_zone = s_other: diff {float(t.effect[0]):+.4f}, p={float(t.pvalue):.3f}")
    return m


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
    old = (a["urb"] >= 50) & ~zone
    other = ~old & ~zone
    lab = sg.ravel().astype(np.int64)
    k = sg.max() + 1

    def by(v, mask=None):
        w = v.ravel().astype(np.float64)
        if mask is not None:
            w = w * mask.ravel()
        return np.bincount(lab, weights=w, minlength=k)

    years = sorted({y for p in PERIODS for y in p})
    pop = {y: sgis("pop", y, shape) for y in years}
    hh = {y: sgis("hh", y, shape) for y in years}
    house = {y: sgis("house", y, shape) for y in years}
    land = by(np.ones(shape, np.float32))
    ids = [i for i in sorted(names) if i not in cap and land[i] > 0]

    rows = []
    for t0, t1 in PERIODS:
        P0, P1 = by(pop[t0]), by(pop[t1])
        O0, O1 = by(pop[t0], old), by(pop[t1], old)
        Z0, Z1 = by(pop[t0], zone), by(pop[t1], zone)
        H0, H1 = by(hh[t0]), by(hh[t1])
        U0 = by(house[t0])
        dU = {p: by(house[t1] - house[t0], m) for p, m in [("old", old), ("zone", zone), ("other", other)]}
        dUall = by(house[t1]) - U0
        new_cell = (sgis("house", t0, shape, na=0) < NEW_FROM) & (house[t1] >= NEW_TO)
        nz, no = by(new_cell, zone) * 0.01, by(new_cell, other) * 0.01
        for i in ids:
            nm = names[i]
            rows.append(dict(
                SG_ID=i, sigun=nm, period=f"{t0}-{t1}", t0=t0, t1=t1,
                si=int(nm.endswith("시") or nm == "세종시"), metro=int(nm.endswith("광역시")),
                treated=int(nm in TREATED), pop0=P0[i], pop1=P1[i], old0=O0[i], old1=O1[i],
                zone0=Z0[i], zone1=Z1[i], hh0=H0[i], hh1=H1[i], house0=U0[i],
                d_pop=P1[i] / P0[i] - 1, d_hh=H1[i] / H0[i] - 1,
                d_old=O1[i] / O0[i] - 1 if O0[i] else np.nan,
                s_old=dU["old"][i] / U0[i], s_zone=dU["zone"][i] / U0[i], s_other=dU["other"][i] / U0[i],
                excess=(dUall[i] - (H1[i] - H0[i])) / H0[i],
                newres_zone=nz[i], newres_other=no[i]))
    df = pd.DataFrame(rows)
    df["rel_old"] = (1 + df.d_old) / (1 + df.d_pop) - 1
    df["lpop05"] = np.log(df.groupby("SG_ID").pop0.transform("first"))
    df = df[df.old0 >= 1000].copy()
    df.to_csv(os.path.join(OUT, "supply_decomp_panel.csv"), index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    mrows = []
    for per, g in df.groupby("period"):
        say(f"\n######## {per}: 시군 {len(g)}")
        say("\n중앙값 (전체): " + ", ".join(f"{c} {g[c].median():+.3f}" for c in
                                      ["d_pop", "d_hh", "d_old", "rel_old", "s_old", "s_zone", "s_other", "excess"]))
        say("주택 증가분 구성 (전체 합): 기성시가지 {:.0%}, 혁신·기업도시 {:.0%}, 그 외 {:.0%}".format(
            *(g[c].mul(g.house0).sum() / (g.s_old + g.s_zone + g.s_other).mul(g.house0).sum()
              for c in ["s_old", "s_zone", "s_other"])))
        say(f"신규 주택지 km2 (전체 합): 혁신·기업도시 {g.newres_zone.sum():.1f}, 그 외 {g.newres_other.sum():.1f}")
        g = g.assign(ex3=pd.qcut(g.excess, 3, labels=["low", "mid", "high"]))
        say("\n초과공급 3분위별 중앙값")
        say(g.groupby("ex3", observed=True)[["excess", "d_hh", "d_pop", "d_old", "rel_old", "s_other"]]
            .median().round(3).to_string())
        say("\n처치 시군")
        t = g[g.treated == 1].set_index("sigun")[["d_pop", "d_old", "rel_old", "s_old", "s_zone", "s_other",
                                                   "excess", "newres_zone", "newres_other"]]
        say(t.round(3).to_string())
        ctl = "+ lpop05 + si + metro"
        for samp, gg in [("all", g), ("no세종", g[g.sigun != "세종시"])]:
            lab_ = f"{per} {samp}"
            fit(gg, "d_old", f"d_hh {ctl}", lab_, say, mrows)
            fit(gg, "d_old", f"d_hh + s_old + s_zone + s_other {ctl}", lab_, say, mrows)
            fit(gg, "rel_old", f"s_old + s_zone + s_other {ctl}", lab_, say, mrows)
            fit(gg, "rel_old", f"excess + s_old {ctl}", lab_, say, mrows)
    pd.DataFrame(mrows, columns=["sample", "y", "term", "coef", "se", "p", "n", "r2"]).to_csv(
        os.path.join(OUT, "supply_decomp_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "supply_decomp.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
