"""Supplementary tables S2-S11 of paper 1, built from the output files (no typed-in numbers).

  S2  grid population / registered population by group and year (census -> register-census break)
  S3  sprawl indicators by group, both periods (shrink_sprawl.txt block 1)
  S4  elasticity of new urban land to population growth (shrink_sprawl.txt blocks 2 and 4)
  S5  housing supply and demand: all panel models (supply_demand_models.csv)
  S6  vacancy panel, all outcomes and the household-controlled model (vacancy_models.csv); vacancy levels
  S7  industrial complexes by designation window and group; all growth and placebo models (ic_unmet.txt, ic_unmet_models.csv)
  S8  plans: planned growth by adoption era (cap), plan-on-trend and cross-section models (plan_pop.txt, plan_pop_models.csv)
  S9  event study: all coefficients k = -4..6, cumulative 0-5 effects and pre-trend tests (plan_event_coefs.csv)
  S10 zoning routes: new urban land, new dwellings and available land by zone; concentration ratios; KOSIS comparison
      (zoning_route.txt)
  S11 innovation and enterprise new towns excluded from the old core (newcity_zones.csv)
Output: outputs/paper1/supplement_tables.md
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\paper1_supplement_tables.py
"""
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.join(paths.OUTPUTS, "partA")
OUT = os.path.join(paths.OUTPUTS, "paper1")
G = ["감소", "정체", "성장", "광역시", "수도권"]
EN = {"감소": "Shrinking", "정체": "Stagnant", "성장": "Growing", "광역시": "Metropolitan", "수도권": "Capital region",
      "감소+정체+성장": "Non-capital provincial", "광역시+수도권": "Metropolitan and capital region", "nonmetro": "Non-capital provincial",
      "전체": "All", "감소·정체·성장": "Non-capital provincial", "광역시·수도권": "Metropolitan and capital region"}


def read(f):
    return open(os.path.join(A, f), encoding="utf-8").read()


def tidy(c):
    c = str(c)
    if re.fullmatch(r"-?\d{4,}(\.\d+)?", c):                 # counts, totals and large means: integer, comma
        return f"{round(float(c)):,d}"
    return c


def md(header, rows):
    rows = [[tidy(c) for c in r] for r in rows]
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def cs(c, s, p, d=3):
    return f"{c:.{d}f} ({s:.{d}f}){stars(p)}"


def s2():
    lv = pd.read_csv(os.path.join(A, "supply_demand_levels.csv"))
    sp = pd.read_csv(os.path.join(A, "supply_demand_panel.csv"))[["sigun", "group"]].drop_duplicates("sigun")
    rp = pd.read_csv(os.path.join(A, "regpop_sigun.csv"))
    d = lv.merge(sp, on="sigun").merge(rp, on=["sigun", "year"])
    t = d.groupby(["group", "year"])[["pop", "regpop"]].sum()
    r = (t["pop"] / t["regpop"]).unstack().reindex(G)
    allr = d.groupby("year")[["pop", "regpop"]].sum()
    r.loc["All non-capital provincial and comparison groups"] = allr["pop"] / allr["regpop"]
    yrs = [y for y in [2000, 2005, 2010, 2015, 2019, 2024] if y in r.columns]
    rows = [[EN.get(g, g)] + [f"{r.at[g, y]:.3f}" for y in yrs] for g in r.index]
    return ("**Table S2.** Gridded population (SGIS 100 m) divided by registered population (KOSIS DT_1B040A3), group "
            "totals.\n\n" + md(["Group"] + [str(y) for y in yrs], rows) +
            "\n\nThe grid is a field census to 2010 and a register-based census from 2015; the jump between 2010 and 2015 "
            "in every group is a change of method, not of population. Registered population counts nationals only.")


