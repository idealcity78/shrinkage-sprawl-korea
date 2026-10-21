"""Planned population in 도시·군기본계획 against registered population (question 1, "why build": growth-premised plans).

Data (KOSIS org 460, 국토교통부 도시계획현황, fetched by 00_data/fetch_kosis_housing.py)
  TX_315_2009_H1004   plan in force at the end of each year 2005-2025: 수립일, 목표년도, 계획인구
  TX_315_2009_H1004A  land-use plan of that plan: 시가화용지, 시가화예정용지, 보전용지, ... (m2)
A plan vintage is one (시군, 수립일). Its adoption year y0, target year T and planned population P are compared with the
KOSIS registered population (outputs/partA/regpop_sigun.csv, December):
  plan_g    (P / R[y0]) ** (1 / (T - y0)) - 1          planned growth, %/yr
  trend_g   (R[y0] / R[y0 - 5]) ** (1 / 5) - 1         growth in the five years before adoption
  act_g     growth from y0 to min(T, 2025)              realised growth (plans adopted 2020 or earlier)
  attain    R[T] / P                                    for targets reached by 2025
Groups and the land-cover urban change come from outputs/partA/shrink_sprawl_sigun.csv.

Blocks
  1. coverage and plan vintages
  2. planned vs trend vs realised growth by group; share of plans assuming growth while the 시군 was shrinking
  3. does planned growth follow the trend?  plan_g ~ trend_g x group, region FE
  4. land reserve: 시가화예정용지 / 시가화용지 against the planned increase (land-use plan from 2008: earlier rows
     mostly use the pre-2003 land classes)
  5. reserves and actual urbanisation: new urban land 2009 -> 2019 (land cover) ~ planned excess (plan in force 2009)
     + realised population change, region FE (non-capital 도 시군)

Outputs: outputs/partA/plan_pop.txt, plan_vintages.csv, plan_pop_models.csv
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\plan_pop.py
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
OUT = os.path.join(paths.OUTPUTS, "partA")
SRC = os.path.join(paths.WORK, "housing")
ORDER = ["감소", "정체", "성장", "광역시", "수도권"]
METRO = {"서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시"}
OLD_UNIT = {"여주군": "여주시", "당진군": "당진시", "청원군": "청주시", "마산시": "창원시", "진해시": "창원시",
            "세종특별자치시": "세종시", "연기군": "세종시"}
DROP_BEFORE_MERGE = {"마산시", "진해시", "청원군", "연기군"}    # the merged city's own plan represents the unit


def unit(name, prov):
    name = str(name).strip()
    if name == "고성군":
        return "강원고성군" if prov.startswith("강원") else "경남고성군"
    return OLD_UNIT.get(name, name)


def load():
    a = pd.read_csv(os.path.join(SRC, "TX_315_2009_H1004.csv"), dtype=str)
    prov = {c: n for c, n in zip(a.C1, a.C1_NM) if len(c) == 11}
    a = a[(a.C1.str.len() > 11) | a.C1_NM.isin(METRO | {"세종특별자치시"})]
    a = a[~a.C1_NM.str.strip().isin(DROP_BEFORE_MERGE)]
    a["sigun"] = [unit(n, prov.get(c[:11], "")) for c, n in zip(a.C1, a.C1_NM)]
    w = a.pivot_table(index=["sigun", "PRD_DE"], columns="ITM_NM", values="DT_TXT", aggfunc="first").reset_index()
    w["year"] = w.PRD_DE.astype(int)
    w["P"] = pd.to_numeric(w["계획인구"], errors="coerce")
    w["T"] = pd.to_numeric(w["목표년도"].str.extract(r"(\d{4})")[0], errors="coerce")
    w["adopt"] = pd.to_datetime(w["수립일"], errors="coerce")
    w = w.dropna(subset=["P", "T", "adopt"])

    b = pd.read_csv(os.path.join(SRC, "TX_315_2009_H1004A.csv"), dtype=str)
    provb = {c: n for c, n in zip(b.C1, b.C1_NM) if len(c) == 11}
    b = b[(b.C1.str.len() > 11) | b.C1_NM.isin(METRO | {"세종특별자치시"})]
    b = b[~b.C1_NM.str.strip().isin(DROP_BEFORE_MERGE)]
    b["sigun"] = [unit(n, provb.get(c[:11], "")) for c, n in zip(b.C1, b.C1_NM)]
    b["year"] = b.PRD_DE.astype(int)
    b["DT"] = pd.to_numeric(b.DT, errors="coerce")
    lu = b.pivot_table(index=["sigun", "year"], columns="C2_NM", values="DT", aggfunc="first") / 1e6   # km2
    lu = lu.rename(columns={"시가화용지": "urb_plan", "시가화예정용지": "reserve", "보전용지": "conserve"})
    # before 2008 most plans still use the pre-2003 land classes (시가화예정용지 near 0, 보전용지 a tenth of later
    # values), and a few rows are all zero (e.g. 나주 2017): keep the land-use plan from 2008 on with a non-zero total
    bad = (lu.index.get_level_values("year") < 2008) | (lu[["urb_plan", "reserve", "conserve"]].sum(axis=1) == 0)
    lu.loc[bad, ["urb_plan", "reserve", "conserve"]] = np.nan
    return w.merge(lu[["urb_plan", "reserve", "conserve"]].reset_index(), on=["sigun", "year"], how="left")


def vintages(w, rp, info):
    w = w.sort_values(["sigun", "year"])
    v = w.groupby(["sigun", "adopt"]).agg(P=("P", "first"), T=("T", "first"), first_yr=("year", "min"),
                                          urb_plan=("urb_plan", "first"), reserve=("reserve", "first")).reset_index()
    v["y0"] = v.adopt.dt.year

    def R(s, y):
        try:
            return rp.at[s, y]
        except KeyError:
            return np.nan

    v["R0"] = [R(s, y) for s, y in zip(v.sigun, v.y0)]
    v["R_5"] = [R(s, y - 5) for s, y in zip(v.sigun, v.y0)]
    v["y1"] = np.minimum(v["T"], 2025)
    v["R1"] = [R(s, y) for s, y in zip(v.sigun, v.y1)]
    h = v["T"] - v.y0
    v["plan_g"] = ((v.P / v.R0) ** (1 / h) - 1) * 100
    v["trend_g"] = ((v.R0 / v.R_5) ** (1 / 5) - 1) * 100
    v["act_g"] = (((v.R1 / v.R0) ** (1 / (v.y1 - v.y0))) - 1).where(v.y1 - v.y0 >= 5) * 100
    v["attain"] = (v.R1 / v.P).where(v["T"] <= 2025)
    v["excess_pct"] = (v.P / v.R0 - 1) * 100          # planned increase over the plan horizon, % of current pop
    v["reserve_share"] = v.reserve / v.urb_plan * 100
    v["m2_per_added"] = (v.reserve * 1e6 / (v.P - v.R0)).where(v.P > v.R0)
    v = v.merge(info, on="sigun", how="left")
    return v[(v.y0 >= 1995) & v.R0.notna() & (h > 0)]


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def main():
    lines, mrows = [], []

    def say(s=""):
        print(s)
        lines.append(s)

    rp = pd.read_csv(os.path.join(OUT, "regpop_sigun.csv")).set_index(["sigun", "year"]).regpop
    ss = pd.read_csv(os.path.join(OUT, "shrink_sprawl_sigun.csv"))
    info = ss[["sigun", "group", "region"]].drop_duplicates("sigun")
    w = load()
    v = vintages(w, rp, info)
    miss = sorted(set(v.sigun[v.group.isna()]))
    v = v.dropna(subset=["group"])
    v.to_csv(os.path.join(OUT, "plan_vintages.csv"), index=False, encoding="utf-8-sig")

    say("도시·군기본계획 계획인구와 주민등록인구 (KOSIS TX_315_2009_H1004, H1004A; DT_1B040A3)")
    say(f"1. 범위: 연도별 계획 보유 시군 {w.groupby('year').sigun.nunique().min()}~"
        f"{w.groupby('year').sigun.nunique().max()}, 계획(시군 × 수립일) {len(v)}개, 시군 {v.sigun.nunique()}개 "
        f"(연구 시군 {info.sigun.nunique()}개 중). 연구 시군에 붙지 않은 이름: {', '.join(miss) if miss else '없음'}")
    say(f"   수립 연도 {int(v.y0.min())}~{int(v.y0.max())}, 계획 기간 중앙값 {int((v['T'] - v.y0).median())}년")

    say("\n2. 계획 성장률 대 직전 추세·실현 성장률 (%/년, 중앙값; 수립 2000년 이후)")
    g = v[v.y0 >= 2000]
    tab = g.groupby("group").agg(계획수=("P", "size"), 계획성장=("plan_g", "median"), 직전추세=("trend_g", "median"),
                                 실현=("act_g", "median"), 계획증가율=("excess_pct", "median"),
                                 달성률=("attain", "median")).reindex(ORDER)
    say(tab.round(2).to_string())
    for grp in ["감소", "정체"]:
        x = g[(g.group == grp) & (g.trend_g < 0)]
        if len(x):
            say(f"   {grp} 시군에서 직전 5년 인구가 줄던 때 세운 계획 {len(x)}개 중 인구 증가를 계획한 비율 "
                f"{(x.P > x.R0).mean() * 100:.0f}%, 계획인구가 수립 당시 인구의 {x.excess_pct.median():.0f}% 위(중앙값)")
    x = g[g.attain.notna()]
    say("   목표 연도가 지난 계획의 달성률(실제 ÷ 계획인구, 중앙값): " + ", ".join(
        f"{k} {x[x.group == k].attain.median():.2f} (n={int((x.group == k).sum())})" for k in ORDER if (x.group == k).any()))

    say("\n3. 계획 성장률은 직전 추세를 따르는가: plan_g ~ trend_g × 집단 + 권역 FE (비수도권 도 시군, 수립 2000년 이후)")
    d = g[g.group.isin(["감소", "정체", "성장"])].dropna(subset=["plan_g", "trend_g"])
    m = smf.ols("plan_g ~ trend_g + C(region)", d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.sigun)[0]})
    say(f"   기울기 {m.params.trend_g:.2f}{stars(m.pvalues.trend_g)} (se {m.bse.trend_g:.2f}), 절편(추세 0일 때 계획 성장) "
        f"{m.params.Intercept:.2f}{stars(m.pvalues.Intercept)}, n={int(m.nobs)}")
    mrows.append(dict(block="plan_on_trend", term="trend_g", coef=m.params.trend_g, se=m.bse.trend_g,
                      p=m.pvalues.trend_g, n=m.nobs))
    for grp in ["감소", "정체", "성장"]:
        e = d[d.group == grp]
        if len(e) > 10:
            say(f"   {grp}: 추세 {e.trend_g.median():.2f} → 계획 {e.plan_g.median():.2f}, 계획 − 추세 중앙값 "
                f"{(e.plan_g - e.trend_g).median():.2f}%p, 계획이 추세보다 높은 비율 {(e.plan_g > e.trend_g).mean() * 100:.0f}%")

    say("\n4. 시가화예정용지: 계획 증가 인구 1명당 면적, 시가화용지 대비 비율 (중앙값, 수립 2000년 이후)")
    say(g.groupby("group").agg(예정용지_km2=("reserve", "median"), 시가화용지_대비_pct=("reserve_share", "median"),
                               증가1인당_m2=("m2_per_added", "median")).reindex(ORDER).round(1).to_string())
    d = g[g.group.isin(["감소", "정체", "성장"])].dropna(subset=["reserve_share", "excess_pct"])
    m = smf.ols("reserve_share ~ excess_pct + C(region)", d).fit(cov_type="cluster",
                                                                 cov_kwds={"groups": pd.factorize(d.sigun)[0]})
    say(f"   예정용지 비율(%) ~ 계획 증가율(%) + 권역 FE: {m.params.excess_pct:.3f}{stars(m.pvalues.excess_pct)} "
        f"(se {m.bse.excess_pct:.3f}), n={int(m.nobs)}")
    mrows.append(dict(block="reserve_on_excess", term="excess_pct", coef=m.params.excess_pct, se=m.bse.excess_pct,
                      p=m.pvalues.excess_pct, n=m.nobs))

    say("\n5. 계획과 실제 시가화: 2009년에 효력 있던 계획 → 2009→2019 신규 시가지 (대분류 토지피복)")
    p09 = w[w.year == 2009].drop_duplicates("sigun").set_index("sigun")
    s = ss.set_index("sigun")
    d = pd.DataFrame({"group": s.group, "region": s.region,
                      "new_urb": (s.urb19 - s.urb09) / s.urb09 * 100,
                      "g_reg": (pd.Series({k: rp.get((k, 2019)) for k in s.index}) /
                                pd.Series({k: rp.get((k, 2009)) for k in s.index}) - 1) * 100})
    d["plan_excess"] = (p09.P / pd.Series({k: rp.get((k, 2009)) for k in p09.index}) - 1).reindex(d.index) * 100
    d["reserve_share"] = (p09.reserve / p09.urb_plan * 100).reindex(d.index)
    d = d[d.group.isin(["감소", "정체", "성장"])].dropna()
    for f, lab in [("new_urb ~ plan_excess + g_reg + C(region)", "계획 초과(2009 계획인구 ÷ 2009 인구 − 1)"),
                   ("new_urb ~ reserve_share + g_reg + C(region)", "예정용지 ÷ 시가화용지 (2009)")]:
        m = smf.ols(f, d).fit(cov_type="HC1")
        t = f.split("~")[1].split("+")[0].strip()
        say(f"   신규 시가지 증가율(%) ~ {lab}: {m.params[t]:.3f}{stars(m.pvalues[t])} (se {m.bse[t]:.3f}); "
            f"실제 인구 변화 {m.params.g_reg:.3f}{stars(m.pvalues.g_reg)}, n={int(m.nobs)}")
        mrows.append(dict(block="urban_on_plan", term=t, coef=m.params[t], se=m.bse[t], p=m.pvalues[t], n=m.nobs))
    say(f"   감소 시군 2009 계획 초과 중앙값 {d[d.group == '감소'].plan_excess.median():.0f}%, "
        f"성장 시군 {d[d.group == '성장'].plan_excess.median():.0f}%")

    # the 2017-18 revisions (훈령 제900호, 제1133호) cap the target-year population at 105 % of the 도종합계획 지표 and the
    # official projection (110 % for 성장형); compare plans adopted before and after
    say("\n6. 계획인구 상한 도입(2017~18 지침 개정) 전후: 수립 시기별 계획 성장률 (%/년, 중앙값)")
    g = v[v.y0 >= 2005].copy()
    g["era"] = pd.cut(g.y0, [2004, 2012, 2018, 2025], labels=["2005-12", "2013-18", "2019-25"])
    say(g.groupby(["group", "era"], observed=True).agg(
        계획수=("P", "size"), 계획성장=("plan_g", "median"), 직전추세=("trend_g", "median"),
        증가계획비율=("excess_pct", lambda s: (s > 0).mean() * 100)).reindex(ORDER, level=0).round(2).to_string())
    d = g[g.group.isin(["감소", "정체", "성장"])].dropna(subset=["plan_g", "trend_g"]).assign(post=lambda x: (x.y0 >= 2019) * 1)
    m = smf.ols("plan_g ~ post + trend_g + C(region)", d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.sigun)[0]})
    say(f"   2019년 이후 수립(추세·권역 통제): {m.params.post:+.2f}{stars(m.pvalues.post)} %p/년 (se {m.bse.post:.2f}), n={int(m.nobs)}")
    mrows.append(dict(block="cap_2019", term="post", coef=m.params.post, se=m.bse.post, p=m.pvalues.post, n=m.nobs))

    pd.DataFrame(mrows).to_csv(os.path.join(OUT, "plan_pop_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "plan_pop.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
