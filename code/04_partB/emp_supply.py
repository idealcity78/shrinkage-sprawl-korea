"""Old-core jobs (second E2 outcome) and a labour-demand control for the supply-location results.

Employees on the 100 m grid (SGIS total; suppressed cells = 1.5) are split into commerce (도소매·숙박음식) and
manufacturing with the 1 km industry shares of grid_industry.py. Per 시군 and year (2000, 2005, 2010, 2015, 2019,
2020, 2024): old-core employees and commerce employees (same old core as supply_panel.py), 시군 employees,
commerce and manufacturing employees.

A. Supply-location panel (periods of supply_panel.py; 시군 FE + 권역 x 기간 FE, errors clustered by 시군)
   g_emp_old, g_comm_old       old-core employees / commerce employees, growth %/yr (log)
   rel_comm_old                g_comm_old - 시군 commerce growth (pp/yr)
B. Demand control: 시군 manufacturing employment growth (g_manuf, %/yr) added to
   g_old (supply_panel.py M1) and to the flow outcomes of flows_supply_panel.py
   (manufacturing jobs answer to plants and industrial land, not to where housing is built, so they stand in for
   local labour demand). 시군 total employment growth (g_emp) is shown as a bound: it partly follows new housing,
   so it over-controls and shows the most that demand could take from the supply terms.
C. New-city zones: log old-core commerce employees and employees on post (year >= opening; openings from
   zone_event_study.py), 시군 FE + 권역 x 연도 FE, with the 1,000-draw permutation test.
The 2019 -> 2020 step in the business census (national employees +9.9 %) falls inside the 2019-24 period and is
taken up by the 권역 x 기간 / 연도 effects.

Output: outputs/partB/emp_supply_panel.csv, emp_sigun_year.csv, emp_supply.txt
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\emp_supply.py
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "02_grid"))
sys.path.insert(0, HERE)
import paths
import sigun
from zone_event_study import N_PERM, fe_projector, stars

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partB")
YEARS = [2000, 2005, 2010, 2015, 2019, 2020, 2024]
PERIODS = {"2000-2005": (2000, 2005), "2005-2010": (2005, 2010), "2015-2019": (2015, 2019),
           "2019-2024": (2019, 2024)}
S = "s_old + s_zone + s_b1 + s_b2 + s_b3 + s_b4"
TERMS = ["s_old", "s_zone", "s_b1", "s_b2", "s_b3", "s_b4"]


def sgis(item, year, shape, na):
    z = np.load(os.path.join(GRID, f"sgis_{item}.npz"))
    a = np.zeros(shape[0] * shape[1], np.float64)
    v = z[f"y{year}_val"]
    a[z[f"y{year}_idx"]] = np.where(v < 0, na, v)
    return a


def sigun_year():
    a = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(a["x0"]), int(a["y0"])
    shape = a["urb"].shape
    sg, _, _ = sigun.raster(x0, y0, *shape)
    lab = sg.ravel().astype(np.int64)
    k = lab.max() + 1
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    old = ((a["urb"] >= 50) & (sgis("house", 2000, shape, 0).reshape(shape) >= 5) & ~zone).ravel()
    ind = np.load(os.path.join(GRID, "ind_share.npz"))
    rr, cc = np.meshgrid(ind["r1k"], ind["c1k"], indexing="ij")
    rows = []
    for y in YEARS:
        e = sgis("emp", y, shape, 1.5)
        cs = np.nan_to_num(ind[f"y{y}_comm"][rr, cc].ravel(), nan=0.0)
        ms = np.nan_to_num(ind[f"y{y}_manuf"][rr, cc].ravel(), nan=0.0)
        d = {"emp": np.bincount(lab, e, k), "comm": np.bincount(lab, e * cs, k),
             "manuf": np.bincount(lab, e * ms, k), "emp_old": np.bincount(lab, e * old, k),
             "comm_old": np.bincount(lab, e * cs * old, k)}
        t = pd.DataFrame(d)
        t["SG_ID"], t["year"] = t.index, y
        rows.append(t[t.SG_ID > 0])
    return pd.concat(rows, ignore_index=True)


def main():
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    sy = sigun_year()
    sy.to_csv(os.path.join(OUT, "emp_sigun_year.csv"), index=False, encoding="utf-8-sig")
    w = sy.set_index(["SG_ID", "year"])
    rows = []
    for per, (t0, t1) in PERIODS.items():
        a, b = w.xs(t0, level="year"), w.xs(t1, level="year")
        g = lambda c: (np.log(b[c].clip(lower=1)) - np.log(a[c].clip(lower=1))) / (t1 - t0) * 100
        rows.append(pd.DataFrame({"SG_ID": a.index, "period": per, "g_emp_old": g("emp_old").values,
                                  "g_comm_old": g("comm_old").values, "g_comm": g("comm").values,
                                  "g_emp": g("emp").values, "g_manuf": g("manuf").values,
                                  "comm_old0": a.comm_old.values}))
    ep = pd.concat(rows, ignore_index=True)
    ep["rel_comm_old"] = ep.g_comm_old - ep.g_comm
    sp = pd.read_csv(os.path.join(OUT, "supply_panel.csv"))
    sp = sp[(sp.defn == "new") & (sp.sigun != "세종시")]
    df = sp.merge(ep, on=["SG_ID", "period"])
    df = df[df.comm_old0 >= 100]
    df.to_csv(os.path.join(OUT, "emp_supply_panel.csv"), index=False, encoding="utf-8-sig")

    def fit(g, y, x):
        g = g.dropna(subset=[y] + [v.strip() for v in x.split("+")])
        return smf.ols(f"{y} ~ {x} + C(SG_ID) + C(rp)", data=g).fit(cov_type="cluster",
                                                                  cov_kwds={"groups": g.SG_ID})

    say(f"A. 원도심 일자리 (시군 {df.SG_ID.nunique()}, 시군-기간 {len(df)}; 원도심 상업 종사자 100명 이상)")
    say("기간별 중앙값 (%/년)")
    say(df.groupby("period")[["g_emp_old", "g_comm_old", "rel_comm_old", "g_emp", "g_manuf"]].median()
        .round(2).to_string())
    tab = {}
    for y in ["g_emp_old", "g_comm_old", "rel_comm_old"]:
        m = fit(df, y, S)
        tab[y] = {v: f"{m.params[v]:+.2f}{stars(m.pvalues[v])}" for v in TERMS}
    say("\n계수: 공급 1%p/년 -> %/년 (시군·권역x기간 FE)")
    say(pd.DataFrame(tab).T.to_string())

    say("\nB. 수요 통제: 시군 제조업 종사자 증가율(g_manuf), 또는 시군 전체 종사자 증가율(g_emp; 새 주택이 부르는 "
        "일자리도 들어 있어 과잉 통제 = 수요가 설명할 수 있는 최대치)")
    fp = pd.read_csv(os.path.join(OUT, "flows_supply_panel.csv"))
    fl = fp.merge(ep[["SG_ID", "period", "g_manuf", "g_emp"]], on=["SG_ID", "period"])
    tab = {}
    for name, data, y in [("g_old (원도심 인구 %/년)", df, "g_old"), ("net_old (원도심 순이동 ‰)", fl, "net_old"),
                          ("out_new", fl, "out_new"), ("out_outside", fl, "out_outside"),
                          ("in_outside", fl, "in_outside"), ("sg_net (시군 순이동 ‰)", fl, "sg_net")]:
        for lab, x in [("통제 전", S), ("+제조업", S + " + g_manuf"), ("+전체 종사자", S + " + g_emp")]:
            m = fit(data, y, x)
            row = {v: f"{m.params[v]:+.2f}{stars(m.pvalues[v])}" for v in TERMS}
            for c in ["g_manuf", "g_emp"]:
                row[c] = f"{m.params[c]:+.2f}{stars(m.pvalues[c])}" if c in x else ""
            tab[(name, lab)] = row
    say(pd.DataFrame(tab).T.to_string())

    say("\nC. 신도시 입주와 원도심 일자리 (로그, 시군·권역x연도 FE, 순열 추론)")
    zp = pd.read_csv(os.path.join(OUT, "zone_event_panel.csv"))
    on = zp.dropna(subset=["onset"]).groupby("SG_ID").onset.first()
    meta = zp.groupby("SG_ID")[["region"]].first()
    zy = sy[sy.SG_ID.isin(meta.index)].merge(meta, left_on="SG_ID", right_index=True)
    zy = zy[zy.comm_old >= 100].copy()
    zy["onset"] = zy.SG_ID.map(on)
    zy["treated"] = zy.onset.notna().astype(int)
    zy["post"] = ((zy.treated == 1) & (zy.year >= zy.onset)).astype(int)
    zy["ry"] = zy.region + "_" + zy.year.astype(str)
    zy["l_comm_old"], zy["l_emp_old"] = np.log(zy.comm_old), np.log(zy.emp_old)
    zy["l_comm_rel"] = zy.l_comm_old - np.log(zy.comm)
    zy = zy.sort_values(["SG_ID", "year"]).reset_index(drop=True)
    rng = np.random.default_rng(20261019)
    ctrl = zy[zy.treated == 0].reset_index(drop=True)
    resid = fe_projector(ctrl)
    ids, onsets = ctrl.SG_ID.unique(), list(on.values)
    plac = []
    for _ in range(N_PERM):
        o = dict(zip(rng.choice(ids, len(onsets), replace=False), rng.permutation(onsets)))
        po = ctrl.SG_ID.map(o)
        plac.append(resid(((po.notna()) & (ctrl.year >= po)).astype(float).values))
    for y in ["l_emp_old", "l_comm_old", "l_comm_rel"]:
        m = smf.ols(f"{y} ~ post + C(SG_ID) + C(ry)", data=zy).fit(cov_type="cluster",
                                                                   cov_kwds={"groups": zy.SG_ID})
        b = m.params["post"]
        yr = resid(ctrl[y].values)
        pb = np.array([(d @ yr) / (d @ d) for d in plac])
        say(f"   {y:11s} {b:+.3f} (군집 SE {m.bse['post']:.3f}{stars(m.pvalues['post'])})  "
            f"순열 p={(np.abs(pb) >= abs(b)).mean():.3f}")
    say("   (l_comm_rel = 원도심 상업 종사자의 시군 상업 종사자 대비 로그 비율)")
    with open(os.path.join(OUT, "emp_supply.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
