"""Supply-location panel with new housing split into planned housing districts and the rest.

Robustness for flows_supply_panel.py and same_dong_bound_vital.py. The housing added outside the old core and the
new-city zones (s_b1..s_b4 of supply_panel.py, old-core definition "new") is split by whether the cell lies in a
housing-site district (02_grid/housing_districts.py; any district, whatever its start date):
  s_hd_near, s_nh_near    within 2 km of the main old core (s_b1 + s_b2), inside / outside districts
  s_hd_far,  s_nh_far     beyond 2 km (s_b3 + s_b4)
(new units in the part / 시군 units at the start, %/yr). The two halves add up to the s_b* of supply_panel.py,
which is checked.

Question: is the pull of nearby new housing on old-core residents a property of planned estates (택지 / 도시개발 /
공공주택 districts) or of new housing wherever it is built? Outcomes as in flows_supply_panel.py, plus old-core
net migration less the hidden same-동 moves (H_ub: zero natural increase; H_v2: expected natural increase, old-core
동 only) of same_dong_bound(_vital).py. Model: 시군 FE + region x period FE, errors clustered by 시군.

Output: outputs/partB/hd_supply_panel.csv, hd_supply_panel.txt, hd_supply_models.csv
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\hd_supply_panel.py   (add "models" to skip the grid step)
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
for p in (CODE, os.path.join(CODE, "02_grid"), HERE):
    sys.path.insert(0, p)
import paths
from supply_panel import BANDS, CORE_MIN, PERIODS, sgis

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partB")
NEAR, FAR = ["s_b1", "s_b2"], ["s_b3", "s_b4"]
S = "s_old + s_zone + s_hd_near + s_nh_near + s_hd_far + s_nh_far"
TERMS = ["s_hd_near", "s_nh_near", "s_hd_far", "s_nh_far"]
YS = {"out_new": "원도심 -> 신규 주택지", "out_outside": "원도심 -> 시군 밖", "in_outside": "시군 밖 -> 원도심",
      "net_old": "원도심 순이동 (관측)", "y_h_ub": "순이동 - H (자연증가 0)", "y_h_v2": "순이동 - H (둘 다)",
      "sg_net": "시군 순이동"}


def build():
    import sigun
    a = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(a["x0"]), int(a["y0"])
    shape = a["urb"].shape
    sg, names, cap = sigun.raster(x0, y0, *shape)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    hd = np.load(os.path.join(GRID, "hd_zone.npz"))["hid"] > 0
    old = (a["urb"] >= 50) & (sgis("house", 2000, shape, na=0) >= 5) & ~zone
    cl, _ = ndimage.label(old, structure=np.ones((3, 3), bool))
    core = (np.bincount(cl.ravel())[cl] >= CORE_MIN) & (cl > 0)
    dist = ndimage.distance_transform_edt(~core)
    rest = ~old & ~zone
    lab = sg.ravel().astype(np.int64)
    k = int(sg.max()) + 1
    parts = {}
    for b, (lo, hi) in BANDS.items():
        m = rest & (dist > lo) & (dist <= hi)
        parts[f"{b}_hd"], parts[f"{b}_nh"] = (m & hd).ravel(), (m & ~hd).ravel()
    del cl, core, dist, rest, old
    lev = {}
    for y in sorted({y for p in PERIODS for y in p}):
        h = sgis("house", y, shape).ravel().astype(np.float64)
        lev[y] = {t: np.bincount(lab, weights=h * m, minlength=k) for t, m in parts.items()}
    rows = []
    for t0, t1 in PERIODS:
        for i in sorted(names):
            if i in cap:
                continue
            r = dict(SG_ID=i, period=f"{t0}-{t1}")
            for t in parts:
                r[f"d_{t}"] = lev[t1][t][i] - lev[t0][t][i]
            rows.append(r)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "hd_supply_grid.csv"), index=False, encoding="utf-8-sig")


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def main():
    if "models" not in sys.argv[1:]:
        build()
    lines, rows = [], []

    def say(s=""):
        print(s)
        lines.append(s)

    df = pd.read_csv(os.path.join(OUT, "flows_supply_panel.csv"))
    gr = pd.read_csv(os.path.join(OUT, "hd_supply_grid.csv"))
    df = df.merge(gr, on=["SG_ID", "period"], how="left")
    n = df.period.str[-4:].astype(int) - df.t0
    for b in BANDS:
        for s in ("hd", "nh"):
            df[f"{b}_{s}"] = df[f"d_{b}_{s}"] / df.house0 / n * 100
    gap = max(abs(df[f"{b}_hd"] + df[f"{b}_nh"] - df[b]).max() for b in BANDS)
    for s in ("hd", "nh"):
        df[f"s_{s}_near"] = df[[f"{b}_{s}" for b in NEAR]].sum(axis=1)
        df[f"s_{s}_far"] = df[[f"{b}_{s}" for b in FAR]].sum(axis=1)
    v = pd.read_csv(os.path.join(OUT, "same_dong_bound_vital.csv"))[["SG_ID", "period", "n", "h_ub", "h_v2"]]
    df = df.merge(v, on=["SG_ID", "period"], how="left")
    # net_old here is already per 1,000 old-core residents a year
    for h in ("h_ub", "h_v2"):
        df[f"y_{h}"] = df.net_old - df[h] / df.n / df.old_pop0 * 1000
    df.to_csv(os.path.join(OUT, "hd_supply_panel.csv"), index=False, encoding="utf-8-sig")

    say(f"패널: 시군 {df.SG_ID.nunique()}, 시군-기간 {len(df)} (flows_supply_panel.py와 같은 표본); "
        f"주택 지구 안/밖 합과 s_b* 의 최대 차이 {gap:.2e}")
    tot = df.assign(**{c: df[c] * df.house0 for c in TERMS})
    sh = tot.groupby("period")[TERMS].sum()
    say("\n원도심 밖 신규 주택 중 주택 지구 안의 몫 (기간별 합계)")
    for p, r in sh.iterrows():
        say(f"   {p}: 2km 안 {r.s_hd_near / (r.s_hd_near + r.s_nh_near):.1%}, 2km 밖 "
            f"{r.s_hd_far / (r.s_hd_far + r.s_nh_far):.1%}, 전체 "
            f"{(r.s_hd_near + r.s_hd_far) / r.sum():.1%}")
        rows.append(dict(sample="share", y=p, term="hd_share_all", coef=(r.s_hd_near + r.s_hd_far) / r.sum(),
                         se=np.nan, p=np.nan, n=np.nan))
    say(f"\n모형: y ~ {S} + 시군 FE + 권역x기간 FE, 시군 군집. 원도심 천 명당 연, 공급 1%p/년")
    for title, g in [("전 기간", df), ("등록센서스 기간만 (2015-19, 2019-24)", df[df.t0 >= 2015])]:
        say(f"\n{title}: 시군 {g.SG_ID.nunique()}, 시군-기간 {len(g)}")
        tab = {}
        for y, lab in YS.items():
            gg = g.dropna(subset=[y])
            m = smf.ols(f"{y} ~ {S} + C(SG_ID) + C(rp)", data=gg).fit(cov_type="cluster",
                                                                      cov_kwds={"groups": gg.SG_ID})
            col = {t: f"{m.params[t]:+.2f}{stars(m.pvalues[t])} ({m.bse[t]:.2f})" for t in TERMS}
            tt = m.t_test("s_hd_near - s_nh_near = 0")
            col["지구=비지구 (2km 안) p"] = f"{float(tt.pvalue):.3f}"
            tab[lab] = col
            rows.extend(dict(sample=title, y=y, term=t, coef=m.params[t], se=m.bse[t], p=m.pvalues[t],
                             n=int(m.nobs)) for t in TERMS)
            rows.append(dict(sample=title, y=y, term="diff_near", coef=float(np.squeeze(tt.effect)),
                             se=float(np.squeeze(tt.sd)), p=float(tt.pvalue), n=int(m.nobs)))
        say(pd.DataFrame(tab).T.to_string())
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "hd_supply_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "hd_supply_panel.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
