"""Vacant and unsold housing by 시군, 2005-2025: is new supply filled while older housing empties?

Sources (code/00_data/fetch_kosis_housing.py, data_work/housing/):
  DT_1JU0511 (2005) and DT_1JU1012 (2010)   census vacant housing by reason (미분양미입주 = new units not yet sold or
                                             moved into) and, for 2010, by how long empty
  DT_1JU1512 (2015-2025)                    register-census vacant housing by construction year
  DT_1YL202005 (2015-2025)                  all housing units (denominator)
  DT_MLTM_2082, DT_MLTM_5328 (2007-2026)    unsold and unsold-after-completion housing, monthly (December used)
KOSIS 시군구 are mapped to the study's 시군 (2022 boundaries; 광역시 and 세종 as one unit except 울주군, 군위군;
마산·진해 -> 창원, 청원 -> 청주, 연기·조치원 -> 세종, 북·남제주 -> 제주·서귀포). Groups as in supply_demand.py.

Questions
  1. levels      vacancy rate by group and year; share of vacant units that are new and unsold (2005, 2010) or built in
                 the last five years (2015-) versus old (built before 2000)
  2. location    annual 시군 panel 2015-2025: does a larger addition of housing units raise the number of vacant OLD
                 units (built before 2000), given household change? y = change in old vacant units per 1,000 units,
                 x = change in all units per 1,000 units, 시군 FE + 권역 x 연도 FE, by group
  3. unsold      unsold and unsold-after-completion units per 1,000 units by group, 2007-2025

Output: outputs/partA/vacancy_sigun.csv, vacancy.txt, vacancy_models.csv
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\vacancy.py
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
H = os.path.join(paths.WORK, "housing")
OUT = os.path.join(paths.OUTPUTS, "partA")
METRO = {"11": "서울특별시", "21": "부산광역시", "22": "대구광역시", "23": "인천광역시", "24": "광주광역시",
         "25": "대전광역시", "26": "울산광역시", "29": "세종시"}
SHORT = {"서울": "11", "부산": "21", "대구": "22", "인천": "23", "광주": "24", "대전": "25", "울산": "26", "세종": "29",
         "경기": "31", "강원": "32", "충북": "33", "충남": "34", "전북": "35", "전남": "36", "경북": "37", "경남": "38",
         "제주": "39"}
OLD_UNIT = {"마산시": "창원시", "진해시": "창원시", "청원군": "청주시", "연기군": "세종시", "조치원읍": "세종시",
            "당진군": "당진시", "여주군": "여주시", "북제주군": "제주시", "남제주군": "서귀포시"}
ORDER = ["감소", "정체", "성장", "광역시", "수도권"]


def unit(sido, name):
    name = str(name).strip()
    if name in ("울주군", "군위군"):
        return name
    if sido in METRO:
        return METRO[sido]
    if name == "고성군":
        return "강원고성군" if sido == "32" else "경남고성군"
    return OLD_UNIT.get(name, name)


def census(tbl, cols):
    """Rows of a census table at 시군구 (no 구 under a 시, no 동/읍/면 parts), mapped to 시군."""
    d = pd.read_csv(os.path.join(H, f"{tbl}.csv"), dtype={"C1": str, "C2": str})
    d = d[d.C1.str.len() == 5]
    d = d[~d.C1.str[2:].isin(["003", "004", "005"])]
    parent = set(d.C1[d.C1.str[-1] == "0"])
    d = d[~((d.C1.str[-1] != "0") & (d.C1.str[:4] + "0").isin(parent))]
    d["sigun"] = [unit(c[:2], n) for c, n in zip(d.C1, d.C1_NM)]
    return d


def mltm(tbl):
    d = pd.read_csv(os.path.join(H, f"{tbl}.csv"), dtype={"PRD_DE": str})
    d = d[~d.C2_NM.isin(["계", "합계"]) & (d.PRD_DE.str[4:] == "12")]
    d["sigun"] = [unit(SHORT.get(s, ""), n) for s, n in zip(d.C1_NM, d.C2_NM)]
    d["year"] = d.PRD_DE.str[:4].astype(int)
    return d.groupby(["sigun", "year"]).DT.sum()


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def fmt(m, v):
    return f"{m.params[v]:+.3f} ({m.bse[v]:.3f}){stars(m.pvalues[v])}"


def main():
    lines, rows = [], []

    def say(s=""):
        print(s)
        lines.append(s)

    sp = pd.read_csv(os.path.join(OUT, "supply_demand_panel.csv"))
    info = sp.groupby("sigun")[["SG_ID", "group", "region"]].first()
    lv = pd.read_csv(os.path.join(OUT, "supply_demand_levels.csv")).merge(info[["SG_ID"]].reset_index(), on=["SG_ID",
                                                                                                         "sigun"])
    grid = lv.pivot_table(index="sigun", columns="year", values=["house", "hh"])

    # 2005, 2010: vacant by reason (all housing types)
    v05 = census("DT_1JU0511", None)
    v05 = v05[v05.C2_NM.str.startswith("합계")].pivot_table(index="sigun", columns="ITM_NM", values="DT", aggfunc="sum")
    v10 = census("DT_1JU1012", None)
    v10 = v10[v10.C2_NM == "계"].pivot_table(index="sigun", columns="ITM_NM", values="DT", aggfunc="sum")
    # 2015-2025: vacant by construction year, all types
    v15 = census("DT_1JU1512", None)
    v15 = v15[v15.C2_NM == "주택_계"]
    v15["yr"] = v15.PRD_DE.astype(int)
    b = v15.ITM_NM.str.extract(r"(\d{4})")[0].astype(float)
    built = np.where(v15.ITM_NM.str.contains("이전"), 1979, b)
    v15["built"] = built
    den = pd.read_csv(os.path.join(H, "DT_1YL202005.csv"), dtype={"C1": str})
    den = den[den.ITM_NM.str.startswith("전체주택")]
    # 광주·전남 carry a "12" prefix (1224, 1236010); 세종 has only its 시도 row
    den["C1"] = np.where(den.C1.str.startswith("12") & den.C1.str.len().isin([4, 7]), den.C1.str[2:], den.C1)
    den = den[(den.C1.str.len() == 5) | (den.C1 == "29")]
    den["sigun"] = [unit(c[:2], n) for c, n in zip(den.C1, den.C1_NM)]
    # DT_1YL202005 lists 구 under a 시 as well as the 시; keep the larger 시 rows by dropping 구 of non-metro 시도
    den = den[~((~den.C1.str[:2].isin(METRO)) & den.C1_NM.str.endswith("구"))]
    den["yr"] = den.PRD_DE.astype(int)
    units = den.groupby(["sigun", "yr"]).DT.sum()

    rec = []
    for (s, y), g in v15.groupby(["sigun", "yr"]):
        allv = g.loc[g.ITM_NM == "계", "DT"].sum()
        sub = g[g.ITM_NM != "계"]
        rec.append(dict(sigun=s, year=y, vac=allv, vac_new5=sub.loc[sub.built >= y - 5, "DT"].sum(),
                        vac_old=sub.loc[sub.built < 2000, "DT"].sum(), vac_old90=sub.loc[sub.built < 1990, "DT"].sum()))
    v = pd.DataFrame(rec)
    v["units"] = [units.get((s, y), np.nan) for s, y in zip(v.sigun, v.year)]
    v = v.merge(info.reset_index(), on="sigun", how="left")
    miss = sorted(set(v.sigun) - set(info.index))
    v = v.dropna(subset=["group"])
    v.to_csv(os.path.join(OUT, "vacancy_sigun.csv"), index=False, encoding="utf-8-sig")
    say(f"빈집 자료를 연구 시군에 연결: 2015-2025 시군 {v.sigun.nunique()}, 연결 안 된 이름 {miss[:10]}")

    say("\n1. 빈집 비율 (빈집 / 주택, 집단 합계, %)")
    t = {}
    for y, src, col in [(2005, v05, "미거주 주택(빈집)"), (2010, v10, "미거주 주택(빈집)")]:
        x = src[[col]].join(info).join(grid[("house", y)].rename("house"))
        g = x.groupby("group")
        t[y] = g[col].sum() / g.house.sum() * 100
    for y in (2015, 2019, 2024, 2025):
        g = v[v.year == y].groupby("group")
        t[y] = g.vac.sum() / g.units.sum() * 100
    say(pd.DataFrame(t).reindex(ORDER).round(1).to_string())
    say("   (2005·2010 분모는 SGIS 격자 주택, 2015 이후 분모는 KOSIS 전체주택. 2005·2010은 현장조사, 2015 이후 등록센서스)")

    say("\n   빈집 가운데 새 주택 비중: 2005·2010 = '미분양·미입주' 사유, 2015 이후 = 최근 5년 안에 지은 주택 (%)")
    t = {}
    for y, src, col in [(2005, v05, "미분양미입주"), (2010, v10, "미거주 주택(빈집)사유-미분양미입주")]:
        x = src.join(info)
        g = x.groupby("group")
        t[y] = g[col].sum() / g["미거주 주택(빈집)"].sum() * 100
    for y in (2015, 2019, 2024):
        g = v[v.year == y].groupby("group")
        t[y] = g.vac_new5.sum() / g.vac.sum() * 100
    say(pd.DataFrame(t).reindex(ORDER).round(1).to_string())
    say("\n   빈집 가운데 2000년 전에 지은 주택 비중 (%), 그리고 주택 천 호당 2000년 전 주택 빈집")
    t = {}
    for y in (2015, 2019, 2024):
        g = v[v.year == y].groupby("group")
        t[f"비중 {y}"] = g.vac_old.sum() / g.vac.sum() * 100
        t[f"천 호당 {y}"] = g.vac_old.sum() / g.units.sum() * 1000
    say(pd.DataFrame(t).reindex(ORDER).round(1).to_string())
    x = v10.join(info)
    g = x.groupby("group")
    say("\n   2010 빈집 가운데 12개월 이상 빈 주택 비중 (%): " + ", ".join(
        f"{k} {val:.1f}" for k, val in (g["비어있는 기간-12개월 이상"].sum() / g["미거주 주택(빈집)"].sum() * 100)
        .reindex(ORDER).items()))

    # 2. location: annual panel 2015-2025
    p = v.sort_values(["sigun", "year"]).copy()
    p["d_units"] = p.groupby("sigun").units.diff()
    p["units_l"] = p.groupby("sigun").units.shift()
    for c in ("vac", "vac_old", "vac_new5", "vac_old90"):
        p[f"d_{c}"] = p.groupby("sigun")[c].diff() / p.units_l * 1000
    p["s"] = p.d_units / p.units_l * 1000
    hh = lv.pivot_table(index="sigun", columns="year", values="hh")
    p["d_hh"] = [((hh.loc[s, y] - hh.loc[s, y - 1]) / p_ * 1000) if s in hh.index and y in hh and y - 1 in hh
                 else np.nan for s, y, p_ in zip(p.sigun, p.year, p.units_l)]
    p["ry"] = p.region + "_" + p.year.astype(str)
    p = p.dropna(subset=["s", "d_vac_old"])
    p = p[p.s.between(-100, 200)]
    say("\n2. 위치의 문제: 주택이 더 늘어난 해에 오래된(2000년 전) 주택의 빈집이 더 늘어나는가 (2016-2025, 시군 연 패널)")
    say("   y = 빈집 변화 / 직전 주택 x 1000, s = 주택 순증 / 직전 주택 x 1000, 시군 FE + 권역 x 연도 FE, 시군 군집")
    for grp in [["감소", "정체", "성장"], ["감소"], ["정체"], ["성장"], ["광역시", "수도권"]]:
        g = p[p.group.isin(grp)]
        res = []
        for y in ("d_vac", "d_vac_old", "d_vac_new5"):
            m = smf.ols(f"{y} ~ s + C(sigun) + C(ry)", data=g).fit(cov_type="cluster", cov_kwds={"groups": g.sigun})
            res.append(f"{y} {fmt(m, 's')}")
            rows.append(["location", "+".join(grp), y, m.params["s"], m.bse["s"], m.pvalues["s"], int(m.nobs)])
        say(f"   {'·'.join(grp):10s} (시군 {g.sigun.nunique()}): " + ", ".join(res))
    g = p[p.group.isin(["감소", "정체", "성장"])].dropna(subset=["d_hh"])
    m = smf.ols("d_vac_old ~ s + d_hh + C(sigun) + C(ry)", data=g).fit(cov_type="cluster",
                                                                       cov_kwds={"groups": g.sigun})
    say(f"   비수도권 도 시군, 가구 변화 통제 (2020-2024): d_vac_old ~ s {fmt(m, 's')}, d_hh {fmt(m, 'd_hh')}")
    rows.append(["location_hh", "nonmetro", "d_vac_old", m.params["s"], m.bse["s"], m.pvalues["s"], int(m.nobs)])

    # 3. unsold
    us, uc = mltm("DT_MLTM_2082"), mltm("DT_MLTM_5328")
    say("\n3. 미분양 (12월 말, 주택 천 호당; 분모는 SGIS 격자 주택의 가장 가까운 해)")
    near = {y: min([2005, 2010, 2015, 2019, 2020, 2021, 2022, 2023, 2024], key=lambda a: abs(a - y)) for y in
            range(2007, 2026)}
    rec = []
    for (s, y), val in us.items():
        if s in info.index and 2007 <= y <= 2025:
            rec.append(dict(sigun=s, year=y, unsold=val, unsold_done=uc.get((s, y), np.nan),
                            house=grid.loc[s, ("house", near[y])] if s in grid.index else np.nan))
    u = pd.DataFrame(rec).merge(info.reset_index(), on="sigun")
    t = {}
    for y in (2008, 2010, 2013, 2016, 2019, 2022, 2025):
        g = u[u.year == y].groupby("group")
        t[f"미분양 {y}"] = g.unsold.sum() / g.house.sum() * 1000
    say(pd.DataFrame(t).reindex(ORDER).round(1).to_string())
    t = {}
    for y in (2008, 2010, 2013, 2016, 2019, 2022, 2025):
        g = u[u.year == y].groupby("group")
        t[f"준공후 {y}"] = g.unsold_done.sum() / g.house.sum() * 1000
    say(pd.DataFrame(t).reindex(ORDER).round(2).to_string())
    say("   미분양이 한 해라도 주택 천 호당 10호를 넘은 시군 비율 (2007-2025, %): " + ", ".join(
        f"{k} {val:.0f}" for k, val in (u.assign(r=u.unsold / u.house * 1000).groupby(["group", "sigun"]).r.max()
                                        .gt(10).groupby("group").mean() * 100).reindex(ORDER).items()))
    u.to_csv(os.path.join(OUT, "unsold_sigun.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(rows, columns=["block", "sample", "y", "coef", "se", "p", "n"]).to_csv(
        os.path.join(OUT, "vacancy_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "vacancy.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