def s3():
    s = read("shrink_sprawl.txt")
    block = s[s.index("1. 확산 지표"):s.index("   인구 변화 (중앙값")]
    rows = []
    lab = {"시가지 증가 %": "Urban land growth (%)", "신규 시가지/기초 시가지 %": "New urban land / initial urban land (%)",
           "비연속 비율 %": "Non-contiguous (leapfrog) share of new urban land (%)",
           "기성시가지에서 평균 거리 km": "Mean distance of new urban land from the old core (km)",
           "2km 넘는 신규 비율 %": "Share of new urban land > 2 km from the old core (%)"}
    for line in block.splitlines()[2:]:
        m = re.match(r"(.+?)\s{2,}(.+)$", line.strip())
        if not m or m.group(1) not in lab:
            continue
        vals = re.findall(r"([\d.]+) \(([\d.]+)\)", m.group(2))
        rows.append([lab[m.group(1)]] + [f"{a} ({b})" for a, b in vals])
    # Panel B: where new dwellings went and how the old core changed (group totals)
    bl = s[s.index("   새 주택이 기성시가지 밖에"):s.index("2. 확산의 인구 성장 탄력성")]
    rows_b = []
    for line in bl.splitlines():
        q = line.split()
        if q and q[0] in G and len(q) == 8:
            rows_b.append([EN[q[0]]] + q[1:])
    # Panel C: old-core population change on expansion, all terms except region fixed effects
    m = pd.read_csv(os.path.join(A, "shrink_sprawl_models.csv"))
    m = m[m.block == "coexist_full"].copy()
    m[["sample", "term"]] = m.term.str.split("|", expand=True)
    xl = {"new_rate_pre": ("2000–10", "New urban land rate 1999–2009 (%)"), "leap_share_pre": ("2000–10", "Leapfrog share 1999–2009 (%)"),
          "new_rate_post": ("2015–24", "New urban land rate 2009–19 (%)"), "out_share_1524": ("2015–24", "New dwellings outside the old core 2015–24 (%)")}
    sl = {"비수도권 도 시군": "Non-capital provincial", "감소 시군": "Shrinking", "성장·정체 시군": "Stagnant and growing",
          "수도권·광역시": "Metropolitan and capital region"}
    rows_c = []
    for x, (win, xlab) in xl.items():
        for smp, slab in sl.items():
            d = m[(m.y == x) & (m["sample"] == smp)].set_index("term")
            gp = [t for t in d.index if t.startswith("g_pop")][0]
            rows_c.append([win, xlab, slab, cs(d.at[x, "coef"], d.at[x, "se"], d.at[x, "p"]),
                           cs(d.at[gp, "coef"], d.at[gp, "se"], d.at[gp, "p"]),
                           cs(d.at["lpop10", "coef"], d.at["lpop10", "se"], d.at["lpop10", "p"]), int(d.at[x, "n"])])
    # Panel D: expansion with old-core decline (and si/gun decline), share of si/gun
    bd = s[s.index("   시가지는 늘고 기성시가지 인구는 준 시군 비율"):s.index("4. 주민등록인구")]
    rows_d = []
    for line in bd.splitlines():
        q = line.split()
        if q and q[0] in G and len(q) == 5:
            rows_d.append([EN[q[0]]] + [f"{float(v):.0f}" for v in q[1:]])
    n96 = re.search(r"2009-19 주민등록인구가 준 시군 (\d+): 시가지가 늘어난 시군 (\d+)%, 신규 시가지 비율 중앙값 ([\d.]+)%", s)
    n84 = re.search(r"비수도권 도 시군 (\d+) 가운데 2009-19 주민등록인구가 준 시군 (\d+), 그중 시가지가 늘어난 시군 (\d+)", s)
    return ("**Table S3.** Sprawl indicators and the old core by group.\n\nPanel A. Sprawl indicators, si/gun medians, 2009–2019 "
            "(1999–2009 in parentheses).\n\n"
            + md(["Indicator"] + [EN[g] for g in G], rows)
            + "\n\nPanel B. New dwellings outside the old core and population change (group totals, %).\n\n"
            + md(["Group", "New dwellings outside old core 2010–19", "…more than 500 m outside, 2010–19",
                  "New dwellings outside old core 2015–24", "Old-core population 2000–10", "si/gun population 2000–10",
                  "Old-core population 2015–24", "si/gun population 2015–24"], rows_b)
            + "\n\nPanel C. Old-core population change (%) on expansion, si/gun population change and log population 2010, "
              "with region fixed effects (none in the metropolitan and capital-region sample); OLS, HC1 s.e.\n\n"
            + md(["Window of old-core change", "Expansion measure", "Sample", "Expansion", "si/gun population change (%)",
                  "Log population 2010", "N"], rows_c)
            + "\n\nPanel D. si/gun whose urban land grew while old-core population fell (%), and of these, si/gun whose "
              "population also fell (%).\n\n"
            + md(["Group", "Expansion + core decline 1999–2010", "+ population decline 1999–2010",
                  "Expansion + core decline 2009–24", "+ population decline 2009–24"], rows_d)
            + f"\n\nOf the {n84.group(1)} non-capital provincial si/gun, {n84.group(2)} lost registered population in 2009–19 and "
              f"{n84.group(3)} of these expanded urban land; of all {n96.group(1)} si/gun with falling registered population, "
              f"{n96.group(2)} percent expanded, with a median new-urban-land rate of {n96.group(3)} percent. "
              "Population in Panels B–D is gridded (census 2000–10, register-based census 2015–24); changes are taken within "
              "one method only. Source: `shrink_sprawl.txt`, blocks 1, 3 and 4; `shrink_sprawl_models.csv`.")


