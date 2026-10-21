"""Who leaves the old core, and who does new housing pull out of it? Old-core moves by age, 2001-2025.

Age bands of the MDIS movers (age at the move): a00_14, a15_24, a25_39, a40_64, a65p (age_na left out).
  1. 5-year periods: old-core outflow by age and destination (new land, zones, rest of the 시군, other 시군 of the
     도, 광역시, 수도권, elsewhere) and old-core net migration by age
  2. supply models of flows_supply_panel.py by age: y = movers of the band per 1,000 old-core residents at t0, so the
     band coefficients add up to the all-age coefficient (no age-specific population on the grid)
  3. zone sigun before and after the zone opening (zone_event_study.py onsets): net old-core migration by age,
     difference of the treated 시군 against the region-year mean of the other 시군

Output: outputs/partB/flows_age.txt, flows_age_models.csv
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\flows_age.py
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import paths
from flows_supply_panel import S, flow_panel, stars

sys.stdout.reconfigure(encoding="utf-8")
OUT = os.path.join(paths.OUTPUTS, "partB")
FLOWS = os.path.join(paths.OUTPUTS, "flows")
AGES = {"a00_14": "0-14", "a15_24": "15-24", "a25_39": "25-39", "a40_64": "40-64", "a65p": "65+"}
DEST = {"new": "신규개발지", "zone": "혁신·기업도시", "rest": "시군 기타", "same_do": "도 내 타시군", "metro": "인접 광역시",
        "capital": "수도권", "elsewhere": "기타", "unknown": "기타"}
TERMS = ["s_old", "s_zone", "s_b1", "s_b2", "s_b3", "s_b4"]
YS = ["net_old", "out_new", "out_zone", "out_outside", "out_capital"]


def describe(say):
    r = pd.read_csv(os.path.join(FLOWS, "mdis_old_core_flows.csv"))
    r["period"] = r.year.map(lambda y: f"{(y - 1) // 5 * 5 + 1}-{(y - 1) // 5 * 5 + 5}")
    out = r[(r.side == "out") & (r.part == "old") & (r.other != "old")].assign(dest=lambda d: d.other.map(DEST))
    say("1. 원도심 전출자 연령 구성 (%), 행선지별, 2001-05 / 2021-25")
    for per in ["2001-2005", "2011-2015", "2021-2025"]:
        t = out[out.period == per].groupby("dest", sort=False)[list(AGES)].sum()
        t = t.loc[[v for v in dict.fromkeys(DEST.values()) if v in t.index]]
        t.loc["전체"] = t.sum()
        say(f"\n  {per}")
        say((t.div(t.sum(axis=1), axis=0) * 100).rename(columns=AGES).round(1).to_string())

    say("\n원도심 전출 행선지 구성 (%), 연령별: 신규개발지+혁신·기업도시 / 수도권")
    t = out.groupby(["period", "dest"])[list(AGES)].sum()
    tot = t.groupby("period").sum()
    for d in ["신규개발지", "수도권"]:
        x = t.xs(d, level="dest")
        if d == "신규개발지":
            x = x.add(t.xs("혁신·기업도시", level="dest"), fill_value=0)
        say(f"\n  {d}{'+혁신·기업도시' if d == '신규개발지' else ''}")
        say((x / tot * 100).rename(columns=AGES).round(1).to_string())

    inn = pd.concat([r[(r.side == "out") & (r.other == "old") & (r.part != "old")],
                     r[(r.side == "in") & (r.part == "old")]])
    net = inn.groupby("period")[list(AGES)].sum() - out.groupby("period")[list(AGES)].sum()
    pop = pd.read_csv(os.path.join(FLOWS, "mdis_old_core_pop.csv"))
    pop["period"] = pop.year.map(lambda y: f"{(y - 1) // 5 * 5 + 1}-{(y - 1) // 5 * 5 + 5}")
    oldpop = pop.groupby(["period", "year"]).old.sum().groupby("period").mean()
    say("\n원도심 순이동 연령별 (연평균, 원도심 인구 천 명당; 합 = 전체 순이동률)")
    say((net.div(oldpop, axis=0) / 5 * 1000).rename(columns=AGES).round(2).to_string())


def models(say):
    sp = pd.read_csv(os.path.join(OUT, "supply_panel.csv"))
    sp = sp[(sp.defn == "new") & (sp.sigun != "세종시")]
    rows = []
    say("\n2. 공급 모형, 연령별 (원도심 인구 천 명당 연간 이동자; 연령 계수의 합 = 전 연령 계수)")
    say("   y ~ " + S + " + 시군 FE + 권역x기간 FE, 시군 군집")
    for y in YS:
        tab = {}
        for a in ["pers"] + list(AGES):
            f = flow_panel(val=a)
            df = sp.merge(f, on=["SG_ID", "period"], how="inner")
            df[y] = df[y] / df.old_pop0 * 1000
            m = smf.ols(f"{y} ~ {S} + C(SG_ID) + C(rp)", data=df).fit(cov_type="cluster",
                                                                      cov_kwds={"groups": df.SG_ID})
            lab = "전 연령" if a == "pers" else AGES[a]
            tab[lab] = {v: f"{m.params[v]:+.2f}{stars(m.pvalues[v])}" for v in TERMS}
            tab[lab]["평균"] = f"{df[y].mean():.2f}"
            rows += [[y, a, v, m.params[v], m.bse[v], m.pvalues[v], int(m.nobs)] for v in TERMS]
        say(f"\n  {y}")
        say(pd.DataFrame(tab).T.to_string())
    pd.DataFrame(rows, columns=["y", "age", "term", "coef", "se", "p", "n"]).to_csv(
        os.path.join(OUT, "flows_age_models.csv"), index=False, encoding="utf-8-sig")


def zone(say):
    ev = pd.read_csv(os.path.join(OUT, "zone_event_panel.csv"))
    r = pd.read_csv(os.path.join(FLOWS, "mdis_old_core_flows.csv"))
    out = r[(r.side == "out") & (r.part == "old") & (r.other != "old")]
    inn = pd.concat([r[(r.side == "out") & (r.other == "old") & (r.part != "old")],
                     r[(r.side == "in") & (r.part == "old")]])
    ys = {"net": None, "zone": None}
    net = (inn.groupby(["year", "SG_ID"])[list(AGES)].sum()
           .sub(out.groupby(["year", "SG_ID"])[list(AGES)].sum(), fill_value=0))
    oz = out[out.other == "zone"].groupby(["year", "SG_ID"])[list(AGES)].sum()
    d = ev[["SG_ID", "year", "old_pop0", "ry", "treated", "k", "post"]]
    d = d.merge(net.add_prefix("net_").reset_index(), on=["SG_ID", "year"], how="left")
    d = d.merge(oz.add_prefix("zone_").reset_index(), on=["SG_ID", "year"], how="left").fillna(0)
    say("\n3. 혁신·기업도시 입주 전후 (zone_event_study.py 의 pooled 모형: 시군 FE + 권역x연도 FE, 시군 군집)")
    say("   post 계수, 원도심 인구 천 명당 연간; net = 원도심 순이동, zone = 원도심 -> 신도시 전출")
    tab = {}
    for pre in ys:
        col = {}
        for a in AGES:
            y = f"{pre}_{a}"
            d[y] = d[y] / d.old_pop0 * 1000
            m = smf.ols(f"{y} ~ post + C(SG_ID) + C(ry)", data=d).fit(cov_type="cluster",
                                                                      cov_kwds={"groups": d.SG_ID})
            col[AGES[a]] = f"{m.params['post']:+.2f}{stars(m.pvalues['post'])}"
        tab[pre] = col
    say(pd.DataFrame(tab).to_string())


def main():
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    describe(say)
    models(say)
    zone(say)
    with open(os.path.join(OUT, "flows_age.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
