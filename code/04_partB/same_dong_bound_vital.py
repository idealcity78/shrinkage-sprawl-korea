"""Narrow the same-dong bound (same_dong_bound.py) with expected natural increase from local age structure.

same_dong_bound.py only assumes natural change >= 0 on new residential land and <= 0 in the old core, so every
residual person is treated as a possible hidden move H (old core -> new housing in the same 읍면동). Here the
natural change is estimated instead and taken out of both residuals:
  H <= R_new - NI_new       (new land gains H plus its own natural increase)
  H <= NI_old - R_old       (old core loses H on top of its own natural change)
  H_v  = min(max(R_new - NI_new, 0), max(NI_old - R_old, 0));  H_v2 the same with R_new, NI_new limited to 동 that
  also hold old core (as H_ub2).

Expected natural increase (no outside data): SGIS 집계구 sex x 5-year age tables (2025 boundaries; 2000, 2005,
2010, 2015, 2019, 2020, 2024; N/A cells = 2 as in oa_aging.py). National census survival ratios and the
child-woman ratio are taken from the 집계구 totals of a five-year window,
  S[s, a] = P[s, a + 1](t + 5) / P[s, a](t)   (capped at 1; the 95+ and 100+ bands pooled)
  CWR     = P[0-4](t + 5) / W15-49(t)
and applied to each 집계구: 5-year deaths = sum P[s, a] (1 - S[s, a]), births = CWR x W15-49, NI = births - deaths.
The rate per resident is the mean of the rates from the start- and end-year age structure, so new areas that fill
during the period are rated by who lives there. Windows: 2000-05 and 2005-10 (census), 2015-19 (2015 and 2019
structures, 2015-20 national ratios), 2019-24.
Each 집계구 is placed at an inside point on the 100 m frame (oa_aging.oa_cells) and typed old core / new land / other
by that cell, with the same masks as same_dong_bound.py. Rates per 시군 and type are applied to the grid populations
of the accounts (mean of start and end, times years). A 시군 without a new-land 집계구 gets the 도 mean rate.
Census survival ratios also carry net international migration and coverage change; they are used only as
national age schedules, and the local differences come from the age structure.

Output: outputs/partB/same_dong_bound_vital.csv, same_dong_bound_vital.txt
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\same_dong_bound_vital.py
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
for p in (CODE, os.path.join(CODE, "02_grid"), os.path.join(CODE, "03_partA"), os.path.join(CODE, "05_flows"), HERE):
    sys.path.insert(0, p)
import paths
import sigun
from dong_class import dong_raster
from flows_supply_panel import S, flow_panel, stars
from oa_aging import oa_cells
from same_dong_bound import OLD_DONG, PERIODS, TERMS, grid_accounts, new_flows
from supply_panel import sgis

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partB")
CSV = os.path.join(paths.SGIS, "oa_stats", "csv", "2025년기준_{}년_성연령별인구.csv")
NA_VALUE = 2
NB = 21                                                   # 5-year bands 0-4 ... 100+
MALE = [f"in_age_{i:03d}" for i in range(31, 52)]
FEMALE = [f"in_age_{i:03d}" for i in range(61, 82)]
# grid period -> (start structure, end structure, national window for the age schedules)
WINDOWS = {"2000-2005": (2000, 2005, (2000, 2005)), "2005-2010": (2005, 2010, (2005, 2010)),
           "2015-2019": (2015, 2019, (2015, 2020)), "2019-2024": (2019, 2024, (2019, 2024))}


def read_sex_age(year):
    """집계구 x (male 21 bands, female 21 bands) array."""
    d = pd.read_csv(CSV.format(year), encoding="cp949", header=None, names=["y", "code", "item", "v"], dtype=str)
    d = d[d.item.isin(MALE + FEMALE)]
    d["v"] = pd.to_numeric(d.v, errors="coerce").fillna(NA_VALUE)
    w = d.pivot_table(index="code", columns="item", values="v", aggfunc="sum").reindex(columns=MALE + FEMALE).fillna(0)
    return w


def schedules(t0, t1):
    a0, a1 = read_sex_age(t0).sum(), read_sex_age(t1).sum()
    surv = {}
    for sex, items in (("m", MALE), ("f", FEMALE)):
        p0, p1 = a0[items].values, a1[items].values
        s = np.ones(NB)
        s[:NB - 2] = p1[1:NB - 1] / p0[:NB - 2]
        s[NB - 2:] = p1[NB - 1] / (p0[NB - 2] + p0[NB - 1])          # 95+ -> 100+, pooled
        surv[sex] = np.clip(s, 0, 1)
    w = a0[FEMALE[3:10]].sum()                                       # women 15-49
    cwr = (a1[MALE[0]] + a1[FEMALE[0]]) / w
    return surv, cwr


def ni_5yr(w, surv, cwr):
    """Expected 5-year births, deaths and population per 집계구 from its age structure."""
    deaths = (w[MALE].values * (1 - surv["m"])).sum(axis=1) + (w[FEMALE].values * (1 - surv["f"])).sum(axis=1)
    births = cwr * w[FEMALE[3:10]].sum(axis=1).values
    return pd.DataFrame({"births": births, "deaths": deaths, "pop": w.sum(axis=1).values}, index=w.index)


def oa_types():
    a = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(a["x0"]), int(a["y0"])
    shape = a["urb"].shape
    sg, names, cap = sigun.raster(x0, y0, *shape)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    h00 = sgis("house", 2000, shape, na=0)
    old = (a["urb"] >= 50) & (h00 >= 5) & ~zone
    cells = oa_cells(x0, y0, *shape)
    rc = np.array(list(cells.values()))
    t = pd.DataFrame({"code": list(cells.keys()), "SG_ID": sg[rc[:, 0], rc[:, 1]], "old": old[rc[:, 0], rc[:, 1]]})
    for per, (_, t1, _) in WINDOWS.items():
        new = (h00 < 5) & (sgis("house", t1, shape, na=0) >= 5) & ~zone
        t[f"new_{per}"] = new[rc[:, 0], rc[:, 1]]
    t = t[(t.SG_ID > 0) & ~t.SG_ID.isin(cap)]
    return t.set_index("code")


def rates(types):
    """Annual expected natural increase per resident by 시군, period and type (old / new)."""
    rows, sched = [], {}
    for per, (s0, s1, win) in WINDOWS.items():
        surv, cwr = schedules(*win)
        sched[per] = (surv, cwr)
        e = [ni_5yr(read_sex_age(y), surv, cwr) for y in (s0, s1)]
        ni = (e[0].births - e[0].deaths).add(e[1].births - e[1].deaths, fill_value=0)
        pop = e[0]["pop"].add(e[1]["pop"], fill_value=0)
        d = pd.DataFrame({"ni": ni, "pop": pop}).join(types, how="inner")
        for typ, mask in (("old", d.old), ("new", d[f"new_{per}"])):
            g = d[mask].groupby("SG_ID")[["ni", "pop"]].sum()
            g["rate"] = g.ni / g["pop"] / 5                           # per resident-year
            rows.append(g.assign(period=per, type=typ).reset_index())
    return pd.concat(rows, ignore_index=True), sched


def main():
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    types = oa_types()
    r, sched = rates(types)
    g = grid_accounts()
    f = flow_panel()[["SG_ID", "period", "net_old", "out_new"]].merge(new_flows(), on=["SG_ID", "period"], how="left")
    d = g.merge(f, on=["SG_ID", "period"], how="inner")
    d["net_new"] = d.net_new.fillna(0)
    sp = pd.read_csv(os.path.join(OUT, "supply_panel.csv"))
    region = sp.drop_duplicates("SG_ID").set_index("SG_ID").get("region")
    for typ in ("old", "new"):
        rt = r[r.type == typ][["SG_ID", "period", "rate", "pop"]].rename(columns={"rate": f"rate_{typ}",
                                                                                   "pop": f"oapop_{typ}"})
        d = d.merge(rt, on=["SG_ID", "period"], how="left")
        # 시군 without a placed 집계구 of this type (or very few residents): 도 (region) mean, else overall mean
        thin = d[f"oapop_{typ}"].fillna(0) < 200
        d.loc[thin, f"rate_{typ}"] = np.nan
        if region is not None:
            d["region"] = d.SG_ID.map(region)
            fill = d.groupby(["region", "period"])[f"rate_{typ}"].transform("mean")
            d[f"rate_{typ}"] = d[f"rate_{typ}"].fillna(fill)
        d[f"rate_{typ}"] = d[f"rate_{typ}"].fillna(d.groupby("period")[f"rate_{typ}"].transform("mean"))
    d["ni_old"] = d.rate_old * d.n * (d.old0 + d.old1) / 2
    d["ni_new"] = d.rate_new * d.n * (d.new0 + d.new1) / 2
    d["r_old"] = d.old1 - d.old0 - d.n * d.net_old
    d["r_new"] = d.new1 - d.new0 - d.n * d.net_new
    share = np.where(d.new1 - d.new0 > 0, (d.dnew_mixed / (d.new1 - d.new0)).clip(0, 1), 0)
    d["h_ub"] = np.minimum(d.r_new.clip(lower=0), (-d.r_old).clip(lower=0))
    d["h_ub2"] = np.minimum((d.r_new * share).clip(lower=0), (-d.r_old).clip(lower=0))
    d["h_v"] = np.minimum((d.r_new - d.ni_new).clip(lower=0), (d.ni_old - d.r_old).clip(lower=0))
    d["h_v2"] = np.minimum(((d.r_new - d.ni_new) * share).clip(lower=0), (d.ni_old - d.r_old).clip(lower=0))
    d.to_csv(os.path.join(OUT, "same_dong_bound_vital.csv"), index=False, encoding="utf-8-sig")

    say("같은 동 안 이동 상한 좁히기: 집계구 연령구조로 기대 자연증가를 빼고 다시 계산")
    say("전국 생잔비·아동부녀자비 (집계구 합계, 5년 창)")
    for per, (surv, cwr) in sched.items():
        say(f"  {per}: 아동부녀자비 {cwr:.3f}, 5년 생잔 남 60-64세 {surv['m'][12]:.3f}, 80-84세 {surv['m'][16]:.3f}, "
            f"여 80-84세 {surv['f'][16]:.3f}")
    n = d.groupby("period").n.first()
    t = d.groupby("period")[["old0", "new0", "new1", "ni_old", "ni_new", "r_old", "r_new", "h_ub", "h_ub2", "h_v",
                             "h_v2"]].sum()
    say("\n기대 자연증가 (연, 천 명당; 원도심은 원도심 인구, 신규지는 신규지 평균 인구 기준)")
    say(pd.DataFrame({"원도심": t.ni_old / n / t.old0 * 1000,
                      "신규 주거지": t.ni_new / n / ((t.new0 + t.new1) / 2) * 1000}).round(2).to_string())
    say("\n상한 (원도심 인구 천 명당 연)")
    tab = pd.DataFrame({f"H_ub 기존": t.h_ub, "H_ub2 기존": t.h_ub2, "H_v 자연증가 반영": t.h_v,
                        "H_v2 자연증가 반영(원도심 있는 동)": t.h_v2}).div(t.old0, axis=0).div(n, axis=0) * 1000
    obs = d.assign(o=d.out_new * d.n).groupby("period").o.sum() / t.old0 / n * 1000
    tab["관측 원도심→신규"] = obs
    say(tab.round(2).to_string())

    df = sp[(sp.defn == "new") & (sp.sigun != "세종시")].merge(d.drop(columns=["sigun", "region"], errors="ignore"),
                                                             on=["SG_ID", "period"], how="inner")
    k = 1000 / df.old_pop0
    df["y_net"] = df.net_old * k
    for h in ("h_ub", "h_ub2", "h_v", "h_v2"):
        df[f"y_net_{h}"] = (df.net_old - df[h] / df.n) * k
    ys = {"y_net": "net_old 관측", "y_net_h_ub": "net_old - H_ub (기존)", "y_net_h_ub2": "net_old - H_ub2 (기존)",
          "y_net_h_v": "net_old - H_v (자연증가 반영)", "y_net_h_v2": "net_old - H_v2 (자연증가 반영)"}
    rows = []

    def table(g, title):
        say(f"\n{title}: 시군 {g.SG_ID.nunique()}, 시군-기간 {len(g)}")
        tab = {}
        for y, lab in ys.items():
            m = smf.ols(f"{y} ~ {S} + C(SG_ID) + C(rp)", data=g).fit(cov_type="cluster", cov_kwds={"groups": g.SG_ID})
            tab[lab] = {v: f"{m.params[v]:+.2f}{stars(m.pvalues[v])} ({m.bse[v]:.2f})" for v in TERMS}
            rows.extend(dict(sample=title, y=lab, term=v, coef=m.params[v], se=m.bse[v], p=m.pvalues[v]) for v in TERMS)
        say(pd.DataFrame(tab).T.to_string())

    say("\n공급 모형 (same_dong_bound.py와 같음: 시군 FE + 권역x기간 FE, 시군 군집). 원도심 천 명당 연, 공급 1%p/년")
    table(df, "전 기간")
    table(df[df.t0 >= 2015], "등록센서스 기간만 (2015-19, 2019-24)")
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "same_dong_bound_vital_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "same_dong_bound_vital.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