def s4():
    m = pd.read_csv(os.path.join(A, "shrink_sprawl_models.csv"))
    cap = "C(group == '수도권')[T.True]"
    rows = []
    for blk, period, ys in [("elasticity_full_pre", "1999–2009 (census population 2000–2010)", ["new_rate", "leap_share", "d_lpcu"]),
                            ("elasticity_full_rp_post", "2009–2019 (registered population 2009–2019)", ["new_rate", "d_lpcu_rp", "leap_share"])]:
        for y in ys:
            d = m[(m.block == blk) & (m.y == y)].set_index("term")
            c = lambda t: cs(d.at[t, "coef"], d.at[t, "se"], d.at[t, "p"], 2 if t in ("pred_zero_growth", "Intercept") else 3)
            rows.append([period, {"new_rate": "New urban land rate (%)", "leap_share": "Leapfrog share (%)", "d_lpcu": "Δ log urban land per resident ×100",
                                  "d_lpcu_rp": "Δ log urban land per resident ×100"}[y],
                         c("pred_zero_growth"), c("Intercept"), c("gp"), c("gp:neg"), c("neg"), c("lpop10"), c(cap), int(d.at["gp", "n"])])
    return ("**Table S4.** Elasticity of sprawl to population growth, all 161 si/gun (OLS, HC1 standard errors).\n\n"
            + md(["Period", "Outcome", "Prediction at zero growth", "(a) Constant", "(b) Population growth g, 1 pp",
                  "(c) g × N", "(d) N (negative growth)", "(δ) ln P 2010", "(κ) Capital region C", "N (si/gun)"], rows)
            + "\n\nSpecification (equation 5): y_i = a + b g_i + c (g_i × N_i) + d N_i + δ ln P_i,2010 + κ C_i + e_i, with g "
              "population growth (%), N = 1 if g < 0, P population in 2010 and C = 1 for capital-region si/gun. The constant a "
              "is the value at ln P = 0 and has no direct meaning; the prediction at zero growth is a + δ × mean(ln P), the "
              "expected outcome of a non-capital si/gun of mean size whose population did not change, with its delta-method "
              "standard error. Source: `shrink_sprawl_models.csv`, blocks elasticity_full_pre and elasticity_full_rp_post.")


def s5():
    m = pd.read_csv(os.path.join(A, "supply_demand_models.csv"))
    lab = {("drivers", "g_hh_lag"): "Housing growth on prior household growth", ("drivers", "shrink_lag"): "Housing growth on prior population decline (0/1)",
           ("drivers", "g_hh"): "Housing growth on same-period household growth",
           ("absorb", "g_hh"): "Same-period household growth on housing growth (si/gun FE)", ("absorb", "g_pop"): "Same-period population growth on housing growth (si/gun FE)",
           ("absorb_group", "g_hh"): "Same-period household growth on housing growth, by group",
           ("lead", "s_house"): "Next-period growth on housing growth", ("lead", "g_hh"): "Next-period housing growth on household growth",
           ("inmig", "s_house"): "Net/gross in-migration from outside the si/gun on housing growth"}
    d0 = re.search(r"주택 증가율 ([\d.]+)%/년, 가구 증가율 ([\d.]+)%/년; 비감소 ([\d.]+), ([\d.]+)", read("supply_demand.txt"))
    desc = [["Population decline", d0.group(1), d0.group(2)], ["No population decline", d0.group(3), d0.group(4)]]
    rows = []
    for _, r in m.iterrows():
        rows.append([lab.get((r.block, r.term), r.block), str(r.model).replace("직전 수요만", "prior demand only").replace("+감소 시군", "+ prior decline")
                     .replace("+같은 기간 가구", "+ same-period households").replace("전 기간", "all periods").replace("2010-15 제외", "excl. 2010–15")
                     .replace("감소", "shrinking").replace("정체", "stagnant").replace("성장", "growing").replace("|noFE", ", no si/gun FE").replace("|FE", ", si/gun FE"),
                     r.term, cs(r.coef, r.se, r.p), int(r.n)])
    return ("**Table S5.** Housing supply, household growth and in-migration: all panel models, non-capital provincial si/gun.\n\n"
            + md(["Model", "Specification / outcome", "Term", "Coefficient (s.e.)", "N"], rows)
            + "\n\nsi/gun × five-year periods (2000–05, 2005–10, 2010–15, 2015–19, 2019–24); region × period fixed effects in all models; "
              "standard errors clustered by si/gun. Lead models use four periods (488 observations). Source: `supply_demand_models.csv`."
            + "\n\nPanel B. Mean annual growth in the five-year period following one with and without registered-population "
              "decline (%/yr), non-capital provincial si/gun.\n\n" + md(["Previous period", "Housing stock", "Households"], desc)
            + "\n\nAnnual growth g = 100 × [(x_t1/x_t0)^(1/n) − 1] of gridded dwellings and households. Source: `supply_demand.txt`, block 2.")


