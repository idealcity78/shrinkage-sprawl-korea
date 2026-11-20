"""Housing-site districts in the non-capital regions: does designated housing land lead growth or follow it?

The housing counterpart of ic_unmet.py, with the districts of 02_grid/housing_districts.py.

1. District level. Per district on the 100 m grid: mean urban share (large class) in the late 1990s, 2009 and 2019,
   and housing units (SGIS grid) inside it in 2000-2024; realisation = units in the district in 2024 / planned
   units. Summaries by the year the district was started (designation, or the earliest plan date when designation
   is missing) and by the 시군 group of supply_demand.py (감소 / 정체 / 성장). Share of each group's 2010 -> 2024
   housing increase that fell inside housing districts.
2. 시군 level, as for the industrial complexes:
     y = log growth 2010 -> 2024 (x100) of households, residents, housing units
     x = district area started 2006-2012 per 100 km2 of 2009 urban land (hd_0612); 2001-2005 (hd_0105) and before
         2001 (hd_pre) as controls
     controls: the same y over 2000 -> 2005, log residents 2000, region; HC1
   placebo: districts started 2016-2024 (hd_1624) on growth 2010 -> 2024 and 2005 -> 2015; reverse: growth
   2000 -> 2005 predicting hd_0612. Same models with planned units per 100 households of 2005 (u_*) instead of
   area.

Output: outputs/partA/hd_districts_grid.csv, hd_unmet.txt, hd_unmet_models.csv, hd_sigun.csv
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\hd_unmet.py   (add "models" to skip the grid step)
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import paths

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partA")
HOUSE_YEARS = [2000, 2005, 2010, 2015, 2019, 2024]
WINDOWS = [(0, 1990, "~1990"), (1991, 2000, "1991-2000"), (2001, 2005, "2001-05"), (2006, 2010, "2006-10"),
           (2011, 2015, "2011-15"), (2016, 2020, "2016-20"), (2021, 2030, "2021-")]
GROUPS = ["감소", "정체", "성장"]
LAWS = {"taekji": "택지개발촉진법", "urbandev": "도시개발법", "public": "공공주택 특별법", "rental": "민간임대주택법"}


def sgis(item, year, n):
    z = np.load(os.path.join(GRID, f"sgis_{item}.npz"))
    a = np.zeros(n, np.float64)
    v = z[f"y{year}_val"]
    a[z[f"y{year}_idx"]] = np.where(v < 0, 2.5, v)
    return a


def build():
    t = pd.read_csv(os.path.join(OUT, "hd_districts.csv"))
    hid = np.load(os.path.join(GRID, "hd_zone.npz"))["hid"]
    n = hid.size
    lab = hid.ravel().astype(np.int64)
    k = len(t) + 1
    by = lambda w: np.bincount(lab, weights=np.asarray(w, np.float64).ravel(), minlength=k)[1:]
    cells = by(np.ones(n))
    for y in (1999, 2009, 2019):
        u = np.load(os.path.join(GRID, f"l1_{y}.npz"))["urb"]
        t[f"urb{str(y)[2:]}"] = np.divide(by(u), cells, out=np.full(len(t), np.nan), where=cells > 0)
    for y in HOUSE_YEARS:
        t[f"house{y}"] = by(sgis("house", y, n))
        t[f"pop{y}"] = by(sgis("pop", y, n))
    t.to_csv(os.path.join(OUT, "hd_districts_grid.csv"), index=False, encoding="utf-8-sig")


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def fmt(m, v):
    return f"{m.params[v]:+.3f} ({m.bse[v]:.3f}){stars(m.pvalues[v])}"


def main():
    if "models" not in sys.argv[1:]:
        build()
    t = pd.read_csv(os.path.join(OUT, "hd_districts_grid.csv"))
    sp = pd.read_csv(os.path.join(OUT, "supply_demand_panel.csv"))
    grp = sp.groupby("SG_ID")[["group", "region"]].first()
    t = t.join(grp, on="SG_ID")
    t["yr"] = t.desig_yr.fillna(t.start_yr)
    t["window"] = pd.cut(t.yr, [w[0] - 0.5 for w in WINDOWS] + [2030.5], labels=[w[2] for w in WINDOWS])
    lines, rows = [], []

    def say(s=""):
        print(s)
        lines.append(s)

    nc = t[(t.capital == 0) & t.group.isin(GROUPS) & (t.cells > 0)].copy()
    say(f"비수도권 도 시군의 주택 지구 {len(nc)}개 (격자 셀 있음), 지정 면적 {nc.area_km2.sum():,.1f} km2, "
        f"계획 {nc.plan_units.sum():,.0f}호; 법별 {nc.law.map(LAWS).value_counts().to_dict()}; "
        f"지정 연도 없음 {nc.yr.isna().sum()}, 계획 호수 없음 또는 0 {(nc.plan_units.fillna(0) <= 0).sum()}")

    def summary(g):
        w = g.area_km2
        u = g[g.plan_units > 0]
        return pd.Series({
            "지구": len(g), "면적 km2": w.sum(), "계획 호수": g.plan_units.sum(),
            "지정 전 시가화 %": np.average(g.urb99.fillna(0), weights=w),
            "2019 시가화 %": np.average(g.urb19.fillna(0), weights=w),
            "2024 주택 호수": g.house2024.sum(),
            "실현율 %": u.house2024.sum() / u.plan_units.sum() * 100 if len(u) else np.nan,
            "2010-24 주택 증가": (g.house2024 - g.house2010).sum(),
            "준공 %": g.done_yr.notna().mean() * 100})

    say("\n1. 시작 시기별 (비수도권 도 시군; 시가화는 면적 가중)")
    say(nc.groupby("window", observed=True).apply(summary).round(1).to_string())
    say("\n   시군 집단별, 2006년 이후 시작")
    say(nc[nc.yr >= 2006].groupby("group").apply(summary).reindex(GROUPS).round(1).to_string())
    say("\n   시군 집단별, 2005년 이전 시작 (비교)")
    say(nc[nc.yr <= 2005].groupby("group").apply(summary).reindex(GROUPS).round(1).to_string())
    say("\n   법별, 2006년 이후 시작")
    say(nc[nc.yr >= 2006].groupby("law").apply(summary).rename(index=LAWS).round(1).to_string())

    # share of the housing increase inside districts
    lv = pd.read_csv(os.path.join(OUT, "supply_demand_levels.csv")).pivot_table(index="SG_ID", columns="year",
                                                                               values=["pop", "hh", "house"])
    s = sp.groupby("SG_ID")[["sigun", "group", "region"]].first()
    s = s[s.group.isin(GROUPS)]
    pa = pd.read_csv(os.path.join(OUT, "sigun_panel.csv"))[["SG_ID", "urb09"]].set_index("SG_ID")
    s = s.join(pa)
    say("\n   주택 증가 중 주택 지구 안의 몫 (집단 합계)")
    for a, b in [(2000, 2010), (2010, 2024), (2015, 2024)]:
        ins = nc.assign(d=nc[f"house{b}"] - nc[f"house{a}"]).groupby("group").d.sum()
        tot = (lv[("house", b)] - lv[("house", a)]).reindex(s.index).groupby(s.group).sum()
        say(f"   {a}-{b}: " + ", ".join(f"{g} {ins.get(g, 0):,.0f} / {tot[g]:,.0f} = {ins.get(g, 0) / tot[g]:.1%}"
                                      for g in GROUPS))
        for g in GROUPS:
            rows.append(["inside_share", g, f"{a}-{b}", ins.get(g, 0) / tot[g], ins.get(g, 0), tot[g], np.nan])

    # 2. 시군 level
    hh05 = lv[("hh", 2005)]
    for a, b, c in [(2001, 2005, "0105"), (2006, 2012, "0612"), (2016, 2024, "1624"), (0, 2000, "pre")]:
        sel = t[(t.capital == 0) & (t.yr >= max(a, 1)) & (t.yr <= b)]
        s[f"hd_{c}"] = sel.groupby("SG_ID").area_km2.sum().reindex(s.index).fillna(0) / s.urb09 * 100
        s[f"u_{c}"] = sel.groupby("SG_ID").plan_units.sum().reindex(s.index).fillna(0) / hh05.reindex(s.index) * 100
    for v in ["hh", "pop", "house"]:
        s[f"g_{v}"] = np.log(lv[(v, 2024)] / lv[(v, 2010)]).reindex(s.index) * 100
        s[f"pre_{v}"] = np.log(lv[(v, 2005)] / lv[(v, 2000)]).reindex(s.index) * 100
        s[f"g05_{v}"] = np.log(lv[(v, 2015)] / lv[(v, 2005)]).reindex(s.index) * 100
    s["lpop00"] = np.log(lv[("pop", 2000)].reindex(s.index))
    s = s.replace([np.inf, -np.inf], np.nan)
    say(f"\n2. 시군 단위 (비수도권 도 시군 {len(s)}): 주택 지구 지정이 뒤의 성장을 부르는가")
    say("   y = 2010 -> 2024 로그 증가 (x100); 통제: 같은 y의 2000 -> 2005, log 인구 2000, 권역; HC1")
    for x, lab in [("hd", "x = 지구 면적 / 2009 시가지 (%)"), ("u", "x = 계획 호수 / 2005 가구 (%)")]:
        say(f"\n   {lab}: 평균 {x}_0612 {s[f'{x}_0612'].mean():.2f} (지정 시군 {(s[f'{x}_0612'] > 0).sum()}), "
            f"{x}_1624 {s[f'{x}_1624'].mean():.2f} (지정 시군 {(s[f'{x}_1624'] > 0).sum()})")
        for v, vl in [("hh", "가구"), ("pop", "인구"), ("house", "주택")]:
            g = s.dropna(subset=[f"g_{v}", f"pre_{v}"])
            m = smf.ols(f"g_{v} ~ {x}_0612 + {x}_0105 + {x}_pre + pre_{v} + lpop00 + C(region)", data=g).fit(
                cov_type="HC1")
            mp = smf.ols(f"g_{v} ~ {x}_1624 + {x}_0612 + {x}_0105 + {x}_pre + pre_{v} + lpop00 + C(region)",
                         data=g).fit(cov_type="HC1")
            mq = smf.ols(f"g05_{v} ~ {x}_1624 + {x}_pre + pre_{v} + lpop00 + C(region)", data=g).fit(cov_type="HC1")
            say(f"   {vl:4s} 2006-12 시작 {fmt(m, f'{x}_0612')}, 2001-05 {fmt(m, f'{x}_0105')} | 위약: 2016-24 "
                f"시작이 2010-24 성장 {fmt(mp, f'{x}_1624')}, 2005-15 성장 {fmt(mq, f'{x}_1624')}")
            for blk, mm, term in [("growth", m, f"{x}_0612"), ("growth", m, f"{x}_0105"),
                                  ("placebo_1024", mp, f"{x}_1624"), ("placebo_0515", mq, f"{x}_1624")]:
                rows.append([blk, v, term, mm.params[term], mm.bse[term], mm.pvalues[term], int(mm.nobs)])
        say(f"   역방향: {x}_0612 ~ 2000 -> 2005 성장 + log 인구 2000 + 권역")
        for v in ["hh", "pop", "house"]:
            g = s.dropna(subset=[f"pre_{v}"])
            m = smf.ols(f"{x}_0612 ~ pre_{v} + lpop00 + C(region)", data=g).fit(cov_type="HC1")
            say(f"   pre_{v} {fmt(m, f'pre_{v}')}")
            rows.append([f"reverse_{x}", v, f"pre_{v}", m.params[f"pre_{v}"], m.bse[f"pre_{v}"],
                         m.pvalues[f"pre_{v}"], int(m.nobs)])
    s.to_csv(os.path.join(OUT, "hd_sigun.csv"), encoding="utf-8-sig")
    pd.DataFrame(rows, columns=["block", "y", "term", "coef", "se", "p", "n"]).to_csv(
        os.path.join(OUT, "hd_unmet_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "hd_unmet.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
