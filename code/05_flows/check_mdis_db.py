"""Check moves_mdis.sqlite against the published KOSIS 시도 × 시도 table (od_sido in kosis.sqlite), every year.

MDIS persons with in_cd <> out_cd (moves inside one 읍면동 dropped; KOSIS counts none) are summed by 전출·전입 시도 and sex
and compared with KOSIS DT_1B26003 (age 계). Old 시도 codes are mapped to the current ones KOSIS uses (42 -> 51 강원,
45 -> 52 전북, 49 -> 50 제주 before 2006). Writes outputs/flows/mdis_check.csv (one row per year) and prints it.

Run:  propy.bat code\\05_flows\\check_mdis_db.py
"""
import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
MDIS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(paths.WORK, "flows", "mdis", "moves_mdis.sqlite")
KOSIS = os.path.join(paths.WORK, "flows", "kosis.sqlite")
OUT = os.path.join(paths.OUTPUTS, "flows", "mdis_check.csv")
SIDO = {"42": "51", "45": "52", "49": "50"}


def main():
    m = pd.read_sql("""SELECT year, substr(out_sgg,1,2) o, substr(in_sgg,1,2) i,
                              SUM(pers) pers, SUM(male) male, SUM(feml) feml
                       FROM flows_sgg GROUP BY 1,2,3""", sqlite3.connect(MDIS))
    # flows_sgg cannot see same-dong moves, so take the same-dong persons from flows_dong and subtract them
    s = pd.read_sql("""SELECT year, substr(out_cd,1,2) o, substr(in_cd,1,2) i,
                              SUM(pers) pers, SUM(male) male, SUM(feml) feml
                       FROM flows_dong WHERE in_cd = out_cd GROUP BY 1,2,3""", sqlite3.connect(MDIS))
    for d in (m, s):
        d["o"], d["i"] = d.o.replace(SIDO), d.i.replace(SIDO)
    m = m.groupby(["year", "o", "i"]).sum()
    s = s.groupby(["year", "o", "i"]).sum().reindex(m.index, fill_value=0)
    m = (m - s).reset_index()
    k = pd.read_sql("""SELECT year, out_cd o, in_cd i, sex, moves FROM od_sido
                       WHERE age = '000' AND out_cd <> '00' AND in_cd <> '00'""", sqlite3.connect(KOSIS))
    k = k.pivot_table(index=["year", "o", "i"], columns="sex", values="moves", aggfunc="sum")
    k.columns = ["k_pers", "k_male", "k_feml"]
    j = m.set_index(["year", "o", "i"]).join(k, how="outer").fillna(0)
    j["diff"] = j.pers - j.k_pers
    rows = []
    for y, g in j.groupby(level="year"):
        if g.pers.sum() == 0:
            continue
        rows.append({"year": y, "mdis_pers": int(g.pers.sum()), "kosis_pers": int(g.k_pers.sum()),
                     "diff_total": int(g["diff"].sum()), "pairs": len(g),
                     "pairs_off": int((g["diff"] != 0).sum()), "max_abs_pair_diff": int(g["diff"].abs().max()),
                     "male_diff": int(g.male.sum() - g.k_male.sum()), "feml_diff": int(g.feml.sum() - g.k_feml.sum())})
    r = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    r.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(r.to_string(index=False))


if __name__ == "__main__":
    main()