def s6():
    m = pd.read_csv(os.path.join(A, "vacancy_models.csv"))
    yl = {"d_vac": "All vacancies", "d_vac_old": "Pre-2000 dwellings", "d_vac_new5": "Built in last 5 years"}
    rows = [[EN.get(r["sample"], r["sample"]) + (" (household change controlled, 2020–24)" if r.block == "location_hh" else ""),
             yl[r.y], cs(r.coef, r.se, r.p), int(r.n)] for _, r in m.iterrows()]
    v = read("vacancy.txt")
    lv = v[v.index("1. 빈집 비율"):v.index("   (2005·2010")]
    hdr = lv.splitlines()[1].split()
    rows2 = []
    for line in lv.splitlines()[3:]:
        p = line.split()
        if p and p[0] in G:
            rows2.append([EN[p[0]]] + p[1:])
    bo = v[v.index("   빈집 가운데 2000년 전에 지은 주택 비중"):]
    rows3 = []
    for line in bo.splitlines()[1:12]:
        p = line.split()
        if p and p[0] in G and len(p) == 7:
            rows3.append([EN[p[0]]] + p[1:])
    lt = re.search(r"12개월 이상 빈 주택 비중 \(%\): (.+)", v).group(1)
    us = re.search(r"10호를 넘은 시군 비율 \(2007-2025, %\): (.+)", v).group(1)
    lt = dict(re.findall(r"(\S+) ([\d.]+)", lt))
    us = dict(re.findall(r"(\S+) ([\d.]+)", us))
    rows4 = [[EN[g], lt[g], us[g]] for g in G]
    return ("**Table S6.** Vacancy panel (2016–2025), all outcomes, and vacancy rates.\n\n"
            + md(["Sample", "Vacancy outcome", "Coefficient (s.e.)", "N (si/gun-years)"], rows)
            + "\n\nPanel B. Vacancy rate (vacant ÷ dwellings, group totals, %).\n\n" + md(["Group"] + hdr, rows2)
            + "\n\n2005 and 2010: field census, denominator SGIS grid dwellings; 2015 onward: register-based census."
            + "\n\nPanel C. Vacant dwellings built before 2000: share of all vacancies (%) and number per 1,000 dwellings.\n\n"
            + md(["Group", "Share 2015", "Per 1,000 2015", "Share 2019", "Per 1,000 2019", "Share 2024", "Per 1,000 2024"], rows3)
            + "\n\nPanel D. Long-term vacancy and unsold new housing.\n\n"
            + md(["Group", "Vacant 12 months or longer, share of vacancies 2010 (%)",
                  "si/gun with unsold dwellings above 10 per 1,000 in any year 2007–2025 (%)"], rows4)
            + "\n\nSource: `vacancy_models.csv`, `vacancy.txt`.")


