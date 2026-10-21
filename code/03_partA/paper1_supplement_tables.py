"""Supplementary tables S2-S10 of paper 1, built from the output files (no typed-in numbers).

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
    return ("**Table S3.** Sprawl indicators by group, si/gun medians, 2009–2019 (1999–2009 in parentheses).\n\n"
            + md(["Indicator"] + [EN[g] for g in G], rows) + "\n\nSource: `shrink_sprawl.txt`, block 1.")


def s4():
    s = read("shrink_sprawl.txt")
    rows = []
    for period, start, lab in [("1999–2009 (census population 2000–2010)", "   전기 1999-09", "pre"),
                               ("2009–2019 (registered population 2009–2019)", "후기 (토지 2009-19, 주민등록인구 2009-19)", "post")]:
        i = s.index(start)
        for line in s[i:].splitlines()[1:4]:
            m = re.match(r"\s+(\w+)\s+상수\(인구 증가 0\) \+?(-?[\d.]+), 인구 증가 1%p \+?(-?[\d.]+) \(([\d.]+)\)(\**), "
                         r"감소 시군 기울기 차이 \+?(-?[\d.]+) \(([\d.]+)\)(\**), 감소 시군 절편 차이 \+?(-?[\d.]+) \(([\d.]+)\)(\**)", line)
            if m:
                y = {"new_rate": "New urban land rate (%)", "leap_share": "Leapfrog share (%)", "d_lpcu": "Δ log urban land per resident ×100",
                     "d_lpcu_rp": "Δ log urban land per resident ×100"}.get(m.group(1), m.group(1))
                rows.append([period, y, m.group(2), f"{m.group(3)} ({m.group(4)}){m.group(5)}",
                             f"{m.group(6)} ({m.group(7)}){m.group(8)}", f"{m.group(9)} ({m.group(10)}){m.group(11)}"])
    return ("**Table S4.** Elasticity of sprawl to population growth, all 161 si/gun (OLS, HC1 standard errors).\n\n"
            + md(["Period", "Outcome", "Constant (zero growth)", "Population growth, 1 pp", "Negative growth × growth", "Negative growth (intercept shift)"], rows)
            + "\n\nSpecification: y_i = a + b g_i + c (g_i × N_i) + d N_i + δ ln P_i,2010 + κ C_i + e_i, with g population growth (%), N = 1 if g < 0, P population and C a capital-region indicator; the constant is the prediction at zero growth and mean log population. "
              "Source: `shrink_sprawl.txt`, blocks 2 and 4.")


def s5():
    m = pd.read_csv(os.path.join(A, "supply_demand_models.csv"))
    lab = {("drivers", "g_hh_lag"): "Housing growth on prior household growth", ("drivers", "shrink_lag"): "Housing growth on prior population decline (0/1)",
           ("drivers", "g_hh"): "Housing growth on same-period household growth",
           ("absorb", "g_hh"): "Same-period household growth on housing growth (si/gun FE)", ("absorb", "g_pop"): "Same-period population growth on housing growth (si/gun FE)",
           ("absorb_group", "g_hh"): "Same-period household growth on housing growth, by group",
           ("lead", "s_house"): "Next-period growth on housing growth", ("lead", "g_hh"): "Next-period housing growth on household growth",
           ("inmig", "s_house"): "Net/gross in-migration from outside the si/gun on housing growth"}
    rows = []
    for _, r in m.iterrows():
        rows.append([lab.get((r.block, r.term), r.block), str(r.model).replace("직전 수요만", "prior demand only").replace("+감소 시군", "+ prior decline")
                     .replace("+같은 기간 가구", "+ same-period households").replace("전 기간", "all periods").replace("2010-15 제외", "excl. 2010–15")
                     .replace("감소", "shrinking").replace("정체", "stagnant").replace("성장", "growing").replace("|noFE", ", no si/gun FE").replace("|FE", ", si/gun FE"),
                     r.term, cs(r.coef, r.se, r.p), int(r.n)])
    return ("**Table S5.** Housing supply, household growth and in-migration: all panel models, non-capital provincial si/gun.\n\n"
            + md(["Model", "Specification / outcome", "Term", "Coefficient (s.e.)", "N"], rows)
            + "\n\nsi/gun × five-year periods (2000–05, 2005–10, 2010–15, 2015–19, 2019–24); region × period fixed effects in all models; "
              "standard errors clustered by si/gun. Lead models use four periods (488 observations). Source: `supply_demand_models.csv`.")


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
    return ("**Table S6.** Vacancy panel (2016–2025), all outcomes, and vacancy rates.\n\n"
            + md(["Sample", "Vacancy outcome", "Coefficient (s.e.)", "N (si/gun-years)"], rows)
            + "\n\nPanel B. Vacancy rate (vacant ÷ dwellings, group totals, %).\n\n" + md(["Group"] + hdr, rows2)
            + "\n\n2005 and 2010: field census, denominator SGIS grid dwellings; 2015 onward: register-based census. "
              "Source: `vacancy_models.csv`, `vacancy.txt`.")


def s7():
    c = read("ic_unmet.txt")
    blk = c[c.index("1. 지정 시기별"):c.index("   시군 집단별, 2006년 이후")]
    cols = ["Window", "Complexes", "Designated km²", "Urbanised 2019 (%)", "Industrial land 2022 (%)", "Urbanised before designation (%)",
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
    return ("**Table S7.** Industrial complexes in non-capital provincial si/gun (area-weighted).\n\nPanel A. By designation window.\n\n"
            + md(cols, rows) + "\n\nPanel B. By group.\n\n" + md(["Group (designation)"] + cols[1:], rows2)
            + "\n\nPanel C. Designation and growth, cross-section of 122 si/gun (designated area as % of 2009 urban land; outcome log growth ×100; "
              "controls: outcome growth 2000–05, log population 2000, region; HC1 s.e.).\n\n"
            + md(["Model", "Outcome", "Regressor", "Coefficient (s.e.)", "N"], rows3) + "\n\nSource: `ic_unmet.txt`, `ic_unmet_models.csv`.")


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
          "reserve_on_excess": "Reserve share on planned increase (region FE)", "urban_on_plan": "Urban land growth 2009–19 on 2009 plan (region FE, HC1)",
          "cap_2019": "Planned growth: adopted 2019+ vs earlier (trend and region controlled)"}
    tl = {"trend_g": "Prior 5-year trend", "excess_pct": "Planned increase (%)", "plan_excess": "2009 overstatement (%)",
          "reserve_share09": "2009 reserve ÷ urbanised land (%)", "reserve_share": "2009 reserve ÷ urbanised land (%)", "post": "Adopted 2019 or later"}
    rows2 = [[bl[r.block], tl.get(r.term, r.term), cs(r.coef, r.se, r.p), int(r.n)] for _, r in m.iterrows()]
    return ("**Table S8.** Planned population growth by adoption era, and plan models.\n\n"
            + md(["Group", "Adopted", "Plan vintages", "Planned growth (%/yr)", "Prior trend (%/yr)", "Share projecting growth (%)"], rows)
            + "\n\n" + md(["Model", "Regressor", "Coefficient (s.e.)", "N"], rows2)
            + "\n\nThe 105 percent cap (Directives No. 900, 2017, and No. 1133, 2018) applies to plans whose baseline survey began after the "
              "revisions. Source: `plan_pop.txt`, `plan_pop_models.csv`.")


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
    return ("**Table S9.** Event study of master-plan adoptions: all coefficients (k = −1 omitted; endpoints binned).\n\n"
            + "\n\n".join(out)
            + "\n\nOutcomes are annual flows in percent of the si/gun's median urban zoning area 2008–2025, winsorised at the 1st/99th "
              "percentiles; non-capital provincial si/gun, 2010–2025 (Changwon and Cheongju excluded); si/gun and region × year fixed "
              "effects; standard errors clustered by si/gun. Source: `plan_event_coefs.csv`.")


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
        for l in lines[hi + 1:]:
            q = l.split()
            if q and q[0] in G:
                rows.append([EN[q[0]]] + q[1:])
        keep.append(f"Panel: {title}\n\n" + md(["Group"] + [colmap.get(h, h) for h in hdr], rows))
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


def main():
    os.makedirs(OUT, exist_ok=True)
    t = "\n\n".join([s2(), s3(), s4(), s5(), s6(), s7(), s8(), s9(), s10()]) + "\n"
    with open(os.path.join(OUT, "supplement_tables.md"), "w", encoding="utf-8") as f:
        f.write(t)
    print(t[:6000])
    print(f"... {len(t):,} characters")


if __name__ == "__main__":
    main()
