"""Part A, first pass: descriptive comparison and long-difference regressions across 비수도권 시군, 2010 -> 2019.

Groups: innovation-city 시군 (inno), industrial supply (complexes designated 2001-2010 >= 1 km2, not inno),
other 시군.

Models (OLS, HC1 standard errors):
  E0  supply designation on prior conditions: ic_any (2001-2010 >= 1 km2) and inno on population change
      2000 -> 2005, extinction risk 2005, log population 2000, 시, 광역시
  E1  sprawl on supply: new-urban rate (new_urb / urb09), log change in urban m2 per person, leapfrog share
  E2  기성시가지 population change 2010 -> 2019 (and 2019 -> 2024) on supply, without and with the 시군's
      own population change (the second isolates redistribution inside the 시군)
Controls: log population 2010, population change 2000 -> 2010 (pre-trend), urban share of land 2009, 시, 광역시.
Robustness: drop 김천시 and 영주시 (large-class 2009 and 2019 maps identical there), drop 세종시.

Input : outputs/partA/sigun_panel.csv
Output: outputs/partA/partA_groups.csv, partA_models.csv, partA_basic.txt
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\partA_basic.py
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
L1_SAME = ["김천시", "영주시"]


def prepare():
    d = pd.read_csv(os.path.join(OUT, "sigun_panel.csv"))
    d["d_pop"] = d.pop2019 / d.pop2010 - 1
    d["d_pop_recent"] = d.pop2024 / d.pop2019 - 1
    d["pre_pop"] = d.pop2010 / d.pop2000 - 1
    d["pre_pop0005"] = d.pop2005 / d.pop2000 - 1
    d["new_rate"] = d.new_urb / d.urb09
    d["g_urb"] = d.urb19 / d.urb09 - 1
    d["d_lpcu"] = np.log(d.pcu19 / d.pcu10)
    d["old_d"] = d.old_pop2019 / d.old_pop2010 - 1
    d["old_d_recent"] = d.old_pop2024 / d.old_pop2019 - 1
    d["old_share10"] = d.old_pop2010 / d.pop2010
    d["new_pop_share19"] = d.new_pop2019 / d.pop2019
    d["urb_share09"] = d.urb09 / d.land_km2
    d["lpop10"] = np.log(d.pop2010)
    d["lpop00"] = np.log(d.pop2000)
    d["ic_rate"] = d.ic_0110 / d.urb09
    d["ic_any"] = (d.ic_0110 >= 1).astype(int)
    d["group"] = np.where(d.inno == 1, "혁신도시", np.where(d.ic_any == 1, "산업단지 공급", "그 외"))
    return d


def main():
    d = prepare()
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    # descriptive groups
    cols = {"n": ("sigun", "count"), "인구변화 10-19": ("d_pop", "mean"), "신규시가지/2009시가지": ("new_rate", "mean"),
            "1인당 시가지 로그변화": ("d_lpcu", "mean"), "비연속 개발 비율": ("leap_share", "mean"),
            "기성시가지 인구변화 10-19": ("old_d", "mean"), "기성시가지 인구변화 19-24": ("old_d_recent", "mean"),
            "탈동조화 비율": ("decouple", "mean"), "세분류 신규개발 19-25 km2": ("l3_patch", "mean")}
    g = d.groupby("group").agg(**cols).round(3)
    g.to_csv(os.path.join(OUT, "partA_groups.csv"), encoding="utf-8-sig")
    say("== 집단별 평균 (비수도권 130개 시군)")
    say(g.T.to_string())
    tot = d[["urb09", "urb19", "new_urb", "pop2010", "pop2019", "old_pop2010", "old_pop2019", "old_pop2024"]].sum()
    say(f"\n합계: 시가지 {tot.urb09:,.0f} -> {tot.urb19:,.0f} km2, 신규 {tot.new_urb:,.0f} km2; 인구 {tot.pop2010:,.0f} -> "
        f"{tot.pop2019:,.0f}; 기성시가지 인구 {tot.old_pop2010:,.0f} -> {tot.old_pop2019:,.0f} -> {tot.old_pop2024:,.0f}")
    say(f"탈동조화(시가지 증가, 인구 비증가) 시군 {int(d.decouple.sum())}개; 인구 감소 시군 {(d.d_pop < 0).sum()}개, "
        f"그중 시가지 증가 {((d.d_pop < 0) & (d.urb19 > d.urb09)).sum()}개")

    ctrl = "lpop10 + pre_pop + urb_share09 + si + metro"
    supply = "ic_0110 + inno + ent"
    specs = [
        ("E0", "ic_any", "pre_pop0005 + er2005 + lpop00 + si + metro"),
        ("E0", "inno", "pre_pop0005 + er2005 + lpop00 + si + metro"),
        ("E1", "new_rate", f"{supply} + {ctrl}"),
        ("E1", "d_lpcu", f"{supply} + {ctrl}"),
        ("E1", "leap_share", f"{supply} + {ctrl}"),
        ("E1", "decouple", f"{supply} + {ctrl}"),
        ("E2", "old_d", f"{supply} + {ctrl}"),
        ("E2", "old_d", f"{supply} + d_pop + {ctrl}"),
        ("E2", "old_d", f"new_rate + d_pop + {ctrl}"),
        ("E2", "old_d_recent", f"{supply} + {ctrl}"),
    ]
    samples = {"all": d, "no 김천·영주": d[~d.sigun.isin(L1_SAME)], "no 김천·영주·세종": d[~d.sigun.isin(L1_SAME + ["세종시"])]}
    rows = []
    for part, y, x in specs:
        for sname, s in samples.items():
            s = s.dropna(subset=[y] + [v.strip() for v in x.split("+")])
            m = smf.ols(f"{y} ~ {x}", data=s).fit(cov_type="HC1")
            for v in m.params.index:
                rows.append([part, y, x, sname, int(m.nobs), round(m.rsquared, 3), v, m.params[v], m.bse[v], m.pvalues[v]])
            if sname == "no 김천·영주":
                say(f"\n== {part} {y} ~ {x}   [{sname}, n={int(m.nobs)}, R2={m.rsquared:.2f}]")
                for v in m.params.index:
                    if v == "Intercept":
                        continue
                    star = "***" if m.pvalues[v] < .01 else "**" if m.pvalues[v] < .05 else "*" if m.pvalues[v] < .1 else ""
                    say(f"   {v:>12} {m.params[v]:+.4f} ({m.bse[v]:.4f}){star}")
    pd.DataFrame(rows, columns=["part", "y", "x", "sample", "n", "r2", "term", "coef", "se", "p"]).to_csv(
        os.path.join(OUT, "partA_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "partA_basic.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
