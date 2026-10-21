"""Do stagnant or declining 시군 build housing beyond demand, and does building first bring growth later?

Per 시군 and period (2000-05, 2005-10, 2010-15, 2015-19, 2019-24), from the SGIS 100 m grid:
  dhouse, dhh           change in housing units and in households
  excess                dhouse - dhh (units added beyond the added households; > 0 = the vacancy stock grows)
  vac                   1 - households / housing units (vacancy proxy; households in non-housing make it a lower bound)
  s_house, g_hh, g_pop  annual growth rates (%/yr) of units, households and residents
Groups by resident registration population 2000 -> 2019 (KOSIS, regpop.py; the grid population has a census ->
register-census break of +4-6 % between 2010 and 2015): 감소 (< -5 %), 정체 (-5 % to +5 %), 성장 (> +5 %); 수도권 시군
kept as a high-demand benchmark (비수도권 = the 9 도, 광역시 and 세종 split as 광역시).

Questions
  1. supply beyond demand   how much of the added housing is matched by added households, by group; share of
                            시군-periods with units growing while households do not
  2. what drives supply     s_house(t) on past demand g_hh(t-1), shrinking status and 권역 x 기간 FE: do declining
                            시군 build more than their demand predicts?
  3. supply-led growth      does supply come first? (a) absorption: g_hh(t), g_pop(t) on s_house(t) with 시군 FE and
                            권역 x 기간 FE (share of new units filled by new households); (b) lead: g_pop(t+1), g_hh(t+1)
                            on s_house(t) controlling g(t); (c) reverse: s_house(t+1) on g_hh(t); (d) 시군 in-migration
                            from outside (MDIS, next period) on s_house(t)
The 2010-15 period spans the change from the full census to the register census; it is kept with 권역 x 기간 FE
and dropped as a robustness check.

Output: outputs/partA/supply_demand_panel.csv, supply_demand.txt, supply_demand_models.csv
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\supply_demand.py   (add "models" to skip the grid step)
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
for p in (CODE, os.path.join(CODE, "02_grid"), os.path.join(CODE, "04_partB"), HERE):
    sys.path.insert(0, p)
import paths

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partA")
PERIODS = [(2000, 2005), (2005, 2010), (2010, 2015), (2015, 2019), (2019, 2024)]
YEARS = [2000, 2005, 2010, 2015, 2019, 2020, 2021, 2022, 2023, 2024]  # all grid years (levels file)
NA = 2.5
SIDO_REGION = {"11": "수도권", "23": "수도권", "31": "수도권", "21": "경남", "26": "경남", "38": "경남", "22": "경북",
               "37": "경북", "24": "전남", "36": "전남", "25": "충남", "29": "충남", "34": "충남", "33": "충북", "32": "강원",
               "35": "전북", "39": "제주"}
METRO_SIDO = {"21", "22", "23", "24", "25", "26", "29"}


def sgis(item, year, shape):
    z = np.load(os.path.join(GRID, f"sgis_{item}.npz"))
    a = np.zeros(shape[0] * shape[1], np.float32)
    v = z[f"y{year}_val"]
    a[z[f"y{year}_idx"]] = np.where(v < 0, NA, v)
    return a.reshape(shape)


def grid_levels():
    """Residents, households and units per 시군 and grid year; 시도 of each 시군 from the 집계구 codes."""
    import sigun
    from collections import Counter
    from oa_aging import oa_cells
    a = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(a["x0"]), int(a["y0"])
    shape = a["urb"].shape
    sg, names, cap = sigun.raster(x0, y0, *shape)
    lab = sg.ravel().astype(np.int64)
    k = int(sg.max()) + 1
    rows = []
    for y in YEARS:
        r = {"year": y, "SG_ID": np.arange(k)}
        for it in ("pop", "hh", "house"):
            r[it] = np.bincount(lab, weights=sgis(it, y, shape).ravel().astype(np.float64), minlength=k)
        rows.append(pd.DataFrame(r))
    g = pd.concat(rows)
    g = g[g.SG_ID > 0]
    g["sigun"] = g.SG_ID.map(names)
    g["capital"] = g.SG_ID.isin(cap).astype(int)
    sido = {}
    for c, (rr, cc) in oa_cells(x0, y0, *shape).items():
        s = int(sg[rr, cc])
        if s:
            sido.setdefault(s, Counter())[str(c)[:2]] += 1
    g["sido"] = g.SG_ID.map({s: c.most_common(1)[0][0] for s, c in sido.items()})
    g.to_csv(os.path.join(OUT, "supply_demand_levels.csv"), index=False, encoding="utf-8-sig")


def panel():
    lv = pd.read_csv(os.path.join(OUT, "supply_demand_levels.csv"), dtype={"sido": str})
    lv = lv[lv["pop"] > 0]
    w = lv.pivot_table(index="SG_ID", columns="year", values=["pop", "hh", "house"])
    info = lv.groupby("SG_ID")[["sigun", "capital", "sido"]].first()
    rows = []
    for t0, t1 in PERIODS:
        n = t1 - t0
        d = pd.DataFrame(index=w.index)
        for it in ("pop", "hh", "house"):
            d[f"{it}0"], d[f"{it}1"] = w[(it, t0)], w[(it, t1)]
            d[f"g_{it}"] = ((d[f"{it}1"] / d[f"{it}0"]) ** (1 / n) - 1) * 100
        d["dhouse"], d["dhh"], d["dpop"] = d.house1 - d.house0, d.hh1 - d.hh0, d.pop1 - d.pop0
        d["excess"] = d.dhouse - d.dhh
        d["vac0"], d["vac1"] = 1 - d.hh0 / d.house0, 1 - d.hh1 / d.house1
        d["period"], d["t0"], d["n"] = f"{t0}-{t1}", t0, n
        rows.append(d.reset_index())
    p = pd.concat(rows, ignore_index=True).merge(info.reset_index(), on="SG_ID")
    p = p.rename(columns={"g_house": "s_house"})
    p["region"] = p.sido.map(SIDO_REGION).fillna("기타")
    p["metro"] = p.sido.isin(METRO_SIDO).astype(int)
    rp = pd.read_csv(os.path.join(OUT, "regpop_sigun.csv")).pivot(index="sigun", columns="year", values="regpop")
    reg = (rp[2019] / rp[2000] - 1).reindex(info.sigun.values)
    reg.index = info.index
    trend = reg.fillna(w[("pop", 2019)] / w[("pop", 2000)] - 1).rename("pop_0019")
    p = p.merge(trend.reset_index(), on="SG_ID")
    p["group"] = np.where(p.capital == 1, "수도권",
                          np.where(p.metro == 1, "광역시",
                                   np.where(p.pop_0019 < -0.05, "감소", np.where(p.pop_0019 <= 0.05, "정체", "성장"))))
    p = p.sort_values(["SG_ID", "t0"])
    for c in ("g_hh", "g_pop", "s_house"):
        p[f"{c}_lag"] = p.groupby("SG_ID")[c].shift(1)
        p[f"{c}_lead"] = p.groupby("SG_ID")[c].shift(-1)
    p["shrink_lag"] = (p.g_pop_lag < 0).astype(float).where(p.g_pop_lag.notna())
    p["rp"] = p.region + "_" + p.period
    return p


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def fmt(m, v):
    return f"{m.params[v]:+.3f} ({m.bse[v]:.3f}){stars(m.pvalues[v])}"


def main():
    if "models" not in sys.argv[1:]:
        grid_levels()
    p = panel()
    p.to_csv(os.path.join(OUT, "supply_demand_panel.csv"), index=False, encoding="utf-8-sig")
    lines, rows = [], []

    def say(s=""):
        print(s)
        lines.append(s)

    order = ["감소", "정체", "성장", "광역시", "수도권"]
    n = p.groupby("group").SG_ID.nunique().reindex(order)
    say("시군 집단 (인구 2000 -> 2019): " + ", ".join(f"{g} {int(v)}" for g, v in n.items()))

    say("\n1. 공급과 수요: 집단별 합계 (기간 합, 천 호/천 가구)")
    t = p.groupby(["group", "period"])[["dhouse", "dhh", "excess", "dpop"]].sum().div(1000).round(1)
    say(t.unstack("period").reindex(order).stack().to_string())
    say("\n   신규 주택 중 늘어난 가구로 채워진 비율 dhh / dhouse (집단 합계)")
    a = (p.groupby(["group", "period"]).dhh.sum() / p.groupby(["group", "period"]).dhouse.sum()).unstack()
    say(a.reindex(order).round(2).to_string())
    say("\n   주택은 늘고 가구는 늘지 않은 시군-기간 비율 (%), 주택 증가가 가구 증가를 넘은 비율 (%)")
    b = p.assign(nodemand=(p.dhouse > 0) & (p.dhh <= 0), over=p.dhouse > p.dhh)
    say(pd.concat({"가구 감소에도 주택 증가": b.groupby(["group", "period"]).nodemand.mean().unstack() * 100,
                   "주택 증가 > 가구 증가": b.groupby(["group", "period"]).over.mean().unstack() * 100}, axis=1)
        .reindex(order).round(0).to_string())
    say("\n   빈집 지표 1 - 가구/주택 (집단 합계, %; 가구에는 주택 외 거처 가구가 포함되므로 하한)")
    v = p.groupby(["group", "period"])[["house0", "hh0", "house1", "hh1"]].sum()
    vt = pd.DataFrame({"t0": (1 - v.hh0 / v.house0) * 100, "t1": (1 - v.hh1 / v.house1) * 100}).unstack("period")
    say(vt.reindex(order).round(1).to_string())

    np_ = p[p.group.isin(["감소", "정체", "성장"])].copy()
    say("\n2. 무엇이 공급을 정하는가 (비수도권 도 시군): s_house(t) ~ 직전 가구 증가 + 같은 기간 가구 증가 + 감소 여부 "
        "+ 권역 x 기간 FE, 시군 군집")
    g = np_.dropna(subset=["g_hh_lag"])
    for lab, f in [("직전 수요만", "s_house ~ g_hh_lag + C(rp)"),
                   ("+감소 시군", "s_house ~ g_hh_lag + shrink_lag + C(rp)"),
                   ("+같은 기간 가구", "s_house ~ g_hh_lag + g_hh + shrink_lag + C(rp)")]:
        m = smf.ols(f, data=g).fit(cov_type="cluster", cov_kwds={"groups": g.SG_ID})
        terms = [v for v in ["g_hh_lag", "g_hh", "shrink_lag"] if v in m.params]
        say(f"   {lab:12s} " + ", ".join(f"{v} {fmt(m, v)}" for v in terms) + f"  상수 포함 R2={m.rsquared:.2f}")
        rows += [["drivers", lab, v, m.params[v], m.bse[v], m.pvalues[v], int(m.nobs)] for v in terms]
    say("   감소 시군(직전 기간 인구 감소)의 평균: 주택 증가율 "
        f"{g[g.shrink_lag == 1].s_house.mean():.2f}%/년, 가구 증가율 {g[g.shrink_lag == 1].g_hh.mean():.2f}%/년; "
        f"비감소 {g[g.shrink_lag == 0].s_house.mean():.2f}, {g[g.shrink_lag == 0].g_hh.mean():.2f}")

    say("\n3. 공급이 먼저인가: 공급이 가구·인구 증가를 부르는가 (비수도권 도 시군)")
    say("   (a) 흡수: g(t) ~ s_house(t) + 시군 FE + 권역 x 기간 FE, 시군 군집. 계수 = 주택 1%p/년 더 늘 때 가구·인구 증가")
    for sample, gg in [("전 기간", np_), ("2010-15 제외", np_[np_.period != "2010-2015"])]:
        out = []
        for y in ["g_hh", "g_pop"]:
            m = smf.ols(f"{y} ~ s_house + C(SG_ID) + C(rp)", data=gg).fit(cov_type="cluster",
                                                                          cov_kwds={"groups": gg.SG_ID})
            out.append(f"{y} {fmt(m, 's_house')}")
            rows.append(["absorb", sample, y, m.params["s_house"], m.bse["s_house"], m.pvalues["s_house"], int(m.nobs)])
        say(f"     {sample:10s} " + ", ".join(out))
    for grp in ["감소", "정체", "성장"]:
        gg = np_[np_.group == grp]
        m = smf.ols("g_hh ~ s_house + C(SG_ID) + C(rp)", data=gg).fit(cov_type="cluster",
                                                                      cov_kwds={"groups": gg.SG_ID})
        say(f"     집단 {grp}: g_hh {fmt(m, 's_house')} (시군 {gg.SG_ID.nunique()})")
        rows.append(["absorb_group", grp, "g_hh", m.params["s_house"], m.bse["s_house"], m.pvalues["s_house"],
                     int(m.nobs)])

    say("\n   (b) 선행: 다음 기간 증가 g(t+1) ~ s_house(t) + g(t) + 권역 x 기간 FE (시군 FE 없는 모형과 있는 모형)")
    say("   (c) 역방향: s_house(t+1) ~ g_hh(t) + s_house(t) + 권역 x 기간 FE")
    gl = np_.dropna(subset=["g_hh_lead"])
    for y, x in [("g_hh_lead", "s_house + g_hh"), ("g_pop_lead", "s_house + g_pop"), ("s_house_lead", "g_hh + s_house")]:
        key = "s_house" if y != "s_house_lead" else "g_hh"
        m0 = smf.ols(f"{y} ~ {x} + C(rp)", data=gl).fit(cov_type="cluster", cov_kwds={"groups": gl.SG_ID})
        m1 = smf.ols(f"{y} ~ {x} + C(SG_ID) + C(rp)", data=gl).fit(cov_type="cluster", cov_kwds={"groups": gl.SG_ID})
        say(f"     {y:13s} ~ {key}: 시군 FE 없음 {fmt(m0, key)}, 시군 FE {fmt(m1, key)}")
        rows += [["lead", y + "|noFE", key, m0.params[key], m0.bse[key], m0.pvalues[key], int(m0.nobs)],
                 ["lead", y + "|FE", key, m1.params[key], m1.bse[key], m1.pvalues[key], int(m1.nobs)]]

    try:
        from flows_supply_panel import flow_panel
        per = {"2000-2005": range(2001, 2006), "2005-2010": range(2006, 2011), "2010-2015": range(2011, 2016),
               "2015-2019": range(2016, 2020), "2019-2024": range(2020, 2025)}
        f = flow_panel(periods=per)[["SG_ID", "period", "sg_in", "sg_out", "sg_net"]]
        q = np_.merge(f, on=["SG_ID", "period"], how="left")
        for c in ("sg_in", "sg_net"):
            q[c] = q[c] / q.pop0 * 1000
            q[f"{c}_lead"] = q.groupby("SG_ID")[c].shift(-1)
        say("\n   (d) 시군 밖에서의 전입 (MDIS, 시군 인구 천 명당 연): 같은 기간과 다음 기간, 시군 FE + 권역 x 기간 FE")
        for y in ["sg_in", "sg_net", "sg_in_lead", "sg_net_lead"]:
            gg = q.dropna(subset=[y])
            ctrl = " + " + y.replace("_lead", "") if y.endswith("_lead") else ""
            m = smf.ols(f"{y} ~ s_house{ctrl} + C(SG_ID) + C(rp)", data=gg).fit(cov_type="cluster",
                                                                                cov_kwds={"groups": gg.SG_ID})
            say(f"     {y:12s} ~ s_house {fmt(m, 's_house')}")
            rows.append(["inmig", y, "s_house", m.params["s_house"], m.bse["s_house"], m.pvalues["s_house"],
                         int(m.nobs)])
    except FileNotFoundError:
        say("   (d) MDIS 이동 결과가 없어 건너뜀")

    pd.DataFrame(rows, columns=["block", "model", "term", "coef", "se", "p", "n"]).to_csv(
        os.path.join(OUT, "supply_demand_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "supply_demand.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
