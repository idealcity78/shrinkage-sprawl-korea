"""Traceable data-construction statistics for paper 2 (Table 1).

From the MDIS move database (data_work/flows/mdis/moves_mdis.sqlite) and the code-year crosswalk
(data_work/flows/mdis/code_year.csv, dong_xwalk.py):
  - records, persons and same-동 share per year (table `loaded`)
  - number of distinct 읍면동 codes used 2001-2025 (table `codes`)
  - share of movers between 동 (same-동 moves excluded) whose origin / destination code-year is linked to a
    boundary snapshot (match != "none"), and the code-years without a boundary
Output: outputs/paper2/xwalk_stats.txt
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\paper2_xwalk_stats.py
"""
import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
DB = os.path.join(paths.WORK, "flows", "mdis", "moves_mdis.sqlite").replace("\\", "/")
CY = os.path.join(paths.WORK, "flows", "mdis", "code_year.csv")
OUT = os.path.join(paths.OUTPUTS, "paper2", "xwalk_stats.txt")


def main():
    lines = []

    def say(s=""):
        print(s, flush=True)
        lines.append(s)

    con = sqlite3.connect(DB)
    ld = pd.read_sql("select year, records, persons, same_dong_share from loaded order by year", con)
    say("1. MDIS 연도별 레코드·이동자·같은 동 비율")
    say(ld.to_string(index=False))
    say(f"   레코드 최소 {ld.records.min():,} ({ld.loc[ld.records.idxmin(), 'year']}) 최대 {ld.records.max():,} "
        f"({ld.loc[ld.records.idxmax(), 'year']}), 합계 {ld.records.sum():,}")
    s = ld[ld.year >= 2005].same_dong_share
    say(f"   같은 동 비율 2005-2025: {s.min():.3f}-{s.max():.3f}")
    n_codes = con.execute("select count(*) from codes").fetchone()[0]
    say(f"\n2. 쓰인 읍면동 코드 수 (2001-2025): {n_codes:,}")

    cy = pd.read_csv(CY, dtype={"cd": str})
    say(f"\n3. 코드-연도 {len(cy):,}개, 경계 연결 방식: " + ", ".join(f"{k} {v:,}" for k, v in cy.match.value_counts().items()))
    linked = set(zip(cy.year[cy.match != "none"], cy.cd[cy.match != "none"]))
    rows = []
    for side in ("out_cd", "in_cd"):
        q = (f"select year, {side} as cd, sum(pers) as pers from flows_dong where in_cd <> out_cd "
             f"group by year, {side}")
        t = pd.read_sql(q, con)
        t["linked"] = [(y, c) in linked for y, c in zip(t.year, t.cd)]
        tot, ok = t.pers.sum(), t.loc[t.linked, "pers"].sum()
        rows.append((side, tot, ok))
        say(f"   {side}: 동 간 이동자 {tot:,}, 경계에 연결 {ok:,} ({ok / tot * 100:.2f}%)")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
