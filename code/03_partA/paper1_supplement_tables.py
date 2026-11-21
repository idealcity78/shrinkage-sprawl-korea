"""Supplementary tables S2-S13 of paper 1, built from the output files (no typed-in numbers).

Different models never share a panel: each panel holds one model (or one model across samples or outcomes).

  S2  grid population / registered population by group and year (census -> register-census break)
  S3  sprawl indicators by group, both periods (shrink_sprawl.txt block 1)
  S4  elasticity of new urban land to population growth (shrink_sprawl.txt blocks 2 and 4)
  S5  housing supply and demand: all panel models (supply_demand_models.csv)
  S6  vacancy panel, all outcomes and the household-controlled model (vacancy_models.csv); vacancy levels
  S7  industrial complexes by designation window and group; all growth and placebo models (ic_unmet.txt, ic_unmet_models.csv);
      housing-site districts, same layout (hd_unmet.txt, hd_unmet_models.csv)
  S8  plans: planned growth by adoption era (cap), plan-on-trend and cross-section models (plan_pop.txt, plan_pop_models.csv)
  S9  event study: all coefficients k = -4..6, cumulative 0-5 effects and pre-trend tests (plan_event_coefs.csv)
  S10 zoning routes: new urban land, new dwellings and available land by zone; concentration ratios; KOSIS comparison
      (zoning_route.txt)
  S11 innovation and enterprise new towns excluded from the old core (newcity_zones.csv)
  S12 nationwide events in the study period absorbed by the region x period (year) fixed effects (text only)
  S13 every regression with all terms, N, R², fixed effects and s.e. type (replication/data/paper1, from export_model_frames.py)
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
    if not np.isfinite(s):          # e.g. a group of three units: no usable standard error
        return f"{c:.{d}f} (–)"
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
    # Panel A, last column: all si/gun whose registered population fell 2009-19 (any group); last row: share expanding
    t = pd.read_csv(os.path.join(A, "shrink_sprawl_sigun.csv"))
    dn = t[t.g_rp_0919 < 0]
    for r, c in zip(rows, ["g_urb", "new_rate", "leap_share", "dist", "far_share"]):
        r.append(f"{dn[c + '_post'].median():.1f} ({dn[c + '_pre'].median():.1f})")
    grew = lambda d: f"{(d.g_urb_post > 0).mean() * 100:.1f} ({(d.g_urb_pre > 0).mean() * 100:.1f})"
    rows.append(["Si/gun whose urban land grew (%)"] + [grew(t[t.group == g]) for g in G] + [grew(dn)])
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
            + md(["Indicator"] + [EN[g] for g in G] + [f"All si/gun with falling population, 2009–19 ({len(dn)})"], rows)
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
                  "Expansion 2009–19 + core decline 2015–24", "+ population decline 2015–24"], rows_d)
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
    n_all = max(r[-1] for r in rows)
    return (f"**Table S4.** Elasticity of sprawl to population growth, all {n_all} si/gun (OLS, HC1 standard errors).\n\n"
            + md(["Period", "Outcome", "Prediction at zero growth", "(a) Constant", "(b) Population growth g, 1 pp",
                  "(c) g × N", "(d) N (negative growth)", "(δ) ln P 2010", "(κ) Capital region C", "N (si/gun)"], rows)
            + "\n\nSpecification (equation 5): y_i = a + b g_i + c (g_i × N_i) + d N_i + δ ln P_i,2010 + κ C_i + e_i, with g "
              "population growth (%), N = 1 if g < 0, P population in 2010 and C = 1 for capital-region si/gun. The constant a "
              "is the value at ln P = 0 and has no direct meaning; the prediction at zero growth is a + δ × mean(ln P), the "
              "expected outcome of a non-capital si/gun of mean size whose population did not change, with its delta-method "
              "standard error. Source: `shrink_sprawl_models.csv`, blocks elasticity_full_pre and elasticity_full_rp_post.")


def pick(m, **kw):
    """The one row of a model table matching every column=value given."""
    d = m
    for k, v in kw.items():
        d = d[d[k] == v]
    if len(d) != 1:
        raise ValueError(f"expected one row for {kw}, found {len(d)}")
    return d.iloc[0]


def cell(r):
    return cs(r.coef, r.se, r.p)


def ci95(r, k=3):
    """Normal 95% interval of a coefficient, as the models report normal-based p-values."""
    return f"[{r.coef - 1.959964 * r.se:.{k}f}, {r.coef + 1.959964 * r.se:.{k}f}]"


def supply_panels(m, ci=False):
    """Lead/reverse and in-migration panels, shared by Table 3 of the paper and Table S5 (which adds 95% intervals)."""
    lead = [["Next-period household growth", "Housing growth", "g_hh_lead"],
            ["Next-period population growth", "Housing growth", "g_pop_lead"],
            ["Next-period housing growth", "Household growth", "s_house_lead"]]
    rows_l = []
    for y, x, key in lead:
        r0, r1 = pick(m, block="lead", model=key + "|noFE"), pick(m, block="lead", model=key + "|FE")
        rows_l.append([y, x, cell(r0), cell(r1)] + ([ci95(r1)] if ci else []) + [int(r1.n)])
    rows_m = []
    for lab, key in [("Net in-migration", "sg_net"), ("Gross in-migration", "sg_in")]:
        r0, r1 = pick(m, block="inmig", model=key), pick(m, block="inmig", model=key + "_lead")
        rows_m.append([lab, cell(r0), cell(r1)])
        if ci:
            rows_m.append([f"{lab}: 95% confidence interval", ci95(r0), ci95(r1)])
    rows_m.append(["N (si/gun-periods)", int(r0.n), int(r1.n)])
    return (md(["Outcome", "Regressor", "Without si/gun FE", "With si/gun FE"] + (["95% CI, with si/gun FE"] if ci else [])
               + ["N (si/gun-periods)"], rows_l),
            md(["Outcome (per 1,000 residents a year)", "Same period", "Next period"], rows_m))


LEAD_NOTE = ("si/gun × five-year periods; each model also controls for the current-period value of the outcome variable "
             "(e.g. household growth in t when the outcome is household growth in t+1); region × period fixed effects in "
             "both columns; standard errors clustered by si/gun.")
INMIG_NOTE = ("moves from outside the si/gun (MDIS) per 1,000 residents a year on annual housing growth (1 pp); si/gun and "
              "region × period fixed effects; the next-period model also controls for the same-period outcome; standard "
              "errors clustered by si/gun.")


IC_Y = {"manuf": "Manufacturing employment", "emp": "All employment", "pop": "Population", "hh": "Households"}
IC_NOTE = ("OLS with HC1 s.e.; all models control for log population 2000 and region. Growth and placebo models also "
           "control for the outcome's growth 2000–05 and the area designated before 2001; the 2010–24 models include the "
           "areas designated in 2001–05 and 2006–12 together (and, in the placebo, 2016–24).")


def ic_panels(m, ys=tuple(IC_Y), full=True):
    """Designation-growth models with outcomes as columns: growth and placebo rows, and the reverse model."""
    spec = [("growth", "ic_0612", "Growth 2010–24", "Designated 2006–12")]
    if full:
        spec.append(("growth", "ic_0105", "Growth 2010–24", "Designated 2001–05"))
    spec += [("placebo_0515", "ic_1624", "Placebo: growth 2005–15", "Designated 2016–24"),
             ("placebo_1024", "ic_1624", "Placebo: growth 2010–24", "Designated 2016–24")]
    has = lambda b, y, t: ((m.block == b) & (m.y == y) & (m.term == t)).any()
    rows = [[lab, reg] + [cell(pick(m, block=b, y=y, term=t)) if has(b, y, t) else "" for y in ys] for b, t, lab, reg in spec]
    rev = [["Reverse: designation 2006–12", "Prior growth 2000–05 of the outcome"]
           + [cell(pick(m, block="reverse", y=y, term=f"pre_{y}")) if has("reverse", y, f"pre_{y}") else "" for y in ys]]
    return rows, rev


HD_Y = {"hh": "Households", "pop": "Population", "house": "Dwellings"}
HD_X = {"hd": "area (% of 2009 urban land)", "u": "planned dwellings (% of 2005 households)"}


def hd_panels(m):
    """ic_panels for the housing-site districts: both measures of designation, growth, placebo and reverse rows."""
    has = lambda b, y, t: ((m.block == b) & (m.y == y) & (m.term == t)).any()
    get = lambda b, y, t: cell(pick(m, block=b, y=y, term=t)) if has(b, y, t) else ""
    rows = []
    for x, xl in HD_X.items():
        for b, t, lab, reg in [("growth", f"{x}_0612", "Growth 2010–24", "Started 2006–12"),
                               ("growth", f"{x}_0105", "Growth 2010–24", "Started 2001–05"),
                               ("placebo_0515", f"{x}_1624", "Placebo: growth 2005–15", "Started 2016–24"),
                               ("placebo_1024", f"{x}_1624", "Placebo: growth 2010–24", "Started 2016–24")]:
            rows.append([lab, f"{reg}, {xl}"] + [get(b, y, t) for y in HD_Y])
        rows.append([f"Reverse: started 2006–12, {xl}", "Prior growth 2000–05 of the outcome"]
                    + [get(f"reverse_{x}", y, f"pre_{y}") for y in HD_Y])
    return rows

# ---- robustness panels added after the mock review of 2026-11-21 (supply_demand.py block (e), robust_review.py,
# plan_event.py robustness block, zoning_route_robust.py)
ROB_SPECS = [("FE, no lagged outcome", "Unit FE, no lagged outcome"),
             ("same census method, no unit FE", "Period pairs within one census method, no unit FE"),
             ("shrinking, unit FE", "Shrinking only, unit FE"), ("shrinking, no unit FE", "Shrinking only, no unit FE")]


def s5_robust():
    m = pd.read_csv(os.path.join(A, "supply_demand_models.csv"))
    m = m[m.block == "lead_robust"]
    ys = [("g_hh_lead", "Next-period household growth on housing growth"),
          ("g_pop_lead", "Next-period population growth on housing growth"),
          ("s_house_lead", "Next-period housing growth on household growth")]
    rows = [[lab] + [cell(pick(m, model=f"{y}|{k}")) for k, _ in ROB_SPECS] for y, lab in ys]
    rows.append(["N (si/gun-periods)"] + [int(pick(m, model=f"g_hh_lead|{k}").n) for k, _ in ROB_SPECS])
    return ("\n\nPanel F. Robustness of the lead and reverse regressions: coefficient on the regressor named in each row.\n\n"
            + md(["Model"] + [lab for _, lab in ROB_SPECS], rows)
            + "\n\nPanel F: with four periods, unit fixed effects and the lagged outcome, equations (6)–(7) carry Nickell (1981) "
              "bias. Column 1 drops the lagged outcome; column 2 keeps only 2000–05 → 2005–10 and 2015–19 → 2019–24, so that no "
              "pair straddles the 2010–15 change of census method; columns 3–4 use shrinking si/gun only. Region × period fixed "
              "effects throughout; standard errors clustered by si/gun. Source: `supply_demand.txt`, block (e).")


def s6_robust():
    m = pd.read_csv(os.path.join(A, "robust_review_models.csv"))
    lag = m[m.block == "vacancy_lags"]
    rows = []
    for smp in ["감소", "정체", "성장", "비수도권 도 시군"]:
        d = lag[lag["sample"] == smp].set_index("term")
        rows.append([EN.get(smp, "Non-capital provincial")] + [cs(d.at[t, "coef"], d.at[t, "se"], d.at[t, "p"])
                                                               for t in ("s", "s_l1", "s_l2", "sum")] + [int(d.n.iloc[0])])
    hh = m[m.block == "vacancy_hh"].set_index("sample")
    rows_h = [[EN[g], cs(hh.at[g, "coef"], hh.at[g, "se"], hh.at[g, "p"]), int(hh.at[g, "n"])] for g in ("감소", "정체", "성장")]
    vg = m[m.block == "vacancy_group"]
    rows_g = []
    for smp, lab in [("본문 집단", "Groups by population change 2000–19 (main)"),
                     ("사전 집단", "Groups by population change 1992–2000")]:
        d = vg[vg["sample"] == smp].set_index("term")
        rows_g.append([lab] + [cs(d.at[g, "coef"], d.at[g, "se"], d.at[g, "p"]) if np.isfinite(d.at[g, "coef"]) else "–"
                               for g in ("감소", "정체", "성장")])
    rows_n = []
    for y, ylab in [("d_vac_new5", "Built in last 5 years"), ("d_vac", "All vacancies")]:
        lg = m[m.block == f"vacancy_lags_{y}"]
        for smp in ["감소", "정체", "성장", "비수도권 도 시군"]:
            d = lg[lg["sample"] == smp].set_index("term")
            rows_n.append([ylab, EN.get(smp, "Non-capital provincial")]
                          + [cs(d.at[t, "coef"], d.at[t, "se"], d.at[t, "p"]) for t in ("s", "s_l1", "s_l2", "sum")]
                          + [int(d.n.iloc[0])])
    rows_d = []
    for x, xlab in [("g5", "Prior 5-year population change (%/yr)"), ("dec5", "Prior 5-year population decline (0/1)")]:
        dd = m[m.block == f"vacancy_decline_{x}"]
        for smp, slab in [("비수도권 도 시군", "Non-capital provincial"), ("전체 시군", "All si/gun")]:
            d = dd[dd["sample"] == smp].set_index("term")
            rows_d.append([xlab, slab, cs(d.at["s", "coef"], d.at["s", "se"], d.at["s", "p"]),
                           cs(d.at[f"s:{x}", "coef"], d.at[f"s:{x}", "se"], d.at[f"s:{x}", "p"]), int(d.n.iloc[0])])
    vm = pd.read_csv(os.path.join(A, "vacancy_models.csv"))
    tr = vm[vm.block == "location"].set_index("sample")
    ut = vm[vm.block == "location_untrimmed"].set_index("sample")
    rows_u = []
    for smp, lab in [("감소", "Shrinking"), ("정체", "Stagnant"), ("성장", "Growing"),
                     ("광역시+수도권", "Metropolitan and capital region")]:
        a = tr[tr.y == "d_vac_old"].loc[smp]
        b = ut.loc[smp]
        rows_u.append([lab, cs(a.coef, a.se, a.p), int(a.n), cs(b.coef, b.se, b.p), int(b.n)])
    t = read("robust_review.txt")
    ct = re.search(r"All\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", t)
    g5 = re.search(r"평균 ([+\-][\d.]+), 사분위 범위 ([+\-][\d.]+) ~ ([+\-][\d.]+)", t)
    dr = re.search(r"뺀 시군-연도 (\d+): (.+)", read("vacancy.txt"))
    names = {"과천시": "Gwacheon", "세종시": "Sejong", "하남시": "Hanam"}
    dropped = ", ".join(f"{names.get(a, a)} {b}" for a, b in re.findall(r"(\S+) (\d{4})", dr.group(2)))
    return ("\n\nPanel F. Persistence: change in pre-2000 vacancies on net additions in the same and the two previous years "
            "(per 1,000 dwellings), 2018–2025.\n\n"
            + md(["Sample", "Net additions, t", "t−1", "t−2", "Sum", "N (si/gun-years)"], rows)
            + "\n\nPanel F (continued). Equation 8 with household change per 1,000 dwellings as a control, 2020–24, by group.\n\n"
            + md(["Group", "Net additions per 1,000 dwellings", "N (si/gun-years)"], rows_h)
            + "\n\nPanel F (continued). The same lag model for vacancies in dwellings built in the last five years and for all "
              "vacancies.\n\n"
            + md(["Outcome", "Sample", "Net additions, t", "t−1", "t−2", "Sum", "N (si/gun-years)"], rows_n)
            + "\n\nPanel G. Equation 8 for pre-2000 vacancies with groups defined from the pre-period.\n\n"
            + md(["Grouping", "Shrinking", "Stagnant", "Growing"], rows_g)
            + f"\n\nPanel G: groups by registered-population change 1992–2000, decline below −2 percent and growth above +2 "
              f"percent (the main rule's ±5 percent over 19 years scaled to 8 years); declining {ct.group(1)}, growing "
              f"{ct.group(2)}, stagnant {ct.group(3)} of {ct.group(4)} si/gun; the model is not estimated for the stagnant group, "
              "whose few units are absorbed by the fixed effects."
            + "\n\nPanel H. Decline as it happens: change in pre-2000 vacancies on net additions and their interaction with the "
              "unit's registered-population change over the five years before the panel year, si/gun and region × year "
              "fixed effects.\n\n"
            + md(["Interaction variable", "Sample", "Net additions", "Net additions × interaction variable", "N (si/gun-years)"],
                 rows_d)
            + "\n\nPanel I. Equation 8 for pre-2000 vacancies with and without the unit-years excluded from the panel.\n\n"
            + md(["Group", "Panel as estimated", "N", "No exclusion", "N"], rows_u)
            + f"\n\nPanel H: population change is annualised from year y−6 to y−1 (registered population, December); among "
              f"non-capital provincial unit-years its mean is {g5.group(1)} percent a year and its interquartile range "
              f"{g5.group(2)} to {g5.group(3)}. Panel I: the panel excludes unit-years whose net additions lie outside −100 "
              f"to 200 per 1,000 dwellings, which reflect boundary changes or large redevelopment ({int(dr.group(1))} "
              f"unit-years: {dropped}). Source: `robust_review.txt`, `robust_review_models.csv`, `vacancy.txt`.")


def s9_robust():
    r = pd.read_csv(os.path.join(A, "plan_event_robust.csv"))
    tn = {"adopt": "Any new plan", "res_up": "New plan enlarging the reserve"}
    yn = {"zone": "Urban-use zoning", "devp": "Land-form-change permits"}
    sn = {"전체": "All si/gun", "계획 있는 시군": "si/gun that adopted a plan in 2006–2025"}
    rows = [[tn[x.treat], yn[x.y], f"{sn[x['sample']]} ({x.units})", cs(x.cum, x.se, x.p), f"{x.mde:.2f}",
             f"{x.mean_y * 6:.2f}", f"{x.pre_p:.2f}", int(x.n)] for _, x in r.iterrows()]
    return ("\n\nPanel F. Robustness: units with a plan vintage only, and minimum detectable cumulative effects.\n\n"
            + md(["Event", "Outcome", "Sample (si/gun)", "Cumulative 0–5 (s.e.)", "Minimum detectable effect",
                  "Mean six-year flow", "Pre-trend F p", "N"], rows)
            + "\n\nPanel F: minimum detectable effect = 2.8 × s.e. of the cumulative effect (5 percent two-sided test, 80 "
              "percent power); mean six-year flow = 6 × the sample mean of the annual outcome. Source: `plan_event_robust.csv`.")


def s10_robust():
    z = pd.read_csv(os.path.join(A, "zoning_route_robust_summary.csv"))
    val = lambda tb, ms, g: z[(z.table == tb) & (z.measure == ms) & (z.group == g)].value.iloc[0]
    meas = [("offplan_land", "전체 (본문)", "New urban land, all (Panel A)"),
            ("offplan_land", "주거·공업·상업 용도 (2022 중분류)", "New urban land in residential, industrial or commercial use (2022)"),
            ("offplan_land", "주거 용도만", "New urban land in residential use (2022)"),
            ("offplan_land", "2015-24 주택·종사자가 는 셀", "New urban land in cells that gained dwellings or employees 2015–24"),
            ("offplan_dwellings", "셀 증가의 합 (본문)", "Dwellings added outside the old core, sum of cell increases (Panel B)"),
            ("offplan_dwellings", "5호 이상 증가 셀", "Dwellings added outside the old core, cells gaining at least 5"),
            ("offplan_dwellings", "순증가", "Dwellings added outside the old core, net change")]
    rows = [[lab] + [f"{val(tb, ms, g):.1f}" for g in G] for tb, ms, lab in meas]
    rows_o = [[lab] + [f"{val('outside_old_core', ms, g):.1f}" for g in G] for ms, lab in
              [("셀 증가의 합", "Sum of cell increases (Table S3, Panel B)"), ("5호 이상 증가 셀", "Cells gaining at least 5"),
               ("순증가", "Net change")]]
    l2n = ["Residential", "Industrial", "Commercial", "Cultural and leisure", "Transport", "Public facilities"]
    rows_c = []
    for part, lab in [("composition_all", "all"), ("composition_offplan", "outside res./com./ind.")]:
        rows_c += [[f"{EN[g]} ({lab})"] + [f"{val(part, c, g):.1f}" for c in l2n] for g in G]
    gr = pd.read_csv(os.path.join(A, "zoning_route_robust_grid.csv"))
    gr["group"] = gr.SG_ID.map(pd.read_csv(os.path.join(A, "zoning_route_sigun.csv")).set_index("SG_ID").group)
    rl = {"A": "Res./com./ind. zones", "B": "Natural green", "C": "Other green, unsubdivided urban",
          "D": "Planned management", "E": "Production/conservation management", "F": "Agricultural/natural conservation, other"}
    ge = gr.groupby("group")[[f"ge5_{r}" for r in rl]].sum()
    ge = ge.div(ge.sum(axis=1), axis=0) * 100
    rows_f5 = [[EN[g]] + [f"{ge.at[g, f'ge5_{r}']:.1f}" for r in rl] for g in G]
    m = pd.read_csv(os.path.join(A, "robust_review_models.csv"))
    rows_j = []
    for c, lab in [("new_res", "Residential new urban land 2009–19 (2022 map)"),
                   ("ge5", "Dwellings added outside the old core 2015–24, cells gaining at least 5"),
                   ("net", "Dwellings added outside the old core 2015–24, net change")]:
        d = m[m.block == f"offplan_{c}"].set_index("sample")
        rows_j.append([lab] + [cs(d.at[s, "coef"], d.at[s, "se"], d.at[s, "p"], 1) for s in ("기본", "통제")] + [int(d.at["기본", "n"])])
    ol = m[m.block == "offplan_land"].set_index("sample")
    od = m[m.block == "offplan_dwellings_ge5"]
    rows_i = [[lab, cs(ol.at[smp, "coef"], ol.at[smp, "se"], ol.at[smp, "p"], 1)]
              + [f"{od[(od['sample'] == smp) & (od.term == g)].coef.iloc[0]:.1f}" for g in ("감소", "정체", "성장")]
              for smp, lab in [("본문 집단", "Groups by population change 2000–19 (main)"),
                               ("사전 집단", "Groups by population change 1992–2000")]]
    return ("\n\nPanel G. Off-plan shares (%, outside residential, commercial and industrial zones) under alternative measures.\n\n"
            + md(["Measure"] + [EN[g] for g in G], rows)
            + "\n\nPanel G (continued). Share of new dwellings 2015–2024 built outside the old core (%), by measure.\n\n"
            + md(["Measure"] + [EN[g] for g in G], rows_o)
            + "\n\nPanel G (continued). Dwellings added outside the old core 2015–2024 in cells gaining at least 5, by 2026 "
              "zoning (%; Figure 5b).\n\n"
            + md(["Group"] + list(rl.values()), rows_f5)
            + "\n\nPanel H. Land use in 2022 of new urban land 2009–2019 (%, middle-class land-cover map).\n\n"
            + md(["Group (new urban land)"] + l2n, rows_c)
            + "\n\nPanel I. Groups defined from the pre-period: shrinking-versus-growing gap in the off-plan share of new "
              "urban land (model of Panel F, row 1) and off-plan share of dwellings in cells gaining at least 5 (%).\n\n"
            + md(["Grouping", "Gap in new urban land (pp)", "Dwellings, shrinking", "Dwellings, stagnant", "Dwellings, growing"],
                 rows_i)
            + "\n\nPanel J. Shrinking-versus-growing gap (pp) in the off-plan share of residential land and of dwellings, "
              "non-capital provincial si/gun; models of Panel F with the measure's log size in place of log new urban land.\n\n"
            + md(["Off-plan share of", "Region FE and log size", "+ controls of Panel F, row 2", "N (si/gun)"], rows_j)
            + "\n\nPanels G–J: the sum of cell increases counts every cell that gained dwellings, including small counts that "
              "move in and out of the suppression range (1–4) between years; cells gaining at least 5 remove most of this "
              "noise, and the net change also subtracts dwellings lost in other cells (demolition, abandonment). Each cell of "
              "new urban land is split across the urban classes of the 2022 middle-class map in proportion to their shares "
              "of the cell. Groups in Panel I as in Table S6, Panel G. Source: `zoning_route_robust.txt`, "
              "`zoning_route_robust_summary.csv`, `robust_review.txt`. Totals in Tables S10 and S11 can differ from Table S3 "
              "and from each other by up to 0.6 percent, because the zoning tables split each 100-metre cell across "
              "zoning polygons on a 10-metre subgrid, whereas Tables S3 and S11 assign whole cells.")


def s5():
    m = pd.read_csv(os.path.join(A, "supply_demand_models.csv"))
    d0 = re.search(r"주택 증가율 ([\d.]+)%/년, 가구 증가율 ([\d.]+)%/년; 비감소 ([\d.]+), ([\d.]+)", read("supply_demand.txt"))
    desc = [["Population decline", d0.group(1), d0.group(2)], ["No population decline", d0.group(3), d0.group(4)]]
    # Panel B: what drives housing supply, three nested specifications as columns
    specs = ["직전 수요만", "+감소 시군", "+같은 기간 가구"]
    rows_b = []
    for t, lab in [("g_hh_lag", "Prior-period household growth"), ("shrink_lag", "Prior-period population decline (0/1)"),
                   ("g_hh", "Same-period household growth")]:
        rows_b.append([lab] + [cell(pick(m, block="drivers", model=s, term=t)) if ((m.block == "drivers") & (m.model == s) & (m.term == t)).any()
                               else "" for s in specs])
    rows_b.append(["N (si/gun-periods)"] + [int(pick(m, block="drivers", model=s, term="g_hh_lag").n) for s in specs])
    # Panel C: same-period growth on housing growth with si/gun fixed effects, by sample
    cols = [("absorb", "전 기간"), ("absorb", "2010-15 제외"), ("absorb_group", "감소"), ("absorb_group", "정체"), ("absorb_group", "성장")]
    rows_c = []
    for y, lab in [("g_hh", "Household growth"), ("g_pop", "Population growth")]:
        rows_c.append([lab] + [cell(pick(m, block=b, model=s, term=y)) if ((m.block == b) & (m.model == s) & (m.term == y)).any()
                               else "" for b, s in cols])
    rows_c.append(["N (si/gun-periods)"] + [int(pick(m, block=b, model=s, term="g_hh").n) for b, s in cols])
    pl, pm = supply_panels(m, ci=True)
    return ("**Table S5.** Housing supply, household growth and in-migration, non-capital provincial si/gun, five-year periods.\n\n"
            + "Panel A. Mean annual growth in the five-year period following one with and without registered-population "
              "decline (%/yr).\n\n" + md(["Previous period", "Housing stock", "Households"], desc)
            + "\n\nPanel B. What drives housing supply: annual housing growth (%) on demand (region × period fixed effects, "
              "no si/gun fixed effects).\n\n"
            + md(["Regressor", "(1) Prior demand only", "(2) + prior decline", "(3) + same-period households"], rows_b)
            + "\n\nPanel C. Same-period growth (%/yr) on annual housing growth (1 pp), si/gun and region × period fixed effects.\n\n"
            + md(["Outcome", "All periods", "Excl. 2010–15", "Shrinking", "Stagnant", "Growing"], rows_c)
            + "\n\nPanel D. Lead and reverse regressions (equations 6–7).\n\n" + pl
            + "\n\nPanel E. In-migration from outside the si/gun and housing growth.\n\n" + pm
            + "\n\nPeriods 2000–05, 2005–10, 2010–15, 2015–19 and 2019–24; models with a prior or next period use four periods. "
              "Annual growth g = 100 × [(x_t1/x_t0)^(1/n) − 1] of gridded dwellings and households. Standard errors clustered by "
              f"si/gun in Panels B–C. Panel D: {LEAD_NOTE} Panel E: {INMIG_NOTE} Blank cells: term not in the model. "
              "Source: `supply_demand.txt`, block 2; `supply_demand_models.csv`." + s5_robust())


def s6():
    m = pd.read_csv(os.path.join(A, "vacancy_models.csv"))
    yl = {"d_vac": "All vacancies", "d_vac_old": "Pre-2000 dwellings", "d_vac_new5": "Built in last 5 years"}
    main_, hh = m[m.block == "location"], m[m.block == "location_hh"]
    rows = []
    for smp in dict.fromkeys(main_["sample"]):
        d = main_[main_["sample"] == smp].set_index("y")
        rows.append([EN.get(smp, smp)] + [cs(d.at[y, "coef"], d.at[y, "se"], d.at[y, "p"]) if y in d.index else "" for y in yl]
                    + [int(d.n.iloc[0])])
    rows_h = [[EN.get(r["sample"], r["sample"]), yl[r.y], cs(r.coef, r.se, r.p), int(r.n)] for _, r in hh.iterrows()]
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
            + "Panel A. Change in vacant dwellings per 1,000 dwellings on net additions per 1,000 dwellings (equation 8), by "
              "construction cohort of the vacant dwellings; si/gun and region × year fixed effects, s.e. clustered by si/gun.\n\n"
            + md(["Sample"] + list(yl.values()) + ["N (si/gun-years)"], rows)
            + "\n\nPanel B. Robustness: equation 8 with annual household change per 1,000 dwellings as a control, 2020–24 "
              "(years with annual household counts).\n\n"
            + md(["Sample", "Vacancy outcome", "Coefficient (s.e.)", "N (si/gun-years)"], rows_h)
            + "\n\nPanel C. Vacancy rate (vacant ÷ dwellings, group totals, %).\n\n" + md(["Group"] + hdr, rows2)
            + "\n\n2005 and 2010: field census, denominator SGIS grid dwellings; 2015 onward: register-based census."
            + "\n\nPanel D. Vacant dwellings built before 2000: share of all vacancies (%) and number per 1,000 dwellings.\n\n"
            + md(["Group", "Share 2015", "Per 1,000 2015", "Share 2019", "Per 1,000 2019", "Share 2024", "Per 1,000 2024"], rows3)
            + "\n\nPanel E. Long-term vacancy and unsold new housing.\n\n"
            + md(["Group", "Vacant 12 months or longer, share of vacancies 2010 (%)",
                  "si/gun with unsold dwellings above 10 per 1,000 in any year 2007–2025 (%)"], rows4)
            + "\n\nSource: `vacancy_models.csv`, `vacancy.txt`." + s6_robust())


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
    sec = "from 2006"
    for line in blk2.splitlines():
        if "2005년 이전" in line:
            sec = "before 2006"
        p = line.split()
        if p and p[0] in ("감소", "정체", "성장"):
            rows2.append([f"{EN[p[0]]} ({sec})", p[1][:-2]] + p[2:])
    m = pd.read_csv(os.path.join(A, "ic_unmet_models.csv"))
    rows3, rows4 = ic_panels(m, full=True)
    tot = re.search(r"산업단지 (\d+)개, 지정 면적 (\d+) km2", c)
    h = read("hd_unmet.txt")
    hcols = ["Start", "Districts", "Area km²", "Planned dwellings", "Urban in 1999 (%)", "Urbanised 2019 (%)",
             "Dwellings 2024, all districts", "Realised (% of planned)", "Dwelling increase 2010–24", "Completed (%)"]
    blk = h[h.index("1. 시작 시기별"):h.index("   시군 집단별, 2006년 이후")]
    rows5 = []
    for line in blk.splitlines():
        p = line.split()
        if p and re.match(r"(~1990|\d{4}-\d{2,4}|2021-)$", p[0]):
            rows5.append([p[0].replace("-", "–"), p[1][:-2]] + p[2:])
    blk = h[h.index("   시군 집단별, 2006년 이후"):h.index("   법별")]
    rows6, sec = [], "from 2006"
    for line in blk.splitlines():
        if "2005년 이전" in line:
            sec = "before 2006"
        p = line.split()
        if p and p[0] in ("감소", "정체", "성장"):
            rows6.append([f"{EN[p[0]]} ({sec})", p[1][:-2]] + p[2:])
    rows7 = []
    for a, rest in re.findall(r"   (\d{4}-\d{4}): (.+)", h):
        sh = dict((g, (i, t, s)) for g, i, t, s in re.findall(r"(\S+) ([\d,]+) / ([\d,]+) = ([\d.]+)%", rest))
        rows7.append([a.replace("-", "–")] + [f"{sh[g][2]} ({sh[g][0]} of {sh[g][1]})" for g in ("감소", "정체", "성장")])
    rows8 = hd_panels(pd.read_csv(os.path.join(A, "hd_unmet_models.csv")))
    ht = re.search(r"주택 지구 (\d+)개 \(격자 셀 있음\), 지정 면적 ([\d.]+) km2, 계획 ([\d,]+)호.*계획 호수 없음 또는 0 (\d+)", h)
    hd_text = ("\n\nPanel E. Housing-site districts by start year (area-weighted shares).\n\n" + md(hcols, rows5)
               + "\n\nPanel F. Housing-site districts by group.\n\n" + md(["Group (start)"] + hcols[1:], rows6)
               + "\n\nPanel G. Share of the increase in dwellings that lay inside housing-site districts (%; dwellings "
                 "inside ÷ all added, group totals).\n\n" + md(["Period"] + [EN[g] for g in ("감소", "정체", "성장")], rows7)
               + "\n\nPanel H. District start and later growth, cross-section of 123 si/gun: log growth ×100 of each "
                 "column's outcome on the area or the planned dwellings of the districts started in each window; reverse "
                 "rows regress the 2006–12 measure on the outcome's prior growth.\n\n"
               + md(["Model", "Regressor"] + list(HD_Y.values()), rows8)
               + f"\n\nPanels E–H: {ht.group(1)} housing-site districts on the grid ({ht.group(2)} km², "
                 f"{ht.group(3)} planned dwellings): districts under the Housing Site Development Promotion Act, the Urban "
                 "Development Act, the Special Act on Public Housing and the Private Rental Housing Act (source 18). The start "
                 "year is the designation date, or the earliest plan approval where the designation date is missing. "
                 f"Realised = dwellings in the district cells in 2024 (SGIS grid) ÷ planned dwellings, over the districts with "
                 f"a planned number ({ht.group(4)} districts have none), so it is not the ratio of the two preceding "
                 "columns; completed = share of districts with a completion "
                 "date. Panel H models as in Panel C, with the outcome's growth 2000–05, log population 2000, region and the "
                 "earlier windows as controls. Panels E and F leave out the "
                 f"{int(ht.group(1)) - sum(int(r[1].replace(',', '')) for r in rows5)} districts with neither a designation "
                 "nor a plan date. Source: `hd_unmet.txt`, `hd_unmet_models.csv`.")
    return ("**Table S7.** Industrial complexes and housing-site districts in non-capital provincial si/gun.\n\n"
            "Panel A. Industrial complexes by designation window (area-weighted).\n\n"
            + md(cols, rows) + "\n\nPanel B. By group.\n\n" + md(["Group (designation)"] + cols[1:], rows2)
            + "\n\nPanel C. Designation and later growth, cross-section of 123 si/gun: log growth ×100 of each column's outcome "
              "on designated area (% of 2009 urban land).\n\n"
            + md(["Model", "Regressor"] + list(IC_Y.values()), rows3)
            + "\n\nPanel D. Reverse model: area designated in 2006–12 (% of 2009 urban land) on the outcome's prior growth "
              "2000–05 (log ×100), 123 si/gun.\n\n"
            + md(["Model", "Regressor"] + list(IC_Y.values()), rows4)
            + f"\n\n{IC_NOTE} Blank cells: not estimated."
            + f"\n\nAll windows: {tot.group(1)} complexes, {tot.group(2)} km² designated; Panel B leaves out the "
              f"{int(tot.group(1)) - sum(int(r[1].replace(',', '')) for r in rows2)} complexes without a designation year or "
              "mapped area, which Panel A counts in its first row. Area-weighted shares: urbanised 2019 and "
              "industrial land 2022 are the shares of designated area that are urban land in the 2019 large-class land-cover map "
              "and industrial use in the 2022 middle-class map; urban in 1999 is the share urban in the late-1990s map, which "
              "precedes designation for complexes designated after 2000 but not for many earlier ones. Sale rate = sold ÷ saleable "
              "industrial area, operating = operating ÷ resident firms, both summed over the complexes matched to the KICOX "
              "statistics (June 2026). "
              + "The sale rate measures land sold, not land built on: for complexes designated in 2006–10 the saleable "
                "industrial area is {} percent of the designated area of the matched complexes, which are {} percent "
                "urbanised in 2019 and {} percent in industrial use in 2022. ".format(
                    *re.search(r"2006-10 지정 연결: [^\n]*2019 시가화 ([\d.]+)%, 2022 공업용지 ([\d.]+)%, 분양률 [\d.]+%, "
                               r"분양 대상 / 지정 면적 ([\d.]+)%", read("robust_review.txt")).group(3, 1, 2))
              + "Manufacturing workers are gridded employees times the manufacturing share of the enclosing 1 km cell. "
              "Source: `ic_unmet.txt`, `ic_unmet_models.csv`." + hd_text)


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
        rows.append([EN[g], q[0].replace("-", "–")] + q[1:-1] + [f"{float(q[-1]):.1f}"])   # share of plans: one decimal
    m = pd.read_csv(os.path.join(A, "plan_pop_models.csv"))
    ln = lambda r: int(r.n)
    pt = [pick(m, block="plan_on_trend", term=t) for t in ("trend_g", "Intercept", "pred_zero_trend")]
    rows_c = [["Prior 5-year trend (1 pp)", cell(pt[0])],
              ["Constant (zero trend, reference region)", cell(pt[1])],
              ["Prediction at zero trend, mean over regions", cell(pt[2])],
              ["N (plans)", ln(pt[0])]]
    cp = pick(m, block="cap_2019", term="post")
    rows_d = [["Adopted 2019 or later", cell(cp)], ["N (plans)", ln(cp)]]
    re_ = pick(m, block="reserve_on_excess", term="excess_pct")
    rows_e = [["Planned increase (% of population at adoption)", cell(re_)], ["N (plans)", ln(re_)]]
    ox, rs = pick(m, block="urban_on_plan", term="plan_excess"), pick(m, block="urban_on_plan", term="reserve_share")
    gx, gr = pick(m, block="urban_on_plan_plan_excess", term="g_reg"), pick(m, block="urban_on_plan_reserve_share", term="g_reg")
    rows_f = [["2009 overstatement (%)", cell(ox), ""], ["2009 reserve ÷ urbanised land (%)", "", cell(rs)],
              ["Realised population change 2009–19 (%)", cell(gx), cell(gr)], ["N (si/gun)", ln(ox), ln(rs)]]
    # how large a plan effect the estimates rule out: 95% limits times the interquartile range of the plan term,
    # next to the effect of an interquartile difference in realised population change
    iq = pick(m, block="urban_on_plan_scale", term="g_reg").iqr
    ci = lambda r: f"[{r.lo:.3f}, {r.hi:.3f}]"
    bd = lambda r: f"[{r.lo * r.iqr:.1f}, {r.hi * r.iqr:.1f}]"
    rows_f += [["95% confidence interval of the plan term", ci(ox), ci(rs)],
               ["Interquartile range of the plan term (pp)", f"{ox.iqr:.1f}", f"{rs.iqr:.1f}"],
               ["Effect of an interquartile difference in the plan term, 95% bounds (pp)", bd(ox), bd(rs)],
               ["Effect of an interquartile difference in realised population change (pp)",
                f"{gx.coef * iq:.1f}", f"{gr.coef * iq:.1f}"],
               ["Median urban land growth 2009–19 (%)", *[f"{pick(m, block='urban_on_plan_scale', term='new_urb_median').coef:.1f}"] * 2]]
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
            + "\n\nPanel C. Planned growth (%/yr) on the prior 5-year trend (%/yr): non-capital provincial plans adopted "
              "since 2000, region fixed effects, s.e. clustered by si/gun.\n\n" + md(["Term", "Coefficient (s.e.)"], rows_c)
            + "\n\nPanel D. The 2017–2018 cap: planned growth (%/yr) on adoption in 2019 or later, controlling for the prior "
              "trend and region; non-capital provincial plans adopted 2005–2025, s.e. clustered by si/gun.\n\n"
            + md(["Term", "Coefficient (s.e.)"], rows_d)
            + "\n\nPanel E. Reserve share (reserve ÷ urbanised land in the plan, %) on the planned increase: non-capital "
              "provincial plans adopted since 2000, region fixed effects, s.e. clustered by si/gun.\n\n"
            + md(["Term", "Coefficient (s.e.)"], rows_e)
            + "\n\nPanel F. Urban land growth 2009–19 (%) on the plan in force in 2009: non-capital provincial si/gun, region "
              "fixed effects, HC1 s.e.\n\n" + md(["Term", "(1) Overstatement", "(2) Reserve share"], rows_f)
            + "\n\nPlanned growth = 100 × [(P/R_y0)^(1/(T−y0)) − 1], prior trend = 100 × [(R_y0/R_y0−5)^(1/5) − 1], with P the planned "
              "population, T the target year and R registered population (equations 2–3). Overstatement = 100 × (P/R_y0 − 1). "
              "The constant of the plan-on-trend model is the planned growth at zero trend in the reference region; the "
              "prediction averages over the regions of the "
              + re.search(r"절편\(추세 0일 때 계획 성장\) [^,]*, n=(\d+)", read("plan_pop.txt")).group(1)
              + " plans. The 105 percent cap (Directives No. 900, 2017, and "
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
        out.append(f"Panel {chr(65 + len(out))}. {tn[tr]}.\n\n" + md(head, rows))
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
              "population. Source: `plan_event_coefs.csv`, `plan_event.txt`." + s9_robust())


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
        keep.append(f"Panel {chr(65 + len(keep))}. {title}.\n\n" + md(["Group"] + [colmap.get(h, h) for h in hdr]
                                                 + (["Outside res./com./ind. (%)"] if outside else []), rows))
    mm = z[z.index("모형 (비수도권"):]
    g1 = re.search(r"감소 \(성장 대비\): \+([\d.]+)(\**) \(se ([\d.]+)\)", mm)
    g2 = re.search(r"정체 \(성장 대비\): \+([\d.]+)(\**) \(se ([\d.]+)\)", mm)
    ln = re.search(r"log 신규 시가지: (-[\d.]+)(\**), n=(\d+), 성장 평균 ([\d.]+)%", mm)
    c1 = re.search(r"군 여부 통제: 감소 \+([\d.]+)(\**) \(se ([\d.]+)\); 가용지 도시지역 비율 1%p (-?\+?[\d.]+)(\**), 군 \+([\d.]+)(\**), n=(\d+)", mm)
    rs = re.search(r"10%p: \+([\d.]+)(\**) \(se ([\d.]+)\), n=(\d+)", mm)
    rb = re.search(r"95% CI 10%p (\[[-\d.]+, [-\d.]+\]); 사분위 범위 ([\d.]+)%p → (\[[-\d.]+, [-\d.]+\])%p", mm)
    reg = md(["Model", "Shrinking vs growing", "Stagnant vs growing", "Other terms", "N"], [
        ["Group + log new urban land + region", f"{g1.group(1)} ({g1.group(3)}){g1.group(2)}", f"{g2.group(1)} ({g2.group(3)}){g2.group(2)}",
         f"log new urban land {ln.group(1)}{ln.group(2)}; mean for growing si/gun {ln.group(4)}%", ln.group(3)],
        ["+ share of available land in urban areas, old-core zoning, county dummy", f"{c1.group(1)} ({c1.group(3)}){c1.group(2)}", "",
         f"available urban share, 1 pp {c1.group(4)}{c1.group(5)}; county {c1.group(6)}{c1.group(7)}", c1.group(8)],
        ["2009 reserve ÷ urbanised land, 10 pp (instead of group)", "", "", f"{rs.group(1)} ({rs.group(3)}){rs.group(2)}", rs.group(4)],
        ["Same model: 95% confidence interval per 10 pp; effect of an interquartile difference in the reserve share, 95% bounds (pp)",
         "", "", f"{rb.group(1)}; interquartile range {rb.group(2)} pp: {rb.group(3)}", rs.group(4)]])
    return ("**Table S10.** Where new urban land formed: 2026 zoning routes.\n\n" + "\n\n".join(keep)
            + f"\n\nPanel {chr(65 + len(keep))}. Off-plan share of new urban land (%, outside residential, commercial and industrial zones), non-capital "
              "provincial si/gun with at least 5 ha of new urban land, OLS with HC1 s.e.\n\n" + reg + "\n\nSource: `zoning_route.txt`."
            + s10_robust())


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
    sh = pd.read_csv(os.path.join(A, "newcity_share.csv"))
    rows_b = [[EN.get(r.group, r.group), f"{r.dh_out:,.0f}", f"{r.dh_out_newtown:,.0f}", f"{r.dh_pct:.1f}", f"{r.new_km2:.1f}",
               f"{r.new_newtown_km2:.1f}", f"{r.new_pct:.1f}"] for r in sh.itertuples()]
    return ("**Table S11.** Innovation and enterprise new towns excluded from the old core.\n\n"
            + "Panel A. Districts.\n\n"
            + md(["Zone", "Type", "District designated", "Notified area (km²)", "Area on the 100 m grid (km²)", "Ratio", "Boundary source"], rows)
            + f"\n\n{inn} sites of the 10 innovation cities and {ent} sites of the 4 enterprise cities; {len(mapped)} are mapped. "
              f"The {len(z) - len(mapped)} unmapped sites are small Busan sites inside existing urban areas "
              f"({' and '.join(f'{a:.2f}' for a in z[z.source == '없음'].area_gosi_km2)} km² notified) with no district boundary "
              "in V-World. Innovation cities are national projects designated under the Special Act on the Relocation of Public "
              "Institutions to house public agencies moved out of the capital region; enterprise cities are designated under the "
              "Special Act on Enterprise Cities for private-led development. Both were developed by acquiring and rebuilding the "
              "whole district after designation, so housing added inside them is new-town construction rather than change in the "
              "old core; they are therefore excluded from the old core. Other new towns, such as housing-site development "
              "districts, are not excluded. Source: `newcity_zones.csv`."
            + "\n\nPanel B. New development inside the districts, by group.\n\n"
            + md(["Group", "Dwellings added 2015–24 outside the old core", "Of which in the districts", "In the districts (%)",
                  "New urban land 2009–19 (km²)", "Of which in the districts (km²)", "In the districts, land (%)"], rows_b)
            + "\n\nPanel B: dwellings added on the 100-metre grid (increases only) outside the old core, and new urban land "
              "(urban share from below 10 to at least 50 percent), with the part inside the mapped districts. Most new "
              "development lies outside the districts. Source: `newcity_share.csv`.")


def s12():
    """Nationwide events in the study period: what the region x period (year) fixed effects absorb. Dates checked
    against the cited official sources on 2026-10-24; no estimates."""
    rows = [
        ["1 Jan 2003", "National Land Planning and Utilization Act (Act No. 6655) in force; land outside urban areas "
         "becomes management areas, to be subdivided into planned, production and conservation management",
         "Zoning outside urban areas, the main off-plan route", "Before all windows; zoning observed in 2026 (Table S10)",
         "National Law Information Center"],
        ["Oct 2008 – Feb 2009", "Global financial crisis; base rate cut from 5.25 to 2.00 percent",
         "Housing starts, sales and unsold new housing", "Housing period 2005–10; unsold series from 2007",
         "Bank of Korea, base-rate history"],
        ["2012 – Dec 2019", "153 public institutions move from the capital region, mostly to the 10 innovation cities "
         "(relocation plan 2005)", "Housing, population and jobs in the host si/gun only (not absorbed)",
         "Housing periods 2010–15, 2015–19; vacancy 2016–19; event-study years 2012–19; districts excluded from the old core (Table S11)",
         "MOLIT press release, 25 Dec 2019; MOLIT Innovation City Development Office"],
        ["1 Sep 2014", "Housing-market measures: repeal of the Housing Site Development Promotion Act announced; LH "
         "designation of large public housing sites halted until 2017", "Supply of large new housing estates",
         "Housing periods 2010–15, 2015–19; event-study years 2014–17", "MOLIT, measures of 1 Sep 2014"],
        ["1 Nov 2015", "Census becomes register-based (full-count items from administrative registers)",
         "Gridded population, households and dwellings; vacancy", "Break between 2010 and 2015 (Table S2); housing period 2010–15",
         "Statistics Korea"],
        ["2017, 2018", "Master-plan directives No. 900 and No. 1133 cap the target-year population at 105 percent of projections",
         "Planned population of later plans", "Plans adopted 2019–25 (Table S8, Panels B and D)", "MOLIT directives"],
        ["20 Jan 2020 –", "COVID-19 (first domestic case); base rate cut to 0.50 percent in May 2020",
         "Moves and housing demand", "Housing period 2019–24; vacancy and event-study years 2020–22",
         "KDCA; Bank of Korea, base-rate history"],
        ["Aug 2021 – Jan 2023", "Base rate raised from 0.50 to 3.50 percent", "Housing demand, sales and unsold new housing",
         "Housing period 2019–24; vacancy and event-study years 2021–25", "Bank of Korea, base-rate history"],
        ["18 Oct 2021", "89 si/gun/gu designated population-decline areas, with a dedicated local fund",
         "Funding for declining places", "Vacancy and event-study years 2022–25", "MOIS press release, 18 Oct 2021"]]
    return ("**Table S12.** Nationwide events during the study period.\n\n"
            + md(["Date", "Event", "What it changes", "Periods of the models in which it falls", "Source"], rows)
            + "\n\nThe housing panels (Tables 3, S5) include region × period fixed effects and the vacancy panel and event "
              "study (Tables 4, S6, S9) region × year fixed effects. These absorb any event common to the si/gun of one "
              "region in one period, so the events above enter the estimates only through differences between si/gun of the "
              "same region. The relocation of public institutions affected only the host si/gun and is therefore not absorbed.")


# Table S13: every regression of the paper with all its terms, from the replication export
# (replication/export_model_frames.py paper1 records each fitted model while the analysis scripts run).
REP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "replication", "data", "paper1")
TERM = {"Intercept": "Constant", "gp": "Population growth g (pp)", "neg": "N (negative growth)", "gp:neg": "g × N",
        "lpop10": "Log population 2010", "lpop00": "Log population 2000", "C(group == '수도권')[T.True]": "Capital region",
        "new_rate_pre": "New urban land rate 1999–2009 (%)", "leap_share_pre": "Leapfrog share 1999–2009 (%)",
        "new_rate_post": "New urban land rate 2009–19 (%)", "out_share_1524": "New dwellings outside the old core 2015–24 (%)",
        "g_pop_0010": "si/gun population change 2000–10 (%)", "g_pop_1524": "si/gun population change 2015–24 (%)",
        "s_house": "Housing growth (%/yr)", "g_hh_lag": "Prior-period household growth (%/yr)",
        "shrink_lag": "Prior-period population decline (0/1)", "g_hh": "Same-period household growth (%/yr)",
        "g_pop": "Same-period population growth (%/yr)", "sg_in": "Same-period gross in-migration",
        "sg_net": "Same-period net in-migration", "ic_0612": "Area designated 2006–12 (%)", "ic_0105": "Area designated 2001–05 (%)",
        "ic_1624": "Area designated 2016–24 (%)", "ic_pre": "Area designated before 2001 (%)",
        "km2_0612": "Area designated 2006–12 (km²)", "km2_0105": "Area designated 2001–05 (km²)",
        "pre_manuf": "Prior growth 2000–05 of the outcome", "pre_emp": "Prior growth 2000–05 of the outcome",
        "pre_pop": "Prior growth 2000–05 of the outcome", "pre_hh": "Prior growth 2000–05 of the outcome",
        "pre_house": "Prior growth 2000–05 of the outcome",
        "hd_0612": "District area started 2006–12 (%)", "hd_0105": "District area started 2001–05 (%)",
        "hd_1624": "District area started 2016–24 (%)", "hd_pre": "District area started before 2001 (%)",
        "u_0612": "Planned dwellings started 2006–12 (%)", "u_0105": "Planned dwellings started 2001–05 (%)",
        "u_1624": "Planned dwellings started 2016–24 (%)", "u_pre": "Planned dwellings started before 2001 (%)",
        "s": "Net additions per 1,000 dwellings", "d_hh": "Household change per 1,000 dwellings",
        "s_l1": "Net additions per 1,000 dwellings, t−1", "s_l2": "Net additions per 1,000 dwellings, t−2",
        "C(pre_group, Treatment('성장'))[T.감소]": "Shrinking 1992–2000 (vs growing)",
        "C(pre_group, Treatment('성장'))[T.정체]": "Stagnant 1992–2000 (vs growing)",
        "trend_g": "Prior 5-year trend (%/yr)", "excess_pct": "Planned increase (% of population at adoption)",
        "post": "Adopted 2019 or later", "plan_excess": "2009 overstatement (%)", "reserve_share": "2009 reserve ÷ urbanised land (%)",
        "g_reg": "Realised population change 2009–19 (%)", "C(group, Treatment('성장'))[T.감소]": "Shrinking (vs growing)",
        "C(group, Treatment('성장'))[T.정체]": "Stagnant (vs growing)", "lnew": "Log new urban land", "lsize": "Log size of the measure",
        "s:g5": "Net additions × prior 5-year population change (%/yr)", "s:dec5": "Net additions × prior 5-year decline (0/1)",
        "avail_urb": "Share of available land in urban areas (%)", "old_inA": "Old core in residential, commercial and industrial zones (%)",
        "gun": "County (0/1)", "reserve_share09": "2009 reserve ÷ urbanised land (%)",
        "Em4": "k ≤ -4", "Em3": "k = -3", "Em2": "k = -2", "E0": "k = 0", "E1": "k = +1", "E2": "k = +2", "E3": "k = +3",
        "E4": "k = +4", "E5": "k = +5", "E6": "k ≥ +6"}
S3C_Y = ["New urban land rate 1999–2009 (%)", "Leapfrog share 1999–2009 (%)", "New urban land rate 2009–19 (%)",
         "New dwellings outside the old core 2015–24 (%)"]
S3C_S = ["Non-capital provincial", "Shrinking", "Stagnant and growing", "Metropolitan and capital region"]
S9_P = ["S9-A", "S9-B", "S9-C", "S9-D", "S9-E"]
S9_Y = ["Urban-use zoning", "Residential zoning", "Land-form-change permits"]
S9_S = ["All", "Shrinking", "Stagnant and growing"]
VAC_S = ["Non-capital provincial", "Shrinking", "Stagnant", "Growing", "Metropolitan and capital region"]
VAC_Y = ["All vacancies", "Pre-2000 dwellings", "Built in last 5 years"]
IC_YS = ["Manufacturing employment", "All employment", "Population", "Households"]
HD_YS = ["Households", "Population", "Dwellings"]


def s13_where(mid):
    """(source table-panel, outcome, sample or variant) of each exported model; '' source = not tabulated."""
    sc, k = mid.rsplit("_", 1)
    k = int(k)
    if sc == "shrink_sprawl":
        s4 = {1: ("New urban land rate (%)", "1999–2009"), 2: ("Leapfrog share (%)", "1999–2009"),
              3: ("Δ log urban land per resident ×100", "1999–2009"), 22: ("New urban land rate (%)", "2009–2019"),
              23: ("Δ log urban land per resident ×100", "2009–2019"), 24: ("Leapfrog share (%)", "2009–2019")}
        if k in s4:
            return ("S4",) + s4[k]
        if k in (4, 5):
            return ("", ("New urban land rate (%)", "Leapfrog share (%)")[k - 4], "2009–2019, census population")
        j = k - 6
        return "S3-C", "Old-core population change (%)", f"{S3C_Y[j // 4]}; {S3C_S[j % 4]}"
    if sc == "supply_demand":
        tab = {1: ("S5-B", "Housing growth (%/yr)", "(1) Prior demand only"),
               2: ("S5-B", "Housing growth (%/yr)", "(2) + prior decline"),
               3: ("S5-B", "Housing growth (%/yr)", "(3) + same-period households"),
               4: ("S5-C", "Household growth", "All periods"), 5: ("S5-C", "Population growth", "All periods"),
               6: ("S5-C", "Household growth", "Excl. 2010–15"), 7: ("S5-C", "Population growth", "Excl. 2010–15"),
               8: ("S5-C", "Household growth", "Shrinking"), 9: ("S5-C", "Household growth", "Stagnant"),
               10: ("S5-C", "Household growth", "Growing"),
               11: ("S5-D", "Next-period household growth", "Without si/gun FE"),
               12: ("S5-D", "Next-period household growth", "With si/gun FE"),
               13: ("S5-D", "Next-period population growth", "Without si/gun FE"),
               14: ("S5-D", "Next-period population growth", "With si/gun FE"),
               15: ("S5-D", "Next-period housing growth", "Without si/gun FE"),
               16: ("S5-D", "Next-period housing growth", "With si/gun FE"),
               17: ("S5-E", "Gross in-migration", "Same period"), 18: ("S5-E", "Net in-migration", "Same period"),
               19: ("S5-E", "Gross in-migration", "Next period"), 20: ("S5-E", "Net in-migration", "Next period")}
        if k > 20:   # robustness of the lead and reverse models (block "lead_robust")
            y, j = divmod(k - 21, 4)
            return ("S5-F", ["Next-period household growth", "Next-period population growth", "Next-period housing growth"][y],
                    ["Unit FE, no lagged outcome", "Same census method, no unit FE", "Shrinking, unit FE",
                     "Shrinking, no unit FE"][j])
        return tab[k]
    if sc == "ic_unmet":
        if k <= 12:
            v, j = divmod(k - 1, 3)
            return "S7-C", IC_YS[v], ["Growth 2010–24", "Placebo: growth 2010–24", "Placebo: growth 2005–15"][j]
        if k <= 15:
            return "S7-D", "Area designated 2006–12 (%)", ["Manufacturing employment", "Population", "Households"][k - 13]
        return "", "Manufacturing employment change 2010–24", "Designated area in km²"
    if sc == "hd_unmet":
        x, r = divmod(k - 1, 12)
        xl = ["district area", "planned dwellings"][x]
        if r < 9:
            v, j = divmod(r, 3)
            return "S7-H", HD_YS[v], ["Growth 2010–24", "Placebo: growth 2010–24", "Placebo: growth 2005–15"][j] + f", {xl}"
        return "S7-H", f"Start 2006–12, {xl} (%)", HD_YS[r - 9]
    if sc == "robust_review":
        if k <= 2:
            return "S10-I", "Off-plan share of new urban land (%)", ["Main groups", "Groups from 1992–2000"][k - 1]
        g = ["Main groups; Shrinking", "Main groups; Stagnant", "Main groups; Growing",
             "Groups from 1992–2000; Shrinking", "Groups from 1992–2000; Growing"]   # stagnant 1992-2000: too few units
        if k <= 7:
            return "S6-G", "Pre-2000 dwellings", g[k - 3]
        if k <= 11:
            return "S6-F", "Pre-2000 dwellings, with lags", ["Shrinking", "Stagnant", "Growing", "Non-capital provincial"][k - 8]
        if k <= 14:
            return "S6-F", "Pre-2000 dwellings, household control", ["Shrinking", "Stagnant", "Growing"][k - 12]
        smp4 = ["Shrinking", "Stagnant", "Growing", "Non-capital provincial"]
        if k <= 22:   # lag models for recently built and all vacancies (added 2026-11-22)
            y, j = divmod(k - 15, 4)
            return "S6-F", ["Built in last 5 years, with lags", "All vacancies, with lags"][y], smp4[j]
        if k <= 26:   # decline as it happens
            s, x = divmod(k - 23, 2)
            return ("S6-H", "Pre-2000 dwellings",
                    f"{['Non-capital provincial', 'All si/gun'][s]}; {['× prior population change', '× prior decline'][x]}")
        m, s = divmod(k - 27, 2)   # off-plan models on residential land and dwellings
        return ("S10-J", ["Off-plan share of residential new urban land (%)", "Off-plan share of dwellings, cells >= 5 (%)",
                          "Off-plan share of dwellings, net change (%)"][m], ["Region FE and log size", "+ controls"][s])
    if sc == "vacancy":
        if k == 16:
            return "S6-B", "Pre-2000 dwellings", "Non-capital provincial, 2020–24"
        if k > 16:   # no exclusion of unit-years
            return "S6-I", "Pre-2000 dwellings", ["Shrinking", "Stagnant", "Growing", "Metropolitan and capital region"][k - 17]
        s, y = divmod(k - 1, 3)
        return "S6-A", VAC_Y[y], VAC_S[s]
    if sc == "plan_pop":
        return {1: ("S8-C", "Planned growth (%/yr)", "Adopted since 2000"), 2: ("S8-E", "Reserve share (%)", "Adopted since 2000"),
                3: ("S8-F", "Urban land growth 2009–19 (%)", "(1) Overstatement"),
                4: ("S8-F", "Urban land growth 2009–19 (%)", "(2) Reserve share"),
                5: ("S8-D", "Planned growth (%/yr)", "Adopted 2005–2025")}[k]
    if sc == "plan_event":
        if k > 45:   # robustness: units with a plan vintage only
            ev = ["Any new plan", "New plan enlarging the reserve"][(k - 46) // 4]
            out = ["Urban-use zoning", "Land-form-change permits"][((k - 46) % 4) // 2]
            smp = ["All si/gun", "si/gun that adopted a plan"][(k - 46) % 2]
            return "S9-F", out, f"{ev}; {smp}"
        e, r = divmod(k - 1, 9)
        y, s = divmod(r, 3)
        return S9_P[e], S9_Y[y], S9_S[s]
    if sc == "zoning_route":
        return "S10-F", "Off-plan share of new urban land (%)", ["Group", "Group and controls", "2009 reserve share"][k - 1]
    raise KeyError(mid)


def s13_fe(formula):
    fe = []
    for pat, lab in [(r"C\(SG_ID\)|C\(sigun\)", "si/gun"), (r"C\(rp\)", "region × period"), (r"C\(ry\)", "region × year"),
                     (r"C\(region\)", "region")]:
        if re.search(pat, formula):
            fe.append(lab)
    return ", ".join(fe) if fe else "none"


def s13():
    mo = pd.read_csv(os.path.join(REP, "models.csv"))
    es = pd.read_csv(os.path.join(REP, "python_estimates.csv"))
    order = ["S3-C", "S4", "S5-B", "S5-C", "S5-D", "S5-E", "S5-F", "S6-A", "S6-B", "S6-F", "S6-G", "S6-H", "S6-I", "S7-C", "S7-D", "S7-H", "S8-C", "S8-D", "S8-E", "S8-F",
             "S9-A", "S9-B", "S9-C", "S9-D", "S9-E", "S9-F", "S10-F", "S10-I", "S10-J", ""]
    mo["where"] = [s13_where(i) for i in mo.id]
    mo["rank"] = [order.index(w[0]) for w in mo["where"]]
    mo = mo.sort_values(["rank", "id"], kind="stable")
    panels, rows = [], []
    for (src, part) in [(("S3-C", "S4"), "A. Sprawl and the old core (Tables S3, Panel C, and S4)"),
                        (("S5-B", "S5-C", "S5-D", "S5-E", "S5-F"), "B. Housing supply, households and in-migration (Table S5)"),
                        (("S6-A", "S6-B", "S6-F", "S6-G", "S6-H", "S6-I"), "C. Vacancy panel (Table S6)"),
                        (("S7-C", "S7-D", "S7-H"), "D. Industrial complexes and housing-site districts (Table S7)"),
                        (("S8-C", "S8-D", "S8-E", "S8-F"), "E. Master plans (Table S8)"),
                        (("S9-A", "S9-B", "S9-C", "S9-D", "S9-E", "S9-F"), "F. Event study of plan adoptions (Table S9)"),
                        (("S10-F", "S10-I", "S10-J"), "G. Off-plan shares (Table S10, Panels F, I and J)"),
                        (("",), "H. Models estimated by the analysis scripts but not tabulated")]:
        rows = []
        for _, m in mo[mo["where"].map(lambda w: w[0] in src)].iterrows():
            w = m["where"]
            se = "HC1" if m.cov_type == "HC1" else f"clustered by si/gun ({int(m.n_clusters)})"
            first = True
            for _, t in es[es.id == m.id].iterrows():
                if t.term == "Intercept" and s13_fe(m.formula) not in ("none", "region"):
                    continue                                    # absorbed by the fixed effects
                head = [w[0] or "–", w[1], w[2]] if first else ["", "", ""]
                tail = [f"{int(m.nobs)}", f"{m.r2:.3f}", s13_fe(m.formula), se] if first else ["", "", "", ""]
                rows.append(head + [TERM[t.term], cs(t.coef, t.se, t.p)] + tail)
                first = False
        panels.append(f"Panel {part}.\n\n" + md(["Table", "Outcome", "Sample or column", "Term", "Coefficient (s.e.)", "N",
                                                  "R²", "Fixed effects", "Standard errors"], rows))
    nm, nt = len(mo), int(es.id.isin(mo.id).sum())
    return ("**Table S13.** Full estimates of all regressions: every term except fixed-effect dummies.\n\n"
            + "\n\n".join(panels)
            + f"\n\n{nm} models. Each block of rows is one model; its first row gives the table and panel where the model's main "
              "terms are reported, N, R², the fixed effects and the standard errors (number of clusters). Coefficients to three "
              "decimals; * p<0.1, ** p<0.05, *** p<0.01. Constants are omitted where si/gun or region × period (year) fixed "
              "effects absorb them. Source: `replication/data/paper1/models.csv`, `python_estimates.csv` (written by "
              "`replication/export_model_frames.py`, which runs the analysis scripts and records each fitted model).")


def main():
    os.makedirs(OUT, exist_ok=True)
    t = "\n\n".join([s2(), s3(), s4(), s5(), s6(), s7(), s8(), s9(), s10(), s11(), s12(), s13()]) + "\n"
    with open(os.path.join(OUT, "supplement_tables.md"), "w", encoding="utf-8") as f:
        f.write(t)
    print(t[:6000])
    print(f"... {len(t):,} characters")


if __name__ == "__main__":
    main()
