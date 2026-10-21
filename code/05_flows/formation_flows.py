"""Formation period (2000s-2025): where did new-city residents come from, at 시군 level? (KOSIS 국내인구이동통계)

Input : data_work/flows/kosis.sqlite (fetch_kosis.py); outputs/partB/supply_panel.csv; grid100 (zone and
        old-core population as in supply_panel.py)
KOSIS 시군구 codes are matched to the study's 시군 by name: 구 of a 시 (e.g. 전주시 완산구) join their 시, 구 of a
광역시 join the 광역시, 고성군 by 시도 code. Moves between two 구 of one 시 count as moves inside the 시군.

A. Case 시군 (with an innovation / enterprise city zone), each year 2012-2025 (od_sgg):
   in / out / net moves by partner: same_do (other 시군 of the same 도), metro (광역시 / 세종 of the region),
   capital (서울·인천·경기), elsewhere; and moves inside the 시군.
B. Accounting on the grid periods 2010-15, 2015-19, 2019-24 for the case 시군:
   zone, old-core and rest population change (SGIS grid), 시군 net migration (sgg_moves 순이동, sum of the
   years after the start year up to the end year), extra moves inside the 시군 over the 2008-2012 average
   (시도내이동-시군구내, plus moves between 구 of one 시). Anyone who moved from the old core (or anywhere in the 시군) into the zone is one such move,
   so extra inside moves bound the zone growth that can have come from inside the 시군. The 2008-2012 level is
   scaled by the trend of the control 시군 (inside moves fell everywhere after 2010):
     inside_max = min(zone growth, extra inside moves);  outside_min = 1 - inside_max / zone growth.
C. All 시군, supply-location panel (supply_panel.py periods and FE): net migration rate and inside-move rate
   (% of start population per year) on the supply terms. If a new-city unit brings people from outside the
   시군, it raises net migration; if it only reshuffles residents, it raises inside moves but not net migration.

Output: outputs/flows/formation_case_od.csv, formation_accounting.csv, formation_panel_models.csv,
        formation_flows.txt
Run with ArcGIS Pro Python:  propy.bat code\\05_flows\\formation_flows.py
"""
import os
import sqlite3
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths
from zone_pop import zone_old_rest

sys.stdout.reconfigure(encoding="utf-8")
DB = os.path.join(paths.WORK, "flows", "kosis.sqlite")
PANEL = os.path.join(paths.OUTPUTS, "partB", "supply_panel.csv")
OUT = os.path.join(paths.OUTPUTS, "flows")
METRO_CD = {"11": "서울특별시", "26": "부산광역시", "27": "대구광역시", "28": "인천광역시", "29": "광주광역시",
            "30": "대전광역시", "31": "울산광역시", "36": "세종시"}
DO_OF = {"42": "강원", "51": "강원", "43": "충북", "44": "충남", "45": "전북", "52": "전북", "46": "전남", "47": "경북",
         "48": "경남", "50": "제주", "41": "경기"}
CAPITAL = {"11", "28", "41"}
NEAR_METRO = {"전남": {"29"}, "경남": {"26", "31"}, "경북": {"27"}, "충남": {"30", "36"}, "충북": {"30", "36"},
              "전북": set(), "강원": set(), "제주": set()}
CASES = ["원주시", "충주시", "진천군", "음성군", "전주시", "완주군", "나주시", "김천시", "진주시", "서귀포시"]
GRID_PERIODS = [(2010, 2015), (2015, 2019), (2019, 2024)]
PANEL_PERIODS = {2000: (2001, 2005), 2005: (2006, 2010), 2015: (2016, 2019), 2019: (2020, 2024)}


def sigun_map(regions):
    """KOSIS 5-digit code -> study 시군 name."""
    nm = dict(regions)
    out = {}
    for cd, n in regions:
        if len(cd) != 5:
            continue
        sd = cd[:2]
        if sd in METRO_CD:
            out[cd] = METRO_CD[sd]
        elif n.endswith("구") and cd[-1] != "0" and nm.get(cd[:4] + "0", "").endswith("시"):
            out[cd] = nm[cd[:4] + "0"]
        elif n == "고성군":
            out[cd] = "강원고성군" if sd in ("42", "51") else "경남고성군"
        else:
            out[cd] = n
    return out


