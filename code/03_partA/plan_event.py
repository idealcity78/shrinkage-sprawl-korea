"""Event study: does a master-plan revision that enlarges 시가화예정용지 (or planned population) lead to zoning and
development in the following years?  (paper 1, step 21a)

Treatment (시군 x year, from KOSIS TX_315_2009_H1004 / H1004A via plan_pop.load)
  adopt     1 in the year a new plan vintage (new 수립일) takes effect
  res_up    1 if that new plan enlarges 시가화예정용지;  pop_up  1 if it raises 계획인구   (main: binary events)
  d_res     increase in 시가화예정용지 (km2, positive part), % of the base area; 0 otherwise  (secondary, winsorised
            at the 99th percentile of positive values: some series jump implausibly, e.g. 태백 +139 km2 in 2020)
  d_pop     increase in 계획인구, % of registered population; 0 otherwise (same winsorising)
Outcomes (annual flows, % of the base area = the 시군 median of 주거 + 상업 + 공업지역 2008-2025; winsorised at the
1st/99th percentiles because a few zoning series swing and revert, e.g. 신안군 0.3 -> 8.2 -> 0.4 km2)
  zone      change in 주거 + 상업 + 공업지역 area (도시관리계획 zoning, TX_315_2009_H1440, 2008-2025)
  zone_res  change in 주거지역 only
  devp      개발행위허가 토지형질변경 area (TX_315_2009_H1100, 2005-2025). The permit total is not used: the
            건축물의 건축 category starts in 2012 and triples the total.
Model (continuous-treatment event study with binned endpoints, Schmidheiny & Siegloch 2023)
  y_it = sum_{k=-4..6} b_k E^k_it + a_i + g_{region x t} + e_it,   E^k = D_{i,t-k}, k=-1 omitted,
  E^-4 = sum of D at t+4 and later, E^6 = sum of D at t-6 and earlier; s.e. clustered by 시군.
  Sample: non-capital 도 시군 (groups 감소, 정체, 성장), years 2010-2025. 창원시 and 청주시 are left out because
  their units merged in 2010 and 2014 and the plan series jump at the merger. Heterogeneity: 감소 vs 정체·성장.

Outputs: outputs/partA/plan_event.txt, plan_event_coefs.csv, plan_event_panel.csv
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\plan_event.py
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
import plan_pop

sys.stdout.reconfigure(encoding="utf-8")
OUT = os.path.join(paths.OUTPUTS, "partA")
SRC = os.path.join(paths.WORK, "housing")
K = list(range(-4, 7))
YEARS = range(2010, 2026)
MERGED = {"마산시": "창원시", "진해시": "창원시", "청원군": "청주시"}
LEAVE_OUT = {"창원시", "청주시"}


def kosis_sigun(tbl):
    """Rows of a KOSIS 460 시군구 table mapped to study units (고성군 by 도, merged units summed)."""
    a = pd.read_csv(os.path.join(SRC, f"{tbl}.csv"), dtype={"C1": str, "C2": str})
    lens = sorted(a.C1.str.len().unique())
    prov = {c: n for c, n in zip(a.C1, a.C1_NM) if len(c) == lens[0]}
    a = a[a.C1.str.len() == lens[-1]].copy()
    a["prov"] = a.C1.str[:lens[0]].map(prov).fillna("")
    a["sigun"] = [plan_pop.unit(MERGED.get(n.strip(), n), p) for n, p in zip(a.C1_NM, a.prov)]
    a["year"] = a.PRD_DE.astype(int)
    return a


def outcomes():
    z = kosis_sigun("TX_315_2009_H1440")
    z = z[(z.ITM_NM == "면적") & z.C2_NM.isin(["주거지역", "상업지역", "공업지역"])]
    z = z.pivot_table(index=["sigun", "year"], columns="C2_NM", values="DT", aggfunc="sum") / 1e6
    z["urbzone"] = z.sum(axis=1)
    d = kosis_sigun("TX_315_2009_H1100")
    d = d[(d.ITM_NM == "면적") & (d.C2_NM == "토지형질변경")].groupby(["sigun", "year"]).DT.sum() / 1e6
    return z[["urbzone", "주거지역"]].join(d.rename("devp_km2"), how="outer")


def treatments():
    w = plan_pop.load().sort_values(["sigun", "year"])
    w["new"] = w.groupby("sigun").adopt.transform(lambda s: s.ne(s.shift()) & s.shift().notna())
    w["d_res_km2"] = w.groupby("sigun").reserve.diff().clip(lower=0).where(w.new, 0).fillna(0)
    w["d_P"] = w.groupby("sigun").P.diff().clip(lower=0).where(w.new, 0).fillna(0)
    return w.set_index(["sigun", "year"])[["new", "d_res_km2", "d_P", "P"]]


def event_terms(p, d):
    g = p.groupby("sigun")[d]
    names = []
    for k in K:
        if k == -1:
            continue
        n = f"E{k}".replace("-", "m")
        if k == K[0]:          # t+4 and later
            p[n] = g.transform(lambda s: s[::-1].cumsum()[::-1].shift(-(-k)).fillna(0))
        elif k == K[-1]:       # t-6 and earlier
            p[n] = g.transform(lambda s: s.cumsum().shift(k).fillna(0))
        else:
            p[n] = g.shift(k).fillna(0)
        names.append((k, n))
    return names


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def main():
    lines, rows = [], []

    def say(s=""):
        print(s)
        lines.append(s)

    ss = pd.read_csv(os.path.join(OUT, "shrink_sprawl_sigun.csv"))
    info = ss[["sigun", "group", "region"]].drop_duplicates("sigun").set_index("sigun")
    rp = pd.read_csv(os.path.join(OUT, "regpop_sigun.csv")).set_index(["sigun", "year"]).regpop
    o, t = outcomes(), treatments()
    sig = sorted(set(info.index[info.group.isin(["감소", "정체", "성장"])]) - LEAVE_OUT)
    idx = pd.MultiIndex.from_product([sig, range(2000, 2031)], names=["sigun", "year"])
    p = pd.DataFrame(index=idx).join(o).join(t).reset_index()
    p["base"] = p.groupby("sigun").urbzone.transform(lambda s: s[(s.index >= 0)].median())
    p = p[p.base > 0].sort_values(["sigun", "year"])
    p["zone"] = p.groupby("sigun").urbzone.diff() / p.base * 100
    p["zone_res"] = p.groupby("sigun")["주거지역"].diff() / p.base * 100
    p["devp"] = p.devp_km2 / p.base * 100
    p["adopt"] = p.new.fillna(False).astype(float)
    p["d_res"] = p.d_res_km2.fillna(0) / p.base * 100
    p["d_pop"] = p.d_P.fillna(0) / pd.Series([rp.get((s, y), np.nan) for s, y in zip(p.sigun, p.year)],
                                              index=p.index) * 100
    p["d_pop"] = p.d_pop.fillna(0)
    p["res_up"] = ((p.adopt == 1) & (p.d_res > 0)).astype(float)
    p["pop_up"] = ((p.adopt == 1) & (p.d_pop > 0)).astype(float)
    for c in ("d_res", "d_pop"):
        p[c] = p[c].clip(upper=p.loc[p[c] > 0, c].quantile(.99))
    w = p.year.between(2010, 2025)
    for c in ("zone", "zone_res", "devp"):
        lo, hi = p.loc[w, c].quantile([.01, .99])
        p[c] = p[c].clip(lo, hi)
    p = p.join(info, on="sigun")
    p.to_csv(os.path.join(OUT, "plan_event_panel.csv"), index=False, encoding="utf-8-sig")

    say("기본계획 수립·변경 사건연구 (비수도권 도 시군, 2010~2025; 창원·청주 제외)")
    e = p[p.year.between(2009, 2025)]
    ev = e[e.adopt == 1]
    say(f"  시군 {e.sigun.nunique()}개, 새 계획 시행 {len(ev)}건(2009~2025), 그중 시가화예정용지 증가 {int((ev.d_res > 0).sum())}건, "
        f"계획인구 증가 {int((ev.d_pop > 0).sum())}건")
    say(f"  증가가 있던 계획의 중앙값: 예정용지 +{ev[ev.d_res > 0].d_res.median():.1f}% (기준 용도지역 대비), "
        f"계획인구 +{ev[ev.d_pop > 0].d_pop.median():.1f}% (주민등록인구 대비)")
    say(f"  결과 평균(연, 기준 용도지역 대비 %, 1·99% 절단): 용도지역 증가 {e.zone.mean():.2f}, 주거지역 증가 {e.zone_res.mean():.2f}, "
        f"토지형질변경 허가 {e.devp.mean():.2f}")

    specs = [("adopt", "새 계획 시행(0/1)"), ("res_up", "예정용지를 늘린 새 계획(0/1)"),
             ("pop_up", "계획인구를 늘린 새 계획(0/1)"), ("d_res", "예정용지 증가 1%p"), ("d_pop", "계획인구 증가 1%p")]
    for d, lab in specs:
        names = event_terms(p, d)
        for y, ylab in [("zone", "용도지역(주거·상업·공업) 증가"), ("zone_res", "주거지역 증가"), ("devp", "토지형질변경 허가")]:
            for sub, cond in [("전체", None), ("감소", "감소"), ("정체·성장", "other")]:
                q = p[p.year.isin(YEARS)].dropna(subset=[y])
                if cond == "감소":
                    q = q[q.group == "감소"]
                elif cond == "other":
                    q = q[q.group != "감소"]
                q = q.assign(ry=q.region + "_" + q.year.astype(str))
                f = f"{y} ~ " + " + ".join(n for _, n in names) + " + C(sigun) + C(ry)"
                m = smf.ols(f, q).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(q.sigun)[0]})
                pre = [n for k, n in names if k < -1]
                post = [n for k, n in names if 0 <= k <= 5]
                wt = m.wald_test(" , ".join(f"{n} = 0" for n in pre), use_f=True, scalar=True)
                cum = m.t_test(" + ".join(post) + " = 0")
                for k, n in names:
                    rows.append(dict(treat=d, y=y, sample=sub, k=k, coef=m.params[n], se=m.bse[n], p=m.pvalues[n],
                                     n=int(m.nobs)))
                rows.append(dict(treat=d, y=y, sample=sub, k="cum0_5", coef=float(cum.effect[0]),
                                 se=float(cum.sd[0][0]), p=float(cum.pvalue), n=int(m.nobs)))
                rows.append(dict(treat=d, y=y, sample=sub, k="pre_F_p", coef=float(wt.fvalue), se=np.nan,
                                 p=float(wt.pvalue), n=int(m.nobs)))
                if sub == "전체" or y != "zone_res":
                    coefs = "  ".join(f"{k:+d}:{m.params[n]:.3f}{stars(m.pvalues[n])}" for k, n in names if -3 <= k <= 5)
                    say(f"\n[{lab} → {ylab}, {sub}] n={int(m.nobs)}, 사전 계수 결합검정 p={float(wt.pvalue):.2f}, "
                        f"0~5년 누적 {float(cum.effect[0]):.3f}{stars(float(cum.pvalue))} (se {float(cum.sd[0][0]):.3f})")
                    say("   " + coefs)

    pd.DataFrame(rows).to_csv(os.path.join(OUT, "plan_event_coefs.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "plan_event.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
