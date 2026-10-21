"""Tables 1-4 of paper 1, built directly from the output files (no typed-in numbers).

  Table 1  shrinkage-sprawl indicators by group          shrink_sprawl.txt (blocks 1 and 4)
  Table 2  supply-led growth tests                        supply_demand.txt (blocks 2-3), ic_unmet.txt (block 2)
  Table 3  vacancy panel by group                         vacancy.txt (block 2)
  Table 4  plans: premise, attainment, reserves, routes   plan_pop.txt (blocks 2, 4), zoning_route.txt

Output: outputs/paper1/tables.md
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\paper1_tables.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

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


def table1():
    s = read("shrink_sprawl.txt")
    n = dict(zip(G, grab(s, r"시군 집단: 감소 (\d+), 정체 (\d+), 성장 (\d+), 광역시 (\d+), 수도권 (\d+)", 5)))
    pop = dict(zip(G, grab(s, r"/ 2009-19 감소 (-?[\d.]+), 정체 (-?[\d.]+), 성장 (-?[\d.]+), 광역시 (-?[\d.]+), 수도권 (-?[\d.]+)", 5)))
    urb = re.findall(r"([\d.]+) \(", grab(s, r"(시가지 증가 %[^\n]+)"))
    pc = dict(zip(G, grab(s, r"/ 2009-2019 감소 ([\d.]+), 정체 ([\d.]+), 성장 ([\d.]+), 광역시 ([\d.]+), 수도권 ([\d.]+)", 5)))
    dens = {g: grab(s, rf"{g} ([\d,]+ -> [\d,]+ -> [\d,]+)") for g in G}
    both = {g: grab(s, rf"\n{g}\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)\n") for g in G}
    pop = {g: ("0.0" if v == "-0.0" else v) for g, v in pop.items()}   # rounding artefact
    rows = [[EN[g], n[g], pop[g], urb[i], pc[g], dens[g].replace(" -> ", " → "), both[g]] for i, g in enumerate(G)]
    return ("**Table 1.** Shrinkage sprawl by group, si/gun medians unless noted.\n\n" + md(
        ["Group", "si/gun", "Registered pop. change 2009–19 (%)", "Urban land change 2009–19 (%)",
         "Δ log urban land per resident ×100, 2009–19", "Residents per urban km², 2000/1999 → 2009 → 2019 (group total)",
         "Expansion + core decline + pop. decline, 2009–24 (% of si/gun)"], rows)
        + "\n\nSources: land cover (large class), SGIS 100 m grid, registered population (KOSIS DT_1B040A3).")


def table2():
    s, c = read("supply_demand.txt"), read("ic_unmet.txt")
    rows = []
    for lab, rx in [("Next-period household growth on housing growth", r"g_hh_lead\s+~ s_house: 시군 FE 없음 [^,]+, 시군 FE (-?[\d.]+ \([\d.]+\)\**)"),
                    ("Next-period population growth on housing growth", r"g_pop_lead\s+~ s_house: 시군 FE 없음 [^,]+, 시군 FE (-?[\d.]+ \([\d.]+\)\**)"),
                    ("Next-period housing growth on household growth", r"s_house_lead\s+~ g_hh: 시군 FE 없음 [^,]+, 시군 FE (\+?[\d.]+ \([\d.]+\)\**)"),
                    ("Net in-migration from outside, same period", r"sg_net\s+~ s_house (\+?-?[\d.]+ \([\d.]+\)\**)"),
                    ("Net in-migration from outside, next period", r"sg_net_lead\s+~ s_house (-?[\d.]+ \([\d.]+\)\**)")]:
        rows.append([lab, grab(s, rx).replace("+", "")])
    for lab, rx in [("Manufacturing employment growth 2010–24 on 2006–12 designation", r"제조업 종사자  2006-12 지정 \+([\d.]+ \([\d.]+\)\**)"),
                    ("Placebo: 2005–15 growth on 2016–24 designation", r"제조업 종사자[^\n]*2005-15 성장 \+([\d.]+ \([\d.]+\)\**)"),
                    ("Designation 2006–12 on 2000–05 manufacturing growth", r"pre_manuf \+([\d.]+ \([\d.]+\)\**)")]:
        rows.append([lab, grab(c, rx)])
    return ("**Table 2.** Does supply lead growth? Non-capital provincial si/gun.\n\n" + md(["Test", "Coefficient (s.e.)"], rows)
            + "\n\nHousing: si/gun × five-year panel, si/gun and region × period fixed effects, clustered s.e. "
              "In-migration per thousand residents per percentage point of housing growth. Industrial complexes: "
              "cross-section of 122 si/gun, designated area as % of 2009 urban land, log growth ×100, HC1 s.e. "
              "* p<0.1, ** p<0.05, *** p<0.01.")


def table3():
    s = read("vacancy.txt")
    rows = []
    for g, lab in [("감소", "Shrinking"), ("정체", "Stagnant"), ("성장", "Growing"), ("광역시·수도권", "Metropolitan and capital region")]:
        m = grab(s, rf"\n   {g}\s+\(시군 (\d+)\): d_vac (\+[\d.]+ \([\d.]+\)\**), d_vac_old (\+[\d.]+ \([\d.]+\)\**), d_vac_new5 (\+[\d.]+ \([\d.]+\)\**)", 4)
        rows.append([lab, m[0]] + [x.replace("+", "") for x in m[1:]])
    rate = {g: grab(s, rf"\n{g}\s+(?:[\d.]+\s+){{2}}([\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+)\n") for g in ["감소", "수도권"]}
    return ("**Table 3.** Vacancies created per dwelling added, annual panel 2016–2025.\n\n"
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
    return ("**Table 4.** Growth-premised plans and where expansion went.\n\n" + md(
        ["Group", "Plan vintages", "Planned growth (%/yr)", "Prior 5-yr trend (%/yr)", "Realised growth (%/yr)",
         "Attainment (actual ÷ planned)", "Reserve per planned added resident (m²)", "New urban land 2009–19 outside res./com./ind. zones (%)"], rows)
        + "\n\nPlan vintages adopted since 2000, medians. Attainment for plans whose target year has passed. "
          "Sources: MOLIT urban-planning statistics (KOSIS TX_315_2009_H1004, H1004A), registered population, "
          "V-World zoning (2026), land cover.")


def main():
    os.makedirs(OUT, exist_ok=True)
    t = "\n\n".join([table1(), table2(), table3(), table4()]) + "\n"
    with open(os.path.join(OUT, "tables.md"), "w", encoding="utf-8") as f:
        f.write(t)
    print(t)


if __name__ == "__main__":
    main()
