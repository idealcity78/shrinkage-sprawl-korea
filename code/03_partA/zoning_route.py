"""Where did new urban land form: through the planned route (urban-use zones) or outside it?  (paper 1, follow-up
to plan_event.py)

시가화예정용지 has no map, but reserve land that is used becomes 주거·상업·공업지역 through a 도시관리계획 decision.
So new urban land is split by the zoning in force in 2026 (data_work/grid100/zoning.npz, grid_zoning.py):
  A 주거·상업·공업지역 (urban-use zones: the planned route, whether zoned before or after 2009)
  B 자연녹지지역        C 생산·보전녹지, 도시지역 미세분
  D 계획관리지역        E 생산·보전관리지역        F 그 밖 (농림·자연환경보전지역)
B-F are development without urban-use zoning: development permits in green or management zones.
Each 100 m cell is split by its zoning shares.

Measures per 시군 (groups as in shrink_sprawl.py)
  new urban land 2009 -> 2019 (L1, < 10 % -> >= 50 %), km2 by zone, and its share by zone; outside the 기성시가지
  housing units added 2015 -> 2024 outside the 기성시가지 (SGIS grid), by zone
  availability: zone shares of the land that was not urban in 2009, to read the new-urban shares against
  KOSIS check: increase of 주거·상업·공업지역 2008 -> 2019 (TX_315_2009_H1440) against new urban land in zone A,
  and the change in 시가화예정용지 2009 -> 2019 (H1004A)
Models (non-capital 도 시군): share of new urban land outside zone A ~ group + log new urban area + region FE;
  and ~ 2009 reserve share (시가화예정용지 / 시가화용지), to see whether larger reserves keep development inside the
  planned route.

Outputs: outputs/partA/zoning_route.txt, zoning_route_sigun.csv
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\zoning_route.py
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
for p in (CODE, os.path.join(CODE, "02_grid"), HERE):
    sys.path.insert(0, p)
import paths
from shrink_sprawl import sgis
import plan_pop
import plan_event

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partA")
ORDER = ["감소", "정체", "성장", "광역시", "수도권"]
ROUTES = {"A": ["res", "com", "ind"], "B": ["gnat"], "C": ["gprd", "gcon", "uund"], "D": ["mpln"],
          "E": ["mprd", "mcon"]}
LABEL = {"A": "주거·상업·공업", "B": "자연녹지", "C": "생산·보전녹지 등", "D": "계획관리", "E": "생산·보전관리",
         "F": "농림·보전 등"}


def build():
    import sigun
    l09, l19 = np.load(os.path.join(GRID, "l1_2009.npz")), np.load(os.path.join(GRID, "l1_2019.npz"))
    x0, y0 = int(l09["x0"]), int(l09["y0"])
    shape = l09["urb"].shape
    u09, u19 = l09["urb"].astype(np.int16), l19["urb"].astype(np.int16)
    z = np.load(os.path.join(GRID, "zoning.npz"))
    share = {r: sum(z[g].astype(np.float32) for g in gs) / 100 for r, gs in ROUTES.items()}
    share["F"] = np.clip(1 - sum(share.values()), 0, 1)
    sg, names, _ = sigun.raster(x0, y0, *shape)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    old = (u09 >= 50) & (sgis("house", 2000, shape, na=0) >= 5) & ~zone
    lab = sg.ravel().astype(np.int64)
    k = int(sg.max()) + 1
    by = lambda w: np.bincount(lab, weights=np.asarray(w, np.float64).ravel(), minlength=k)
    new = ((u09 < 10) & (u19 >= 50)).astype(np.float32)
    avail = (u09 < 10).astype(np.float32)
    dh = np.clip(sgis("house", 2024, shape, na=0) - sgis("house", 2015, shape, na=0), 0, None) * ~old
    r = {"SG_ID": np.arange(k)}
    for rt, s in share.items():
        r[f"new_{rt}"] = by(new * s) * 0.01                 # km2
        r[f"avail_{rt}"] = by(avail * s) * 0.01
        r[f"dh_{rt}"] = by(dh * s)
        r[f"old_{rt}"] = by(old * s) * 0.01
    t = pd.DataFrame(r)
    t = t[t.SG_ID > 0]
    t["sigun"] = t.SG_ID.map(names)
    return t


def kosis_check(sig):
    o = plan_event.outcomes().reset_index()
    z = o.pivot_table(index="sigun", columns="year", values="urbzone")
    w = plan_pop.load()
    res = w.pivot_table(index="sigun", columns="year", values="reserve", aggfunc="first")
    upl = w.pivot_table(index="sigun", columns="year", values="urb_plan", aggfunc="first")
    return pd.DataFrame({"zoneA_0819": (z[2019] - z[2008]).reindex(sig),
                         "reserve09": res.get(2009, pd.Series(dtype=float)).reindex(sig),
                         "reserve19": res.get(2019, pd.Series(dtype=float)).reindex(sig),
                         "reserve_share09": (res.get(2009) / upl.get(2009) * 100).reindex(sig)})


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def main():
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    t = build()
    info = pd.read_csv(os.path.join(OUT, "shrink_sprawl_sigun.csv"))[["SG_ID", "group", "region"]]
    t = t.merge(info, on="SG_ID", how="inner")
    t = t.join(kosis_check(t.sigun.values).reset_index(drop=True).set_index(t.index))
    R = list(LABEL)
    t["new_tot"] = t[[f"new_{r}" for r in R]].sum(axis=1)
    t["dh_tot"] = t[[f"dh_{r}" for r in R]].sum(axis=1)
    t["out_A"] = (1 - t.new_A / t.new_tot) * 100
    t.to_csv(os.path.join(OUT, "zoning_route_sigun.csv"), index=False, encoding="utf-8-sig")

    say("신규 시가지는 어디서 생겼나: 2026년 용도지역별 구성 (V-World 연속주제 UQ111·UQ112, 토지피복 대분류 2009→2019)")
    g = t.groupby("group")
    for pre, lab, unit in [("new", "신규 시가지 2009→19", "km²"), ("dh", "원도심 밖 주택 증가 2015→24", "호"),
                           ("avail", "2009년 비시가지 땅(가용지)", "km²")]:
        tot = g[[f"{pre}_{r}" for r in R]].sum()
        sh = tot.div(tot.sum(axis=1), axis=0) * 100
        sh.columns = [LABEL[r] for r in R]
        sh[f"합계({unit})"] = tot.sum(axis=1).round(0)
        say(f"\n{lab}: 용도지역별 비중(%)")
        say(sh.reindex(ORDER).round(1).to_string())
    a = g[[f"new_{r}" for r in R]].sum()
    b = g[[f"avail_{r}" for r in R]].sum()
    ratio = (a.div(a.sum(axis=1), axis=0) / b.div(b.sum(axis=1), axis=0).values)
    ratio.columns = [LABEL[r] for r in R]
    say("\n가용지 대비 신규 시가지 집중도 (신규 비중 ÷ 가용지 비중; 1보다 크면 그 용도에서 더 많이 개발)")
    say(ratio.reindex(ORDER).round(2).to_string())

    say("\nKOSIS 대조: 주거·상업·공업지역 순증 2008→19 대 그 안의 신규 시가지, 시가화예정용지 2009→19 (km², 합계)")
    c = g[["zoneA_0819", "new_A", "new_tot", "reserve09", "reserve19"]].sum(min_count=1)
    c["예정용지 변화"] = c.reserve19 - c.reserve09
    c = c.rename(columns={"zoneA_0819": "용도지역 순증", "new_A": "A 안 신규 시가지", "new_tot": "신규 시가지 전체",
                          "reserve09": "예정용지 2009", "reserve19": "예정용지 2019"})
    say(c.reindex(ORDER).round(1).to_string())

    d = t[t.group.isin(["감소", "정체", "성장"]) & (t.new_tot > 0.05)].copy()
    d["lnew"] = np.log(d.new_tot)
    say("\n모형 (비수도권 도 시군, 신규 시가지 5 ha 이상): 신규 시가지 중 주거·상업·공업지역 밖 비중(%)")
    m = smf.ols("out_A ~ C(group, Treatment('성장')) + lnew + C(region)", d).fit(cov_type="HC1")
    for k in [x for x in m.params.index if x.startswith("C(group")]:
        say(f"   {k.split('T.')[-1].rstrip(']')} (성장 대비): {m.params[k]:+.1f}{stars(m.pvalues[k])} (se {m.bse[k]:.1f})")
    say(f"   log 신규 시가지: {m.params.lnew:+.1f}{stars(m.pvalues.lnew)}, n={int(m.nobs)}, 성장 평균 {d[d.group == '성장'].out_A.mean():.1f}%")
    # 감소 시군 are mostly 군 with little 도시지역: control for the share of 2009 non-urban land inside 도시지역 (A-C)
    # and for the share of the 시군's 2009 urban land already in zone A
    d["avail_urb"] = d[["avail_A", "avail_B", "avail_C"]].sum(axis=1) / d[[f"avail_{r}" for r in R]].sum(axis=1) * 100
    d["old_inA"] = d.old_A / d[[f"old_{r}" for r in R]].sum(axis=1) * 100
    d["gun"] = d.sigun.str.endswith("군").astype(int)
    m = smf.ols("out_A ~ C(group, Treatment('성장')) + lnew + avail_urb + old_inA + gun + C(region)", d).fit(cov_type="HC1")
    k = "C(group, Treatment('성장'))[T.감소]"
    say(f"   + 가용지 중 도시지역 비율, 기성시가지 중 주거·상업·공업 비율, 군 여부 통제: 감소 {m.params[k]:+.1f}{stars(m.pvalues[k])} "
        f"(se {m.bse[k]:.1f}); 가용지 도시지역 비율 1%p {m.params.avail_urb:+.2f}{stars(m.pvalues.avail_urb)}, "
        f"군 {m.params.gun:+.1f}{stars(m.pvalues.gun)}, n={int(m.nobs)}")
    e = d.dropna(subset=["reserve_share09"])
    m = smf.ols("out_A ~ reserve_share09 + lnew + C(region)", e).fit(cov_type="HC1")
    say(f"   2009 예정용지 비율(시가화용지 대비 %) 10%p: {m.params.reserve_share09 * 10:+.2f}{stars(m.pvalues.reserve_share09)} "
        f"(se {m.bse.reserve_share09 * 10:.2f}), n={int(m.nobs)}")
    with open(os.path.join(OUT, "zoning_route.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
