"""Manuscript tables for paper 2, written straight from the output files (no hand-typed numbers).

Tables (Markdown) -> outputs/paper2/tables.md
  Table 1  data construction and validation   flows/mdis_check.csv, data_work/logs/build_mdis_db.txt, paper2/xwalk_stats.txt
  Table 2  old-core out-moves and net migration by destination        flows/mdis_old_core.txt
  Table 3  age paths and age-specific net migration                    partB/flows_age.txt
  Table 4  supply-location panel with same-동 bounds                   partB/same_dong_bound_vital.txt
  Table 5  new-town move-in, pooled effects and permutation p          partB/zone_event_pooled.csv, partB/flows_age.txt,
                                                                       partB/emp_supply.txt
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\paper2_tables.py
"""
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
O = paths.OUTPUTS
OUT = os.path.join(O, "paper2", "tables.md")
PER = ["2001-2005", "2006-2010", "2011-2015", "2016-2020", "2021-2025"]
PLAB = ["2001–05", "2006–10", "2011–15", "2016–20", "2021–25"]


def lines(rel):
    with open(os.path.join(O, rel), encoding="utf-8") as f:
        return f.read().splitlines()


def block(rel, header, labels):
    """rows (token lists) for `labels` in the first block after a line containing `header`."""
    L = lines(rel)
    i = next(k for k, l in enumerate(L) if header in l)
    out = {}
    for l in L[i + 1:]:
        t = l.split()
        if t and t[0] in labels and t[0] not in out:
            out[t[0]] = t
        if len(out) == len(labels):
            break
    return out


def md(df):
    cols = list(df.columns)
    s = "| " + " | ".join(cols) + " |\n|" + "|".join("---" for _ in cols) + "|\n"
    for _, r in df.iterrows():
        s += "| " + " | ".join(str(r[c]) for c in cols) + " |\n"
    return s


def minus(x):
    return str(x).replace("-", "−")


def t1():
    chk = pd.read_csv(os.path.join(O, "flows", "mdis_check.csv"))
    log = open(os.path.join(paths.WORK, "logs", "build_mdis_db.txt"), encoding="utf-8").read()
    rec = {int(y): (int(r.replace(",", "")), float(s)) for y, r, s in
           re.findall(r"(\d{4}): records ([\d,]+) .*?same-dong ([\d.]+)", log)}
    rows = []
    for _, r in chk.iterrows():
        y = int(r.year)
        rows.append({"Year": y, "Registrations": f"{rec[y][0]:,}",
                     "Movers between neighbourhoods": f"{int(r.mdis_pers):,}",
                     "Published (KOSIS)": f"{int(r.kosis_pers):,}", "Difference": int(r.diff_total),
                     "Province pairs differing": f"{int(r.pairs_off)} of {int(r.pairs)}",
                     "Within-neighbourhood share (%)": "–" if y < 2005 else f"{rec[y][1] * 100:.1f}"})
    s = md(pd.DataFrame(rows))
    xs = os.path.join(O, "paper2", "xwalk_stats.txt")
    if os.path.exists(xs):
        x = open(xs, encoding="utf-8").read()
        codes = re.search(r"코드 수 \(2001-2025\): ([\d,]+)", x).group(1)
        cy = re.search(r"코드-연도 ([\d,]+)개", x).group(1)
        rsum = re.search(r"합계 ([\d,]+)", x).group(1)
        o = re.search(r"out_cd: 동 간 이동자 ([\d,]+), 경계에 연결 ([\d,]+) \(([\d.]+)%\)", x)
        i = re.search(r"in_cd: 동 간 이동자 ([\d,]+), 경계에 연결 ([\d,]+) \(([\d.]+)%\)", x)
        s += (f"\nRegistrations 2001–2025: {rsum}. Neighbourhood codes used: {codes} ({cy} code-years). Movers between "
              f"neighbourhoods 2001–2025 (all Korea): {o.group(1)}; linked to a boundary at origin {o.group(3)}%, at "
              f"destination {i.group(3)}% (`outputs/paper2/xwalk_stats.txt`).\n")
    return s


def t2():
    rel = "flows/mdis_old_core.txt"
    sh = block(rel, "같은 비율", PER)
    nt = block(rel, "원도심 순이동 (전입", PER)
    op = block(rel, "old_core_pop  net_per_1000", PER)
    rows = []
    for p, lab in zip(PER, PLAB):
        s = dict(zip(["zone", "new", "rest", "same_do", "metro", "capital", "elsewhere", "unknown"], sh[p][1:]))
        n = dict(zip(["zone", "new", "rest", "same_do", "metro", "capital", "elsewhere", "unknown", "total"], nt[p][1:]))
        rows.append({"Period": lab, "New land (%)": s["new"], "New towns (%)": s["zone"], "Rest of city (%)": s["rest"],
                     "Same province (%)": s["same_do"], "Adjacent metro (%)": s["metro"], "Capital region (%)": s["capital"],
                     "Elsewhere (%)": s["elsewhere"],
                     "Net to new land": minus(f"{float(n['new']):,.0f}"), "Net to capital": minus(f"{float(n['capital']):,.0f}"),
                     "Net to new towns": minus(f"{float(n['zone']):,.0f}"), "Net, all": minus(f"{float(n['total']):,.0f}"),
                     "Net per 1,000": minus(op[p][2]), "Out per 1,000": op[p][3]})
    return md(pd.DataFrame(rows))