def s7():
    c = read("ic_unmet.txt")
    blk = c[c.index("1. 지정 시기별"):c.index("   시군 집단별, 2006년 이후")]
    cols = ["Window", "Complexes", "Designated km²", "Urbanised 2019 (%)", "Industrial land 2022 (%)", "Urban in 1999 (%)",
            "Sale rate (%)", "Unsold km²", "Operating (%)", "Manufacturing workers per km², 2024", "Manufacturing employment change 2010–24"]
    rows = []
    for line in blk.splitlines():
        p = line.split()
        if p and re.match(r"(~2000|\d{4}-\d{2}|2021-)$", p[0]):
            rows.append([p[0].replace("-", "–"), p[1][:-2]] + p[2:])   # complex counts as integers
    blk2 = c[c.index("   시군 집단별, 2006년 이후"):c.index("   유형별")]
    rows2 = []
    sec = "after 2006"
    for line in blk2.splitlines():
        if "2005년 이전" in line:
            sec = "before 2006"
        p = line.split()
        if p and p[0] in ("감소", "정체", "성장"):
            rows2.append([f"{EN[p[0]]} ({sec})", p[1][:-2]] + p[2:])
    m = pd.read_csv(os.path.join(A, "ic_unmet_models.csv"))
    yl = {"manuf": "Manufacturing employment", "emp": "All employment", "pop": "Population", "hh": "Households"}
    bl = {"growth": "Growth 2010–24", "placebo_1024": "Placebo: 2010–24 growth", "placebo_0515": "Placebo: 2005–15 growth",
          "reverse": "Reverse: designation 2006–12 on 2000–05 growth"}
    tl = {"ic_0612": "Designated 2006–12", "ic_0105": "Designated 2001–05", "ic_1624": "Designated 2016–24", "pre_manuf": "Prior manufacturing growth",
          "pre_pop": "Prior population growth", "pre_hh": "Prior household growth"}
    m = m[m.block.isin(bl) & m.y.isin(yl)]
    rows3 = [[bl[r.block], yl[r.y], tl[r.term], cs(r.coef, r.se, r.p), int(r.n)] for _, r in m.iterrows()]
    tot = re.search(r"산업단지 (\d+)개, 지정 면적 (\d+) km2", c)
    return ("**Table S7.** Industrial complexes in non-capital provincial si/gun (area-weighted).\n\nPanel A. By designation window.\n\n"
            + md(cols, rows) + "\n\nPanel B. By group.\n\n" + md(["Group (designation)"] + cols[1:], rows2)
            + "\n\nPanel C. Designation and growth, cross-section of 122 si/gun (designated area as % of 2009 urban land; outcome log growth ×100; "
              "controls: outcome growth 2000–05, log population 2000, region; HC1 s.e.).\n\n"
            + md(["Model", "Outcome", "Regressor", "Coefficient (s.e.)", "N"], rows3)
            + f"\n\nAll windows: {tot.group(1)} complexes, {tot.group(2)} km² designated. Area-weighted shares: urbanised 2019 and "
              "industrial land 2022 are the shares of designated area that are urban land in the 2019 large-class land-cover map "
              "and industrial use in the 2022 middle-class map; urban in 1999 is the share urban in the late-1990s map, which "
              "precedes designation for complexes designated after 2000 but not for many earlier ones. Sale rate = sold ÷ saleable "
              "industrial area, operating = operating ÷ resident firms, both summed over the complexes matched to the KICOX "
              "statistics (June 2026). "
              "Manufacturing workers are gridded employees times the manufacturing share of the enclosing 1 km cell. "
              "Source: `ic_unmet.txt`, `ic_unmet_models.csv`.")


