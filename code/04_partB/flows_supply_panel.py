"""Does new housing outside the old core pull residents out of it, or keep them from leaving the 시군?

Joins the MDIS old-core flows (05_flows/flows_old_core_mdis.py) to the supply-location panel (supply_panel.py):
same 시군, same periods, same old-core definition. MDIS years per period: 2000-05 -> 2001-05, 2005-10 -> 2006-10,
2015-19 -> 2016-19, 2019-24 -> 2020-24 (moves inside one 읍면동 are not counted in any year).

Outcomes, per year per 1,000 old-core residents at the start of the period (old_pop0)
  out_new, out_zone, out_rest     old core -> new residential land / new-city zone / rest of the same 시군
  out_inside                      sum of the three
  out_outside                     old core -> anywhere outside the 시군; split out_same_do, out_metro, out_capital,
                                  out_far (elsewhere + unknown)
  in_inside, in_outside           into the old core from the rest of the 시군 / from outside it
  net_old                         in_inside + in_outside - out_inside - out_outside
and for the whole 시군, per 1,000 residents (pop0): sg_out, sg_in, sg_net (moves across the 시군 boundary).

Reading the supply coefficients (s_* = new housing units / 시군 units, %/yr; same model as supply_panel.py:
시군 FE + 권역 x 기간 FE, errors clustered by 시군):
  added pull     supply raises out_new (or out_zone) and leaves out_outside unchanged -> old core loses more
  substitution   supply raises out_new and lowers out_outside about as much -> people who would have left the
                 시군 stay, in new housing; the old core loses the same, the 시군 keeps more
  attraction     supply raises in_outside / sg_in -> new housing also brings people from outside

Output: outputs/partB/flows_supply_panel.csv (panel), flows_supply_models.csv, flows_supply_panel.txt
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\flows_supply_panel.py
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
OUT = os.path.join(paths.OUTPUTS, "partB")
FLOWS = os.path.join(paths.OUTPUTS, "flows")
MDIS_YEARS = {"2000-2005": range(2001, 2006), "2005-2010": range(2006, 2011), "2015-2019": range(2016, 2020),
              "2019-2024": range(2020, 2025)}
OUTSIDE = {"same_do": "out_same_do", "metro": "out_metro", "capital": "out_capital", "elsewhere": "out_far",
           "unknown": "out_far"}
S = "s_old + s_zone + s_b1 + s_b2 + s_b3 + s_b4"
YS = ["out_new", "out_zone", "out_rest", "out_inside", "out_outside", "out_same_do", "out_metro", "out_capital",
      "out_far", "in_inside", "in_outside", "net_old", "sg_out", "sg_in", "sg_net"]


def stars(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


def flow_panel(periods=MDIS_YEARS, val="pers"):
    """Old-core and 시군 flows per 시군 and period (annual means of the years in each period; raw counts of val)."""
    r = pd.read_csv(os.path.join(FLOWS, "mdis_old_core_flows.csv"))
    rows = []
    for per, yrs in periods.items():
        g = r[r.year.isin(yrs)]
        n = len(yrs)
        out = g[g.side == "out"]
        old_out = out[out.part == "old"]
        d = {}
        tab = old_out.groupby(["SG_ID", "other"])[val].sum().unstack(fill_value=0)
        d["out_new"] = tab.get("new", 0)
        d["out_zone"] = tab.get("zone", 0)
        d["out_rest"] = tab.get("rest", 0)
        for k, v in OUTSIDE.items():
            d[v] = d.get(v, 0) + tab.get(k, 0)
        d["in_inside"] = out[(out.other == "old") & (out.part != "old")].groupby("SG_ID")[val].sum()
        d["in_outside"] = g[(g.side == "in") & (g.part == "old")].groupby("SG_ID")[val].sum()
        cross = out[out.other.isin(list(OUTSIDE))]
        d["sg_out"] = cross.groupby("SG_ID")[val].sum()
        d["sg_in"] = g[g.side == "in"].groupby("SG_ID")[val].sum()
        p = pd.DataFrame(d).fillna(0) / n
        p["period"] = per
        rows.append(p.reset_index().rename(columns={"index": "SG_ID"}))
    f = pd.concat(rows, ignore_index=True)
    f["out_inside"] = f.out_new + f.out_zone + f.out_rest
    f["out_outside"] = f.out_same_do + f.out_metro + f.out_capital + f.out_far
    f["net_old"] = f.in_inside + f.in_outside - f.out_inside - f.out_outside
    f["sg_net"] = f.sg_in - f.sg_out
    return f


def main():
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    sp = pd.read_csv(os.path.join(OUT, "supply_panel.csv"))
    sp = sp[(sp.defn == "new") & (sp.sigun != "세종시")]
    f = flow_panel()
    df = sp.merge(f, on=["SG_ID", "period"], how="inner")
    for y in YS:
        base = df.pop0 if y.startswith("sg_") else df.old_pop0
        df[y] = df[y] / base * 1000
    df.to_csv(os.path.join(OUT, "flows_supply_panel.csv"), index=False, encoding="utf-8-sig")
    say(f"패널: 시군 {df.SG_ID.nunique()}, 시군-기간 {len(df)} (세종 제외, supply_panel.py와 같은 표본)")
    say("단위: 원도심 인구 천 명당 연간 이동자 (sg_* 는 시군 인구 천 명당). 같은 동 안 이동은 제외.\n")
    say("기간별 평균")
    say(df.groupby("period")[YS].mean().round(1).T.to_string())

    mrows = []
    say("\n모형: y ~ " + S + " + 시군 FE + 권역x기간 FE, 시군 군집 표준오차")
    say("계수 = 공급 1%p/년 (시군 주택 대비) 늘 때 천 명당 연간 이동자 변화\n")
    tab = {}
    for y in YS:
        g = df.dropna(subset=[y])
        m = smf.ols(f"{y} ~ {S} + C(SG_ID) + C(rp)", data=g).fit(cov_type="cluster", cov_kwds={"groups": g.SG_ID})
        col = {}
        for v in ["s_old", "s_zone", "s_b1", "s_b2", "s_b3", "s_b4"]:
            col[v] = f"{m.params[v]:+.2f}{stars(m.pvalues[v])}"
            mrows.append([y, v, m.params[v], m.bse[v], m.pvalues[v], int(m.nobs)])
        tab[y] = col
    say(pd.DataFrame(tab).T.to_string())

    say("\n대체 검정: 같은 공급이 원도심 -> 시군 안 이동과 원도심 -> 시군 밖 이동을 얼마나 바꾸는가")
    say("(out_inside + out_outside 의 계수 = 원도심 총 전출 변화. 0이면 행선지만 바뀐 것)")
    g = df.assign(out_all=df.out_inside + df.out_outside)
    for v in ["s_zone", "s_b1", "s_b2", "s_b3", "s_b4"]:
        res = {}
        for y in ["out_inside", "out_outside", "out_all"]:
            m = smf.ols(f"{y} ~ {S} + C(SG_ID) + C(rp)", data=g).fit(cov_type="cluster",
                                                                     cov_kwds={"groups": g.SG_ID})
            res[y] = (m.params[v], m.bse[v], m.pvalues[v])
        say(f"   {v}: 시군 안 {res['out_inside'][0]:+.2f} ({res['out_inside'][1]:.2f}){stars(res['out_inside'][2])}, "
            f"시군 밖 {res['out_outside'][0]:+.2f} ({res['out_outside'][1]:.2f}){stars(res['out_outside'][2])}, "
            f"총 전출 {res['out_all'][0]:+.2f} ({res['out_all'][1]:.2f}){stars(res['out_all'][2])}")

    say("\n강건성: 등록센서스 기간만 (2015-19, 2019-24)")
    g = df[df.t0 >= 2015]
    tab = {}
    for y in ["out_new", "out_zone", "out_outside", "in_outside", "net_old", "sg_net"]:
        m = smf.ols(f"{y} ~ {S} + C(SG_ID) + C(rp)", data=g).fit(cov_type="cluster", cov_kwds={"groups": g.SG_ID})
        tab[y] = {v: f"{m.params[v]:+.2f}{stars(m.pvalues[v])}" for v in ["s_old", "s_zone", "s_b1", "s_b2", "s_b3",
                                                                          "s_b4"]}
    say(pd.DataFrame(tab).T.to_string())

    pd.DataFrame(mrows, columns=["y", "term", "coef", "se", "p", "n"]).to_csv(
        os.path.join(OUT, "flows_supply_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "flows_supply_panel.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