def t3():
    rel = "partB/flows_age.txt"
    L = lines(rel)
    i_new = next(k for k, l in enumerate(L) if l.strip() == "신규개발지+혁신·기업도시")
    i_cap = next(k for k, l in enumerate(L) if l.strip() == "수도권")
    i_net = next(k for k, l in enumerate(L) if l.startswith("원도심 순이동 연령별"))

    def rows_after(i):
        out = {}
        for l in L[i + 1:]:
            t = l.split()
            if t and t[0] in PER:
                out[t[0]] = t[1:]
            if len(out) == 5:
                return out
    a, b, c = rows_after(i_new), rows_after(i_cap), rows_after(i_net)
    ages = ["0–14", "15–24", "25–39", "40–64", "65+"]
    rows = []
    for p, lab in zip(PER, PLAB):
        r = {"Period": lab}
        r.update({f"{g} to new land/towns (%)": v for g, v in zip(ages, a[p])})
        r.update({f"{g} to capital (%)": v for g, v in zip(ages, b[p])})
        rows.append(r)
    s = md(pd.DataFrame(rows))
    net = pd.DataFrame([{"Period": lab, **{g: minus(v) for g, v in zip(ages, c[p])}} for p, lab in zip(PER, PLAB)])
    return s + "\nNet migration by age, per 1,000 old-core residents a year (sum over ages = total):\n\n" + md(net)


def t4():
    rel = "partB/same_dong_bound_vital.txt"
    L = lines(rel)
    pp = ["2000-2005", "2005-2010", "2015-2019", "2019-2024"]
    ni = block(rel, "기대 자연증가 (연", pp)
    ub = block(rel, "상한 (원도심 인구 천 명당 연)", pp)
    a = pd.DataFrame([{"Period": p.replace("-", "–"), "Natural increase, old core": minus(ni[p][1]), "Natural increase, new land": minus(ni[p][2]),
                       "Bound H (zero natural increase)": ub[p][1], "Bound H (old-core dong only)": ub[p][2],
                       "Bound H (expected natural increase)": ub[p][3], "Bound H (both)": ub[p][4],
                       "Observed old core → new land": ub[p][5]} for p in pp])
    s = "Panel A. Hidden-move bound, per 1,000 old-core residents a year\n\n" + md(a)
    labs = [("net_old 관측", "Observed"), ("net_old - H_ub (기존)", "− H (zero natural increase)"),
            ("net_old - H_ub2 (기존)", "− H (old-core dong only)"), ("net_old - H_v (자연증가 반영)", "− H (expected natural increase)"),
            ("net_old - H_v2 (자연증가 반영)", "− H (both)")]
    for title, start in [("Panel B. Old-core net migration on supply location, all periods (122 cities, 488 city-periods)", "전 기간"),
                         ("Panel C. Register-census periods only (2015–19, 2019–24; 244 city-periods)", "등록센서스 기간만")]:
        k0 = next(k for k, l in enumerate(L) if l.startswith(start))
        rows = []
        for key, lab in labs:
            l = next(x for x in L[k0:] if x.startswith(key))
            cells = re.findall(r"([+-]\d+\.\d+\**)\s*\((\d+\.\d+)\)", l)
            rows.append({"Outcome": lab, **{c: minus(f"{v} ({se})") for c, (v, se) in
                                              zip(["Old core", "New towns", "0–0.5 km", "0.5–2 km", "2–5 km", "> 5 km"], cells)}})
        s += f"\n{title}\n\n" + md(pd.DataFrame(rows))
    return s


def t5():
    z = pd.read_csv(os.path.join(O, "partB", "zone_event_pooled.csv"))
    lab = {"out_zone": "Old core → new town", "out_new": "Old core → new land", "out_rest": "Old core → rest of city",
           "out_outside": "Old core → outside city", "out_capital": "Old core → capital region",
           "in_outside": "Outside city → old core", "net_old": "Old-core net migration",
           "sg_in": "City in-migration (per 1,000 city residents)", "sg_out": "City out-migration (per 1,000 city residents)",
           "sg_net": "City net migration (per 1,000 city residents)"}
    rows = [{"Outcome": lab[r.y], "Post move-in": minus(f"{r.coef:+.2f}"), "Cluster s.e.": f"{r.se:.2f}",
             "Cluster p": "< 0.001" if r.p_cluster < 0.001 else f"{r.p_cluster:.3f}", "Permutation p": "< 0.001" if r.p_perm < 0.001 else f"{r.p_perm:.3f}",
             "Placebo 95% range": minus(f"[{r.placebo_lo:+.2f}, {r.placebo_hi:+.2f}]")} for r in z.itertuples()]
    return md(pd.DataFrame(rows))


def main():
    parts = [("Table 1. Data construction and validation", t1()), ("Table 2. Old-core out-moves by destination (share of "
             "out-moves, moves between old-core neighbourhoods excluded) and net migration (persons a year)", t2()),
             ("Table 3. Age paths of old-core out-migration", t3()), ("Table 4. Supply location, hidden moves and old-core "
             "net migration", t4()), ("Table 5. Opening of the new towns: pooled post-move-in effects (per 1,000 old-core "
             "residents a year unless noted; 10 treated, 109 comparison cities, 2001–2025; 1,000 permutations)", t5())]
    with open(OUT, "w", encoding="utf-8") as f:
        for t, s in parts:
            f.write(f"### {t}\n\n{s}\n")
    print(open(OUT, encoding="utf-8").read())


if __name__ == "__main__":
    main()