def s8():
    p = read("plan_pop.txt")
    blk = p[p.index("6. 계획인구 상한"):p.index("   2019년 이후 수립")]
    rows = []
    g = None
    for line in blk.splitlines()[3:]:
        q = line.split()
        if not q:
            continue
        if q[0] in G:
            g, q = q[0], q[1:]
        rows.append([EN[g], q[0].replace("-", "–")] + q[1:])
    m = pd.read_csv(os.path.join(A, "plan_pop_models.csv"))
    bl = {"plan_on_trend": "Planned growth on prior trend (non-capital provincial, adopted 2000+, region FE, si/gun-clustered s.e.)",
          "urban_on_plan_plan_excess": "Urban land growth 2009–19 on 2009 plan (region FE, HC1)",
          "urban_on_plan_reserve_share": "Urban land growth 2009–19 on 2009 plan (region FE, HC1)",
          "reserve_on_excess": "Reserve share on planned increase (region FE)", "urban_on_plan": "Urban land growth 2009–19 on 2009 plan (region FE, HC1)",
          "cap_2019": "Planned growth: adopted 2019+ vs earlier (trend and region controlled)"}
    tl = {"Intercept": "Constant (reference region, zero trend)", "pred_zero_trend": "Prediction at zero trend, mean over regions",
          "g_reg": "Realised population change 2009–19 (%)",
          "trend_g": "Prior 5-year trend", "excess_pct": "Planned increase (%)", "plan_excess": "2009 overstatement (%)",
          "reserve_share09": "2009 reserve ÷ urbanised land (%)", "reserve_share": "2009 reserve ÷ urbanised land (%)", "post": "Adopted 2019 or later"}
    rows2 = [[bl[r.block], tl.get(r.term, r.term) + (" (with overstatement)" if r.block == "urban_on_plan_plan_excess" else
                                                     " (with reserve share)" if r.block == "urban_on_plan_reserve_share" else ""),
              cs(r.coef, r.se, r.p), int(r.n)] for _, r in m.iterrows()]
    sc = re.search(r"계획\(시군 × 수립일\) (\d+)개, 시군 (\d+)개", p)
    rows0 = [["Plan vintages (si/gun × adoption date), 2005–2025 tables", sc.group(1)], ["si/gun with a master plan", sc.group(2)]]
    for g_ in ("감소", "정체"):
        q = re.search(rf"{g_} 시군에서 직전 5년 인구가 줄던 때 세운 계획 (\d+)개 중 인구 증가를 계획한 비율 (\d+)%, 계획인구가 수립 당시 인구의 (\d+)% 위", p)
        rows0 += [[f"{EN[g_]}: plans adopted after five years of population decline", q.group(1)],
                  [f"{EN[g_]}: of these, share projecting growth (%)", q.group(2)],
                  [f"{EN[g_]}: of these, median planned population above population at adoption (%)", q.group(3)]]
    ov = re.search(r"감소 시군 2009 계획 초과 중앙값 (\d+)%, 성장 시군 (\d+)%", p)
    rows0 += [["Overstatement of plans in force in 2009, median (%): shrinking", ov.group(1)],
              ["Overstatement of plans in force in 2009, median (%): growing", ov.group(2)]]
    return ("**Table S8.** Plan vintages, planned population growth by adoption era, and plan models.\n\n"
            + "Panel A. Plan vintages and the growth premise.\n\n" + md(["Quantity", "Value"], rows0)
            + "\n\nPanel B. Planned growth by adoption era (medians).\n\n"
            + md(["Group", "Adopted", "Plan vintages", "Planned growth (%/yr)", "Prior trend (%/yr)", "Share projecting growth (%)"], rows)
            + "\n\nPanel C. Plan models.\n\n" + md(["Model", "Regressor", "Coefficient (s.e.)", "N"], rows2)
            + "\n\nPlanned growth = 100 × [(P/R_y0)^(1/(T−y0)) − 1], prior trend = 100 × [(R_y0/R_y0−5)^(1/5) − 1], with P the planned "
              "population, T the target year and R registered population (equations 2–3). Overstatement = 100 × (P/R_y0 − 1). "
              "The constant of the plan-on-trend model is the planned growth at zero trend in the reference region; the "
              "prediction averages over the regions of the 289 plans. The 105 percent cap (Directives No. 900, 2017, and "
              "No. 1133, 2018) applies to plans whose baseline survey began after the revisions. Source: `plan_pop.txt`, "
              "`plan_pop_models.csv`.")


def s9():
    c = pd.read_csv(os.path.join(A, "plan_event_coefs.csv"))
    tn = {"adopt": "Any new plan", "res_up": "New plan enlarging the reserve", "pop_up": "New plan raising planned population",
          "d_res": "Reserve increase, 1 pp", "d_pop": "Planned-population increase, 1 pp"}
    yn = {"zone": "Urban-use zoning", "zone_res": "Residential zoning", "devp": "Land-form-change permits"}
    sn = {"전체": "All", "감소": "Shrinking", "정체·성장": "Stagnant and growing"}
    out = []
    for tr in tn:
        rows = []
        for y in yn:
            for smp in sn:
                d = c[(c.treat == tr) & (c.y == y) & (c["sample"] == smp)]
                if d.empty:
                    continue
                k = d[~d.k.isin(["cum0_5", "pre_F_p"])].copy()
                k["k"] = k.k.astype(int)
                k = k.sort_values("k")
                cells = [f"{r.coef:.3f}{stars(r.p)}" for _, r in k.iterrows()]
                cum = d[d.k == "cum0_5"].iloc[0]
                pre = d[d.k == "pre_F_p"].iloc[0]
                rows.append([yn[y], sn[smp]] + cells + [cs(cum.coef, cum.se, cum.p), f"{pre.p:.2f}", int(cum.n)])
        ks = sorted(int(x) for x in c[~c.k.isin(["cum0_5", "pre_F_p"])].k.unique())
        head = ["Outcome", "Sample"] + [("≤" if kk == ks[0] else "≥" if kk == ks[-1] else "") + f"{kk:+d}" for kk in ks] + ["Cumulative 0–5 (s.e.)", "Pre-trend F p", "N"]
        out.append(f"Panel: {tn[tr]}\n\n" + md(head, rows))
    pe = read("plan_event.txt")
    ev = re.search(r"시군 (\d+)개, 새 계획 시행 (\d+)건\(2009~2025\), 그중 시가화예정용지 증가 (\d+)건, 계획인구 증가 (\d+)건", pe)
    mi = re.search(r"예정용지 \+([\d.]+)% \(기준 용도지역 대비\), 계획인구 \+([\d.]+)%", pe)
    return ("**Table S9.** Event study of master-plan adoptions: all coefficients (k = −1 omitted; endpoints binned).\n\n"
            + "\n\n".join(out)
            + "\n\nOutcomes are annual flows in percent of the si/gun's median urban zoning area 2008–2025, winsorised at the 1st/99th "
              "percentiles; non-capital provincial si/gun, 2010–2025 (Changwon and Cheongju excluded); si/gun and region × year fixed "
              f"effects; standard errors clustered by si/gun. Events, 2009–2025: {ev.group(2)} new plans, of which {ev.group(3)} enlarged "
              f"the reserve and {ev.group(4)} raised the planned population ({ev.group(1)} si/gun). Median increase where one occurred: "
              f"reserve +{mi.group(1)} percent of the base urban zoning, planned population +{mi.group(2)} percent of registered "
              "population. Source: `plan_event_coefs.csv`, `plan_event.txt`.")


