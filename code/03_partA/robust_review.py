"""Robustness checks requested by the mock review of 2026-11-21 that need no grid step.

1. Groups from the pre-period. The main groups use registered-population change 2000-2019, which overlaps the
   outcome windows. Here units are regrouped by the change 1992-2000 (decline below -2 %, growth above +2 %, which is
   the main rule's -5 / +5 % over 19 years scaled to 8 years), and the main group comparisons are re-run:
     a) off-plan share of new urban land (zoning_route.py model, growing units as reference)
     b) off-plan share of dwellings added 2015-24 outside the old core, cells with >= 5 added (zoning_route_robust.py)
     c) vacancy panel: pre-2000 vacancies on net additions by group (vacancy.py, equation 8)
2. Vacancy panel dynamics: current and lagged net additions (t-1, t-2), to see whether the pre-2000 vacancies that
   follow new building persist or are refilled; and the household control by group (2020-2024).
3. Industrial complexes: sale rate and land-cover measures on the same set of complexes (those matched to the KICOX
   statistics), since the sale rate is only known for matched complexes.
Added after the final mock review (2026-11-22):
4. Refilling of recently built vacancies: the lag model of 2 for vacancies in dwellings built in the last five years
   and for all vacancies.
5. Decline as it happens rather than by group: pre-2000 vacancies on net additions interacted with the annualised
   registered-population change of the five years before the panel year (y-6 -> y-1), and with an indicator for decline.
6. Off-plan models on residential new urban land and on dwellings: the zoning_route.py group models (growing units as
   reference, log size and region; then the controls of the full model) with the off-plan share of residential new
   urban land (2022 middle-class map), of dwellings added outside the old core in cells gaining at least 5, and of the
   net dwelling change outside the old core.

Output: outputs/partA/robust_review.txt, robust_review_models.csv
Run:  propy.bat code\\03_partA\\robust_review.py
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
OUT = os.path.join(paths.OUTPUTS, "partA")
GROUPS = ["감소", "정체", "성장"]
RTS = ["A", "B", "C", "D", "E", "F"]


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def fmt(m, v):
    return f"{m.params[v]:+.3f} ({m.bse[v]:.3f}){stars(m.pvalues[v])}"


def main():
    lines, rows = [], []

    def say(s=""):
        print(s)
        lines.append(s)

    # 1. pre-period groups
    rp = pd.read_csv(os.path.join(OUT, "regpop_sigun.csv")).pivot_table(index="sigun", columns="year", values="regpop")
    z = pd.read_csv(os.path.join(OUT, "zoning_route_sigun.csv"))
    z = z[z.group.isin(GROUPS)].copy()
    ch = (rp[2000] / rp[1992] - 1) * 100
    z["pre_ch"] = z.sigun.map(ch)
    z["pre_group"] = np.select([z.pre_ch < -2, z.pre_ch > 2], ["감소", "성장"], "정체")
    z.loc[z.pre_ch.isna(), "pre_group"] = np.nan
    say("1. 사전 기간(1992 -> 2000 주민등록인구 변화) 집단: 감소 < -2 %, 성장 > +2 %")
    say(pd.crosstab(z.group, z.pre_group, margins=True).reindex(GROUPS + ["All"]).to_string())
    pre = z.set_index("SG_ID").pre_group

    d = z[(z[[f"new_{r}" for r in RTS]].sum(axis=1) > 0.05)].dropna(subset=["pre_group"]).copy()
    d["lnew"] = np.log(d[[f"new_{r}" for r in RTS]].sum(axis=1))
    say("\n   a) 신규 시가지 중 주거·상업·공업지역 밖 비중 (%), 성장 대비, + log 신규 시가지 + 권역, HC1")
    for lab, col in [("본문 집단", "group"), ("사전 집단", "pre_group")]:
        m = smf.ols(f"out_A ~ C({col}, Treatment('성장')) + lnew + C(region)", d).fit(cov_type="HC1")
        k = f"C({col}, Treatment('성장'))[T.감소]"
        say(f"      {lab}: 감소 {m.params[k]:+.1f}{stars(m.pvalues[k])} (se {m.bse[k]:.1f}), n={int(m.nobs)}")
        rows.append(["offplan_land", lab, "shrinking", m.params[k], m.bse[k], m.pvalues[k], int(m.nobs)])

    g = pd.read_csv(os.path.join(OUT, "zoning_route_robust_grid.csv"))
    g["group"], g["pre_group"] = g.SG_ID.map(z.set_index("SG_ID").group), g.SG_ID.map(pre)
    say("\n   b) 기성시가지 밖 새 주택 2015-24 (5호 이상 증가 셀) 중 주거·상업·공업지역 밖 비중 (%, 집단 합계)")
    for lab, col in [("본문 집단", "group"), ("사전 집단", "pre_group")]:
        t = g.dropna(subset=[col]).groupby(col)[[f"ge5_{r}" for r in RTS]].sum()
        sh = (1 - t.ge5_A / t.sum(axis=1)) * 100
        say(f"      {lab}: " + ", ".join(f"{k} {sh.get(k, np.nan):.1f}" for k in GROUPS))
        for k in GROUPS:
            rows.append(["offplan_dwellings_ge5", lab, k, sh.get(k, np.nan), np.nan, np.nan, np.nan])

    v = pd.read_csv(os.path.join(OUT, "vacancy_panel.csv"))
    v["pre_group"] = v.SG_ID.map(pre)
    say("\n   c) 빈집 패널 (2016-2025): 2000년 이전 주택 빈집 변화 ~ 주택 순증 (천 호당), 시군 FE + 권역 x 연도 FE")
    for lab, col in [("본문 집단", "group"), ("사전 집단", "pre_group")]:
        out = []
        for k in GROUPS:
            q = v[v[col] == k]
            if q.sigun.nunique() < 5:     # too few units for unit and region x year fixed effects
                out.append(f"{k} 추정 안 함 (시군 {q.sigun.nunique()})")
                rows.append(["vacancy_group", lab, k, np.nan, np.nan, np.nan, len(q)])
                continue
            m = smf.ols("d_vac_old ~ s + C(sigun) + C(ry)", q).fit(cov_type="cluster", cov_kwds={"groups": q.sigun})
            out.append(f"{k} {fmt(m, 's')} (시군 {q.sigun.nunique()})")
            rows.append(["vacancy_group", lab, k, m.params["s"], m.bse["s"], m.pvalues["s"], int(m.nobs)])
        say(f"      {lab}: " + "; ".join(out))

    # 2. vacancy dynamics
    v = v.sort_values(["sigun", "year"])
    for L in (1, 2):
        v[f"s_l{L}"] = v.groupby("sigun").s.shift(L)
    say("\n2. 빈집 패널의 시차: d_vac_old ~ s + s(t-1) + s(t-2), 시군 FE + 권역 x 연도 FE (2018-2025)")
    for k in GROUPS + ["비수도권 도 시군"]:
        q = v[v.group.isin(GROUPS)] if k == "비수도권 도 시군" else v[v.group == k]
        q = q.dropna(subset=["s_l1", "s_l2"])
        m = smf.ols("d_vac_old ~ s + s_l1 + s_l2 + C(sigun) + C(ry)", q).fit(cov_type="cluster",
                                                                          cov_kwds={"groups": q.sigun})
        tot = m.t_test("s + s_l1 + s_l2 = 0")
        say(f"   {k}: s {fmt(m, 's')}, s(t-1) {fmt(m, 's_l1')}, s(t-2) {fmt(m, 's_l2')}; 합 "
            f"{float(tot.effect[0]):+.3f} ({float(tot.sd[0][0]):.3f}){stars(float(tot.pvalue))}, n={int(m.nobs)}")
        for t_ in ("s", "s_l1", "s_l2"):
            rows.append(["vacancy_lags", k, t_, m.params[t_], m.bse[t_], m.pvalues[t_], int(m.nobs)])
        rows.append(["vacancy_lags", k, "sum", float(tot.effect[0]), float(tot.sd[0][0]), float(tot.pvalue), int(m.nobs)])
    say("\n   가구 변화 통제 (2020-2024), 집단별: d_vac_old ~ s + d_hh")
    for k in GROUPS:
        q = v[(v.group == k)].dropna(subset=["d_hh"])
        m = smf.ols("d_vac_old ~ s + d_hh + C(sigun) + C(ry)", q).fit(cov_type="cluster", cov_kwds={"groups": q.sigun})
        say(f"   {k}: s {fmt(m, 's')}, d_hh {fmt(m, 'd_hh')}, n={int(m.nobs)}")
        rows.append(["vacancy_hh", k, "s", m.params["s"], m.bse["s"], m.pvalues["s"], int(m.nobs)])

    # 4. refilling of recently built vacancies
    say("\n4. 시차 모형, 최근 5년 내 지은 주택 빈집과 전체 빈집: y ~ s + s(t-1) + s(t-2), 시군 FE + 권역 x 연도 FE (2018-2025)")
    for y in ("d_vac_new5", "d_vac"):
        for k in GROUPS + ["비수도권 도 시군"]:
            q = v[v.group.isin(GROUPS)] if k == "비수도권 도 시군" else v[v.group == k]
            q = q.dropna(subset=["s_l1", "s_l2"])
            m = smf.ols(f"{y} ~ s + s_l1 + s_l2 + C(sigun) + C(ry)", q).fit(cov_type="cluster",
                                                                          cov_kwds={"groups": q.sigun})
            tot = m.t_test("s + s_l1 + s_l2 = 0")
            say(f"   {y} {k}: s {fmt(m, 's')}, s(t-1) {fmt(m, 's_l1')}, s(t-2) {fmt(m, 's_l2')}; 합 "
                f"{float(tot.effect[0]):+.3f} ({float(tot.sd[0][0]):.3f}){stars(float(tot.pvalue))}, n={int(m.nobs)}")
            for t_ in ("s", "s_l1", "s_l2"):
                rows.append([f"vacancy_lags_{y}", k, t_, m.params[t_], m.bse[t_], m.pvalues[t_], int(m.nobs)])
            rows.append([f"vacancy_lags_{y}", k, "sum", float(tot.effect[0]), float(tot.sd[0][0]), float(tot.pvalue),
                         int(m.nobs)])

    # 5. decline as it happens: prior five-year registered-population change, varying by year
    v["g5"] = [100 * ((rp.loc[s, y - 1] / rp.loc[s, y - 6]) ** 0.2 - 1) if s in rp.index else np.nan
               for s, y in zip(v.sigun, v.year)]
    v["dec5"] = (v.g5 < 0).astype(int)
    say("\n5. 2000년 이전 주택 빈집 ~ s + s x 직전 5년 주민등록인구 연 변화율(%) (또는 감소 여부), 시군 FE + 권역 x 연도 FE")
    for k, smp in [("비수도권 도 시군", v.group.isin(GROUPS)), ("전체 시군", v.group.notna())]:
        q = v[smp].dropna(subset=["g5"])
        for x in ("g5", "dec5"):
            m = smf.ols(f"d_vac_old ~ s + s:{x} + C(sigun) + C(ry)", q).fit(cov_type="cluster",
                                                                         cov_kwds={"groups": q.sigun})
            say(f"   {k}, {x}: s {fmt(m, 's')}, s x {x} {fmt(m, f's:{x}')}, n={int(m.nobs)}")
            for t_ in ("s", f"s:{x}"):
                rows.append([f"vacancy_decline_{x}", k, t_, m.params[t_], m.bse[t_], m.pvalues[t_], int(m.nobs)])
    say(f"   직전 5년 인구 변화율 분포 (비수도권 도 시군): 평균 {v[v.group.isin(GROUPS)].g5.mean():+.2f}, "
        f"사분위 범위 {v[v.group.isin(GROUPS)].g5.quantile(.25):+.2f} ~ {v[v.group.isin(GROUPS)].g5.quantile(.75):+.2f}")

    # 6. off-plan models on residential land and dwellings
    zr = pd.read_csv(os.path.join(OUT, "zoning_route_sigun.csv"))
    d = zr[zr.group.isin(GROUPS) & (zr.new_tot > 0.05)].copy()
    d["lnew"] = np.log(d.new_tot)
    d["avail_urb"] = d[["avail_A", "avail_B", "avail_C"]].sum(axis=1) / d[[f"avail_{r}" for r in RTS]].sum(axis=1) * 100
    d["old_inA"] = d.old_A / d[[f"old_{r}" for r in RTS]].sum(axis=1) * 100
    d["gun"] = d.sigun.str.endswith("군").astype(int)
    agg = g.groupby("SG_ID")[[f"{c}_{r}" for c in ("new_res", "ge5", "net") for r in RTS]].sum()
    for c in ("new_res", "ge5", "net"):
        tot = agg[[f"{c}_{r}" for r in RTS]].sum(axis=1)
        agg[f"out_{c}"] = np.where(tot > 0, (1 - agg[f"{c}_A"] / tot.where(tot > 0)) * 100, np.nan)
        agg[f"size_{c}"] = tot
    d = d.merge(agg[[f"{p_}_{c}" for p_ in ("out", "size") for c in ("new_res", "ge5", "net")]].reset_index(), on="SG_ID")
    say("\n6. 계획 밖 비중 모형 (비수도권 도 시군, 성장 대비): 주거 신규 시가지, 5호 이상 증가 셀의 새 주택, 순증 주택")
    k = "C(group, Treatment('성장'))[T.감소]"
    for c, lab in [("new_res", "주거 신규 시가지 (2022 중분류)"), ("ge5", "새 주택, 5호 이상 증가 셀"), ("net", "새 주택, 순증")]:
        q = d[d[f"size_{c}"] > 0].dropna(subset=[f"out_{c}"]).copy()
        q["lsize"] = np.log(q[f"size_{c}"])
        for spec, f in [("기본", f"out_{c} ~ C(group, Treatment('성장')) + lsize + C(region)"),
                        ("통제", f"out_{c} ~ C(group, Treatment('성장')) + lsize + avail_urb + old_inA + gun + C(region)")]:
            m = smf.ols(f, q).fit(cov_type="HC1")
            say(f"   {lab} {spec}: 감소 {m.params[k]:+.1f}{stars(m.pvalues[k])} (se {m.bse[k]:.1f}), n={int(m.nobs)}, "
                f"성장 평균 {q[q.group == '성장'][f'out_{c}'].mean():.1f}%")
            rows.append([f"offplan_{c}", spec, "shrinking", m.params[k], m.bse[k], m.pvalues[k], int(m.nobs)])

    # 3. industrial complexes: matched complexes only
    c = pd.read_csv(os.path.join(OUT, "ic_complexes.csv"))
    c = c[(c.capital == 0) & c.group.isin(GROUPS)]
    say("\n3. 산업단지: 산업단지공단 현황과 연결된 단지와 전체 단지 (면적 가중)")
    for w, lab in [((2006, 2010), "2006-10 지정"), ((2006, 2030), "2006년 이후 지정")]:
        s = c[c.appn_yr.between(*w)]
        for part, q in [("전체", s), ("연결", s[s.k_sale_target > 0]), ("미연결", s[~(s.k_sale_target > 0)])]:
            if len(q) == 0:
                continue
            kk = q[q.k_sale_target > 0]
            say(f"   {lab} {part}: 단지 {len(q)}, {q.km2.sum():.1f} km2, 2019 시가화 "
                f"{np.average(q.urb19.fillna(0), weights=q.km2):.1f}%, 2022 공업용지 "
                f"{np.average(q.ind22.fillna(0), weights=q.km2):.1f}%"
                + (f", 분양률 {kk.k_sold.sum() / kk.k_sale_target.sum() * 100:.1f}%, 분양 대상 / 지정 면적 "
                   f"{kk.k_sale_target.sum() / 1000 / kk.km2.sum() * 100:.1f}%" if len(kk) else ""))
    pd.DataFrame(rows, columns=["block", "sample", "term", "coef", "se", "p", "n"]).to_csv(
        os.path.join(OUT, "robust_review_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "robust_review.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