def partner(row_do, sd_other):
    if sd_other in CAPITAL:
        return "capital"
    if sd_other in NEAR_METRO.get(row_do, set()):
        return "metro"
    if DO_OF.get(sd_other) == row_do:
        return "same_do"
    return "elsewhere"


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def main():
    os.makedirs(OUT, exist_ok=True)
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    con = sqlite3.connect(DB)
    od = pd.read_sql("SELECT year, out_cd, out_nm, in_cd, in_nm, moves FROM od_sgg WHERE sex = '0'", con)
    sm = pd.read_sql("SELECT year, cd, nm, item, value FROM sgg_moves WHERE sex = '0' AND age = '000'", con)
    con.close()
    regions = sorted(set(zip(od.out_cd, od.out_nm)) | set(zip(sm.cd, sm.nm)))
    smap = sigun_map(regions)
    od = od[od.out_cd.str.len().eq(5) & od.in_cd.str.len().eq(5)].copy()
    od["out_sg"], od["in_sg"] = od.out_cd.map(smap), od.in_cd.map(smap)
    sm = sm[sm.cd.str.len().eq(5)].copy()
    sm["sg"] = sm.cd.map(smap)
    do_of_sg = {smap[c]: DO_OF.get(c[:2], "") for c in smap}

    # A. case 시군 OD by partner
    rows = []
    for s in CASES:
        d = do_of_sg.get(s, "")
        inn = od[(od.in_sg == s) & (od.out_sg != s)]
        out = od[(od.out_sg == s) & (od.in_sg != s)]
        ins = od[(od.in_sg == s) & (od.out_sg == s)].groupby("year").moves.sum()
        for y in sorted(od.year.unique()):
            r = {"sigun": s, "year": y, "inside": ins.get(y, 0)}
            for p in ["same_do", "metro", "capital", "elsewhere"]:
                fi = inn[(inn.year == y) & (inn.out_cd.str[:2].map(lambda x: partner(d, x)) == p)].moves.sum()
                fo = out[(out.year == y) & (out.in_cd.str[:2].map(lambda x: partner(d, x)) == p)].moves.sum()
                r[f"in_{p}"], r[f"out_{p}"], r[f"net_{p}"] = fi, fo, fi - fo
            rows.append(r)
    a = pd.DataFrame(rows)
    a.to_csv(os.path.join(OUT, "formation_case_od.csv"), index=False, encoding="utf-8-sig")
    say("== A. 혁신·기업도시 시군: 시군 밖과의 순이동 (명, 2012-2025 연도별 합계를 기간으로 묶음)")
    a["per"] = pd.cut(a.year, [2011, 2014, 2019, 2025], labels=["2012-14", "2015-19", "2020-25"])
    say(a.groupby(["sigun", "per"], observed=True)[["net_same_do", "net_metro", "net_capital", "net_elsewhere",
                                                     "inside"]].sum().to_string())

    # B. accounting on grid periods
    pan = pd.read_csv(PANEL, encoding="utf-8-sig")
    pan = pan[pan.defn == "new"]
    zpop = zone_old_rest()  # {(sigun, year): (zone, old, rest)}
    net = sm[sm.item == "T25"].groupby(["sg", "year"]).value.sum()
    t30 = sm[sm.item == "T30"].groupby(["sg", "year"]).value.sum()
    between = od[(od.in_sg == od.out_sg) & (od.in_cd != od.out_cd)].groupby(["in_sg", "year"]).moves.sum()
    # inside moves fell everywhere after 2010: scale each case's 2008-2012 level by the control 시군 trend
    ctrl = set(pan.sigun) - set(CASES) - {"세종시"}
    ct = t30[t30.index.get_level_values(0).isin(ctrl)].groupby(level=1).sum()
    trend = ct / ct.loc[2008:2012].mean()
    say("\n비교 시군 시군 안 이동 추세 (2008-12 = 1): " + ", ".join(f"{y} {trend[y]:.2f}" for y in range(2010, 2025, 2)))
    rows = []
    for s in CASES:
        base = np.mean([t30.get((s, y), np.nan) for y in range(2008, 2013)])
        base_b = between.get((s, 2012), 0) / trend.get(2012, 1)
        for t0, t1 in GRID_PERIODS:
            yrs = range(t0 + 1, t1 + 1)
            z0, o0, r0 = zpop[(s, t0)]
            z1, o1, r1 = zpop[(s, t1)]
            extra = sum(t30.get((s, y), 0) + between.get((s, y), 0) - (base + base_b) * trend.get(y, 1) for y in yrs)
            dz = z1 - z0
            inside_max = min(max(dz, 0), max(extra, 0))
            rows.append(dict(sigun=s, period=f"{t0}-{t1}", d_zone=dz, d_old=o1 - o0, d_rest=r1 - r0,
                             d_total=(z1 + o1 + r1) - (z0 + o0 + r0), net_mig=sum(net.get((s, y), 0) for y in yrs),
                             extra_inside=extra, inside_max=inside_max,
                             outside_min_share=1 - inside_max / dz if dz > 0 else np.nan))
    b = pd.DataFrame(rows)
    b.to_csv(os.path.join(OUT, "formation_accounting.csv"), index=False, encoding="utf-8-sig")
    say("\n== B. 지구 인구 증가와 시군 순이동, 시군 안 추가 이동 (명)")
    say("   inside_max: 지구 증가분 가운데 시군 안에서 옮겨 왔을 수 있는 최대치 (= min(지구 증가, 시군 안 추가 이동))")
    say(b.round(2).to_string(index=False))
    tot = b[b.d_zone > 0].groupby("sigun")[["d_zone", "inside_max", "net_mig", "d_old"]].sum()
    tot["outside_min_share"] = 1 - tot.inside_max / tot.d_zone
    say("\n2010-2024 합계")
    say(tot.round(3).to_string())

    # C. panel: migration outcomes on supply location
    mig, ins_ = [], []
    for _, r in pan.iterrows():
        a0, a1 = PANEL_PERIODS[int(r.t0)]
        n = a1 - a0 + 1
        nm_ = sum(net.get((r.sigun, y), np.nan) for y in range(a0, a1 + 1))
        im = sum(t30.get((r.sigun, y), np.nan) for y in range(a0, a1 + 1))
        mig.append(nm_ / n / r.pop0 * 100)
        ins_.append(im / n / r.pop0 * 100)
    pan["g_netmig"], pan["g_inside"] = mig, ins_
    pan["rp"] = pan.region + "_" + pan.period
    d = pan[(pan.sigun != "세종시")].dropna(subset=["g_netmig"])
    say(f"\n== C. 시군 패널 (시군 {d.SG_ID.nunique()}, 시군·권역×기간 고정효과, 시군 군집 표준오차)")
    S = "s_old + s_zone + s_b1 + s_b2 + s_b3 + s_b4"
    mrows = []
    for y in ["g_netmig", "g_inside", "g_pop"]:
        dd = d.dropna(subset=[y])
        m = smf.ols(f"{y} ~ {S} + C(SG_ID) + C(rp)", data=dd).fit(cov_type="cluster", cov_kwds={"groups": dd.SG_ID})
        say(f"\n{y} (n={int(m.nobs)})")
        for v in S.split(" + "):
            say(f"   {v:8s} {m.params[v]:+.4f} ({m.bse[v]:.4f}){stars(m.pvalues[v])}")
            mrows.append([y, v, m.params[v], m.bse[v], m.pvalues[v], int(m.nobs)])
        tt = m.t_test("s_zone - s_b1 = 0")
        say(f"   s_zone = s_b1: diff {float(tt.effect[0]):+.4f}, p={float(tt.pvalue):.3f}")
    say("   (g_netmig, g_inside: 연간 순이동·시군 안 이동 / 기초 인구 %. 공급은 시군 주택 대비 %/년)")
    say("   주의: KOSIS 순이동은 주민등록 기준이고 격자 인구는 센서스 기준이라 수준이 다를 수 있음")
    pd.DataFrame(mrows, columns=["y", "term", "coef", "se", "p", "n"]).to_csv(
        os.path.join(OUT, "formation_panel_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "formation_flows.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