def s10():
    z = read("zoning_route.txt")
    parts = re.split(r"\n\n", z)
    keep = []
    names = {"신규 시가지 2009→19": "New urban land 2009–2019 by 2026 zoning (%)",
             "원도심 밖 주택 증가 2015→24": "Dwellings added outside the old core 2015–2024 by 2026 zoning (%)",
             "2009년 비시가지 땅(가용지)": "Land not urban in 2009 (available land) by 2026 zoning (%)",
             "가용지 대비 신규 시가지 집중도": "Concentration: share of new urban land ÷ share of available land",
             "KOSIS 대조": "KOSIS comparison: urban-use zones and reserves (km²)"}
    colmap = {"주거·상업·공업": "Res./com./ind.", "자연녹지": "Natural green", "생산·보전녹지 등": "Other green, unsubdivided",
              "계획관리": "Planned mgmt", "생산·보전관리": "Prod./cons. mgmt", "농림·보전 등": "Agric./nat. cons., other",
              "합계(km²)": "Total (km²)", "합계(호)": "Total (dwellings)", "용도지역 순증": "Urban-use zones, net increase 2008–19",
              "A 안 신규 시가지": "New urban land inside them", "신규 시가지 전체": "All new urban land", "예정용지 2009": "Reserve 2009",
              "예정용지 2019": "Reserve 2019", "예정용지 변화": "Reserve change"}
    for p in parts:
        title = next((v for k, v in names.items() if k in p), None)
        if not title:
            continue
        lines = [l for l in p.splitlines() if l.strip()]
        ti = next(i for i, l in enumerate(lines) if any(k in l for k in names))
        hi = ti + 1
        hdr = re.split(r"\s{2,}", lines[hi].strip())
        rows = []
        outside = "주거·상업·공업" in hdr and "합계" in hdr[-1]      # route panels: add the off-plan share
        for l in lines[hi + 1:]:
            q = l.split()
            if q and q[0] in G:
                rows.append([EN[q[0]]] + q[1:] + ([f"{100 - float(q[1]):.1f}"] if outside else []))
        keep.append(f"Panel: {title}\n\n" + md(["Group"] + [colmap.get(h, h) for h in hdr]
                                                 + (["Outside res./com./ind. (%)"] if outside else []), rows))
    mm = z[z.index("모형 (비수도권"):]
    g1 = re.search(r"감소 \(성장 대비\): \+([\d.]+)(\**) \(se ([\d.]+)\)", mm)
    g2 = re.search(r"정체 \(성장 대비\): \+([\d.]+)(\**) \(se ([\d.]+)\)", mm)
    ln = re.search(r"log 신규 시가지: (-[\d.]+)(\**), n=(\d+), 성장 평균 ([\d.]+)%", mm)
    c1 = re.search(r"군 여부 통제: 감소 \+([\d.]+)(\**) \(se ([\d.]+)\); 가용지 도시지역 비율 1%p (-?\+?[\d.]+)(\**), 군 \+([\d.]+)(\**), n=(\d+)", mm)
    rs = re.search(r"10%p: \+([\d.]+)(\**) \(se ([\d.]+)\), n=(\d+)", mm)
    reg = md(["Model", "Shrinking vs growing", "Stagnant vs growing", "Other terms", "N"], [
        ["Group + log new urban land + region", f"{g1.group(1)} ({g1.group(3)}){g1.group(2)}", f"{g2.group(1)} ({g2.group(3)}){g2.group(2)}",
         f"log new urban land {ln.group(1)}{ln.group(2)}; mean for growing si/gun {ln.group(4)}%", ln.group(3)],
        ["+ share of available land in urban areas, old-core zoning, county dummy", f"{c1.group(1)} ({c1.group(3)}){c1.group(2)}", "",
         f"available urban share, 1 pp {c1.group(4)}{c1.group(5)}; county {c1.group(6)}{c1.group(7)}", c1.group(8)],
        ["2009 reserve ÷ urbanised land, 10 pp (instead of group)", "", "", f"{rs.group(1)} ({rs.group(3)}){rs.group(2)}", rs.group(4)]])
    return ("**Table S10.** Where new urban land formed: 2026 zoning routes.\n\n" + "\n\n".join(keep)
            + "\n\nPanel: Off-plan share of new urban land (%, outside residential, commercial and industrial zones), non-capital "
              "provincial si/gun with at least 5 ha of new urban land, OLS with HC1 s.e.\n\n" + reg + "\n\nSource: `zoning_route.txt`.")


