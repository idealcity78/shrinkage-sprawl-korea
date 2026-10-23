"""Tables 1-5 of paper 1, built directly from the output files (no typed-in numbers).

  Table 1  propositions, tests and where the evidence is  (text only)
  Table 2  shrinkage-sprawl indicators by group          shrink_sprawl.txt (blocks 1 and 4)
  Table 3  supply-led growth tests, one panel per model   supply_demand_models.csv, ic_unmet_models.csv
  Table 4  vacancy panel by group                         vacancy.txt (block 2)
  Table 5  plans: premise, attainment, reserves, routes   plan_pop.txt (blocks 2, 4), zoning_route.txt

Output: outputs/paper1/tables.md
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\paper1_tables.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
import pandas as pd
from paper1_supplement_tables import supply_panels, ic_panels, IC_Y

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.join(paths.OUTPUTS, "partA")
OUT = os.path.join(paths.OUTPUTS, "paper1")
G = ["감소", "정체", "성장", "광역시", "수도권"]
EN = {"감소": "Shrinking", "정체": "Stagnant", "성장": "Growing", "광역시": "Metropolitan", "수도권": "Capital region"}


def read(f):
    return open(os.path.join(A, f), encoding="utf-8").read()


def grab(text, rx, n=1):
    m = re.search(rx, text, re.S)
    if not m:
        raise ValueError(f"not found: {rx}")
    return m.groups() if n > 1 else m.group(1)


def md(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def table_props():
    rows = [["Background: shrinkage sprawl", "Urban land grows without population growth", "Group indicators; equation (5)",
             "Table 2, Figure 2; S3, S4"],
            ["P1 No supply-led growth", "Supply and industrial designation do not raise later growth",
             "Lead and reverse regressions (6–7); designation placebo", "Table 3; S5, S7"],
            ["P2 Locational oversupply", "Supply within household growth, but new dwellings empty older stock",
             "Supply against household growth; vacancy panel (8)", "Table 4; S5 Panel A, S6"],
            ["P3 Universal growth premise", "Planned growth weakly related to the prior trend",
             "Plan on trend (2–3); adoption eras and the cap", "Table 5, Figure 3; S8 Panels A–D"],
            ["P4 Non-binding capacity", "Overstatement and revisions do not predict zoning or development",
             "2009 cross-section; event study (9)", "Figure 4; S8 Panels E–F, S9"],
            ["P5 Off-plan expansion", "Expansion bypasses the planned route; reserves stay unused",
             "Zoning routes; off-plan regression", "Table 5, Figure 5; S10"]]
    return ("**Table 1.** Propositions, tests and evidence.\n\n"
            + md(["Proposition", "Prediction (fails if not observed)", "Test (equation)", "Evidence"], rows)
            + "\n\nS = Supplementary Table. Equations refer to Section 4.")


def table1():
    s = read("shrink_sprawl.txt")
    n = dict(zip(G, grab(s, r"시군 집단: 감소 (\d+), 정체 (\d+), 성장 (\d+), 광역시 (\d+), 수도권 (\d+)", 5)))
    pop = dict(zip(G, grab(s, r"/ 2009-19 감소 (-?[\d.]+), 정체 (-?[\d.]+), 성장 (-?[\d.]+), 광역시 (-?[\d.]+), 수도권 (-?[\d.]+)", 5)))
    urb = re.findall(r"([\d.]+) \(", grab(s, r"(시가지 증가 %[^\n]+)"))
    pc0 = dict(zip(G, grab(s, r"x100 중앙값: 1999-2009 감소 (-?[\d.]+), 정체 (-?[\d.]+), 성장 (-?[\d.]+), 광역시 (-?[\d.]+), 수도권 (-?[\d.]+)", 5)))
    pc = dict(zip(G, grab(s, r"/ 2009-2019 감소 ([\d.]+), 정체 ([\d.]+), 성장 ([\d.]+), 광역시 ([\d.]+), 수도권 ([\d.]+)", 5)))
    dens = {g: grab(s, rf"{g} ([\d,]+ -> [\d,]+ -> [\d,]+)") for g in G}
    both = {g: grab(s, rf"\n{g}\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)\n") for g in G}
    pop = {g: ("0.0" if v == "-0.0" else v) for g, v in pop.items()}   # rounding artefact
    rows = [[EN[g], n[g], pop[g], urb[i], pc0[g], pc[g], dens[g].replace(" -> ", " → "), both[g]] for i, g in enumerate(G)]
    return ("**Table 2.** Shrinkage sprawl by group, si/gun medians unless noted.\n\n" + md(
        ["Group", "si/gun", "Registered pop. change 2009–19 (%)", "Urban land change 2009–19 (%)",
         "Δ log urban land per resident ×100, 1999–2009", "Δ log urban land per resident ×100, 2009–19", "Residents per urban km², 2000/1999 → 2009 → 2019 (group total)",
         "Expansion + core decline + pop. decline, 2009–24 (% of si/gun)"], rows)
        + "\n\nSources: land cover (large class), SGIS 100 m grid, registered population (KOSIS DT_1B040A3).")


def table2():
    m = pd.read_csv(os.path.join(A, "supply_demand_models.csv"))
    pl, pm = supply_panels(m)
    ys = ("manuf", "emp")
    rows, rev = ic_panels(pd.read_csv(os.path.join(A, "ic_unmet_models.csv")), ys=ys, full=False)
    rev = [[r if r else "not estimated" for r in rev[0]]]
    return ("**Table 3.** Does supply lead growth? Non-capital provincial si/gun.\n\n"
            + "Panel A. Lead and reverse regressions (equations 6–7), five-year periods.\n\n" + pl
            + "\n\nPanel B. In-migration from outside the si/gun on housing growth.\n\n" + pm
            + "\n\nPanel C. Industrial-complex designation and growth, cross-section of 122 si/gun (outcome log growth ×100; "
              "designated area as % of 2009 urban land).\n\n" + md(["Model", "Regressor"] + [IC_Y[y] for y in ys], rows + rev)
            + "\n\nPanels A–B: si/gun × five-year periods, region × period fixed effects (with si/gun fixed effects where "
              "stated, and in Panel B), s.e. clustered by si/gun; next-period models control for the current value of the "
              "outcome. Panel C: OLS, HC1 s.e., controls as in Supplementary Table S7. Full models: Supplementary Tables S5 "
              "(Panels D–E) and S7 (Panels C–D). * p<0.1, ** p<0.05, *** p<0.01.")


def table3():
    s = read("vacancy.txt")
    rows = []
    for g, lab in [("감소", "Shrinking"), ("정체", "Stagnant"), ("성장", "Growing"), ("광역시·수도권", "Metropolitan and capital region")]:
        m = grab(s, rf"\n   {g}\s+\(시군 (\d+)\): d_vac (\+[\d.]+ \([\d.]+\)\**), d_vac_old (\+[\d.]+ \([\d.]+\)\**), d_vac_new5 (\+[\d.]+ \([\d.]+\)\**)", 4)
        rows.append([lab, m[0]] + [x.replace("+", "") for x in m[1:]])
    rate = {g: grab(s, rf"\n{g}\s+(?:[\d.]+\s+){{2}}([\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+)\n") for g in ["감소", "수도권"]}
    return ("**Table 4.** Vacancies created per dwelling added, annual panel 2016–2025.\n\n"
            + md(["Group", "si/gun", "All vacancies", "Pre-2000 dwellings", "Dwellings built in last 5 years"], rows)
            + "\n\nDependent variable: change in vacant dwellings per 1,000 dwellings; regressor: net additions per 1,000 "
              "dwellings; si/gun and region × year fixed effects, clustered s.e. Vacancy rates 2015/2019/2024/2025 (%): "
              f"shrinking {rate['감소'].split()[0]}/{rate['감소'].split()[1]}/{rate['감소'].split()[2]}/{rate['감소'].split()[3]}, "
              f"capital region {rate['수도권'].split()[0]}/{rate['수도권'].split()[1]}/{rate['수도권'].split()[2]}/{rate['수도권'].split()[3]}. "
              "Sources: register-based census vacancy by construction year (KOSIS DT_1JU1512).")


def table4():
    p, z = read("plan_pop.txt"), read("zoning_route.txt")
    z = grab(z, r"(신규 시가지 2009→19: 용도지역별 비중\(%\)\n.*?)\n\n")     # first table only
    rows = []
    for g in G:
        n, pg, tr, ac, _, at = grab(p, rf"\n{g}\s+(\d+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+([\d.]+)\n", 6)
        m2 = grab(p, rf"\n{g}\s+[\d.]+\s+[\d.]+\s+([\d.]+)\n")
        a = float(grab(z, rf"\n{g}\s+([\d.]+)"))
        rows.append([EN[g], n, pg, tr, ac, at, m2, f"{100 - a:.1f}"])
    return ("**Table 5.** Growth-premised plans and where expansion went.\n\n" + md(
        ["Group", "Plan vintages", "Planned growth (%/yr)", "Prior 5-yr trend (%/yr)", "Realised growth (%/yr)",
         "Attainment (actual ÷ planned)", "Reserve per planned added resident (m²)", "New urban land 2009–19 outside res./com./ind. zones (%)"], rows)
        + "\n\nPlan vintages adopted since 2000, medians. Attainment for plans whose target year has passed. "
          "Sources: MOLIT urban-planning statistics (KOSIS TX_315_2009_H1004, H1004A), registered population, "
          "V-World zoning (2026), land cover.")


def main():
    os.makedirs(OUT, exist_ok=True)
    t = "\n\n".join([table_props(), table1(), table2(), table3(), table4()]) + "\n"
    with open(os.path.join(OUT, "tables.md"), "w", encoding="utf-8") as f:
        f.write(t)
    print(t)


if __name__ == "__main__":
    main()