def s11():
    z = pd.read_csv(os.path.join(A, "newcity_zones.csv"))
    name = {"강원원주 혁신도시": "Wonju (Gangwon) innovation city", "경남진주 혁신도시": "Jinju (Gyeongnam) innovation city",
            "경북김천 혁신도시": "Gimcheon (Gyeongbuk) innovation city", "광주·전남 공동혁신도시": "Gwangju–Jeonnam joint innovation city (Naju)",
            "대구신서 혁신도시": "Daegu Sinseo innovation city", "부산대연 혁신도시": "Busan Daeyeon innovation city",
            "부산동삼 혁신도시": "Busan Dongsam innovation city", "부산문현 혁신도시": "Busan Munhyeon innovation city",
            "부산센텀 혁신도시": "Busan Centum innovation city", "영암·해남 기업도시 구성지구": "Yeongam–Haenam enterprise city, Guseong district",
            "영암·해남 기업도시 삼포지구": "Yeongam–Haenam enterprise city, Sampo district",
            "영암·해남 기업도시 삼호지구": "Yeongam–Haenam enterprise city, Samho district", "울산우정 혁신도시": "Ulsan Ujeong innovation city",
            "원주 지식기반형 기업도시": "Wonju knowledge-based enterprise city", "전북 전주·완주 혁신도시": "Jeonju–Wanju (Jeonbuk) innovation city",
            "제주서귀포 혁신도시": "Seogwipo (Jeju) innovation city", "충북 진천·음성 혁신도시": "Jincheon–Eumseong (Chungbuk) innovation city",
            "충주 지식기반형 기업도시": "Chungju knowledge-based enterprise city", "태안 관광레저형 기업도시": "Taean tourism-leisure enterprise city"}
    src = {"V-World": "development-district layer", "V-World UQ161 지구단위계획구역": "district-unit-plan area (UQ161)", "없음": "not mapped"}
    rows = [[name[r.zone], r.type, r.designated, f"{r.area_gosi_km2:.2f}", f"{r.area_grid_km2:.2f}", f"{r.ratio:.2f}", src[r.source]]
            for r in z.itertuples()]
    inn, ent = (z.type == "innovation").sum(), (z.type == "enterprise").sum()
    mapped = z[z.source != "없음"]
    return ("**Table S11.** Innovation and enterprise new towns excluded from the old core.\n\n"
            + md(["Zone", "Type", "District designated", "Notified area (km²)", "Area on the 100 m grid (km²)", "Ratio", "Boundary source"], rows)
            + f"\n\n{inn} sites of the 10 innovation cities and {ent} sites of the 4 enterprise cities; {len(mapped)} are mapped. "
              f"The {len(z) - len(mapped)} unmapped sites are small Busan sites inside existing urban areas "
              f"({' and '.join(f'{a:.2f}' for a in z[z.source == '없음'].area_gosi_km2)} km² notified) with no district boundary "
              "in V-World. Innovation cities are national projects designated under the Special Act on the Relocation of Public "
              "Institutions to house public agencies moved out of the capital region; enterprise cities are designated under the "
              "Special Act on Enterprise Cities for private-led development. Both were developed by acquiring and rebuilding the "
              "whole district after designation, so housing added inside them is new-town construction rather than change in the "
              "old core; they are therefore excluded from the old core. Other new towns, such as housing-site development "
              "districts, are not excluded. Source: `newcity_zones.csv`.")


def main():
    os.makedirs(OUT, exist_ok=True)
    t = "\n\n".join([s2(), s3(), s4(), s5(), s6(), s7(), s8(), s9(), s10(), s11()]) + "\n"
    with open(os.path.join(OUT, "supplement_tables.md"), "w", encoding="utf-8") as f:
        f.write(t)
    print(t[:6000])
    print(f"... {len(t):,} characters")


if __name__ == "__main__":
    main()
