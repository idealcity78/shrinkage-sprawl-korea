"""Load the cached API pages (fetch_moves.py) into one SQLite database, for this study and later ones.

data_work/flows/moves.sqlite
  moves      (month, in_cd, out_cd, tot, male, feml)      one row per month and 전입·전출 행정동 pair
  moves_age  (month, in_cd, out_cd, sex, age, n)          single years 0-110 (110 = 110 and over), n > 0 only
  admin      (cd, ctpv, sgg, dong, first_month, last_month)  names of 행정기관코드 as the API gives them
  loaded     (quarter, pages, rows, loaded_at)            quarters already in the database
  view moves_band: moves with age bands a00_14, a15_24, a25_39, a40_64, a65p
Codes are 행정안전부 10-digit 행정기관코드 (in = 전입지, out = 전출지). Coverage: every move with at least one end
in a 동 of the non-metropolitan 도 or 세종 (see fetch_moves.py); moves inside one 동 are kept as the API gives them.
Only quarters whose download finished (_done) are loaded; a quarter is never loaded twice.

Run:  propy.bat code\\05_flows\\build_moves_db.py
"""
import glob
import gzip
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
API = os.path.join(paths.RAW, "movement", "api")
DB = os.path.join(paths.WORK, "flows", "moves.sqlite")
SCHEMA = """
CREATE TABLE IF NOT EXISTS moves (month TEXT, in_cd TEXT, out_cd TEXT, tot INTEGER, male INTEGER, feml INTEGER,
                                  PRIMARY KEY (month, in_cd, out_cd)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS moves_age (month TEXT, in_cd TEXT, out_cd TEXT, sex TEXT, age INTEGER, n INTEGER,
                                      PRIMARY KEY (month, in_cd, out_cd, sex, age)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS admin (cd TEXT PRIMARY KEY, ctpv TEXT, sgg TEXT, dong TEXT, first_month TEXT,
                                  last_month TEXT);
CREATE TABLE IF NOT EXISTS loaded (quarter TEXT PRIMARY KEY, pages INTEGER, rows INTEGER, loaded_at TEXT);
CREATE INDEX IF NOT EXISTS moves_out ON moves (out_cd, month);
CREATE INDEX IF NOT EXISTS moves_in ON moves (in_cd, month);
DROP VIEW IF EXISTS moves_band;
CREATE VIEW moves_band AS
SELECT m.*,
  COALESCE(SUM(CASE WHEN a.age <= 14 THEN a.n END), 0) AS a00_14,
  COALESCE(SUM(CASE WHEN a.age BETWEEN 15 AND 24 THEN a.n END), 0) AS a15_24,
  COALESCE(SUM(CASE WHEN a.age BETWEEN 25 AND 39 THEN a.n END), 0) AS a25_39,
  COALESCE(SUM(CASE WHEN a.age BETWEEN 40 AND 64 THEN a.n END), 0) AS a40_64,
  COALESCE(SUM(CASE WHEN a.age >= 65 THEN a.n END), 0) AS a65p
FROM moves m LEFT JOIN moves_age a USING (month, in_cd, out_cd)
GROUP BY m.month, m.in_cd, m.out_cd;
"""


def items(f):
    with gzip.open(f, "rt", encoding="utf-8") as fh:
        d = json.load(fh)
    it = d["Response"].get("items") or {}
    it = it.get("item", []) if isinstance(it, dict) else it
    return [it] if isinstance(it, dict) else it


def main():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    have = {q for (q,) in con.execute("SELECT quarter FROM loaded")}
    for qd in sorted(glob.glob(os.path.join(API, "*"))):
        q = os.path.basename(qd)
        if q in have or not os.path.exists(os.path.join(qd, "_done")):
            continue
        pages = sorted(glob.glob(os.path.join(qd, "*.json.gz")))
        mv, ag, names = {}, [], {}
        for f in pages:
            for r in items(f):
                k = (r["statsYm"], r["mvinAdmmCd"], r["mvtAdmmCd"])
                if k in mv:
                    continue  # the same pair can come from two 시도 queries only if codes overlap; keep one
                mv[k] = (int(r["totNmprCnt"]), int(r["maleNmprCnt"]), int(r["femlNmprCnt"]))
                for sex, p in (("M", "male"), ("F", "feml")):
                    for age in range(111):
                        n = int(r.get(f"{p}{age}AgeNmprCnt", 0) or 0)
                        if n:
                            ag.append(k + (sex, age, n))
                for side in ("mvin", "mvt"):
                    cd = r[f"{side}AdmmCd"]
                    nm = (r[f"{side}CtpvNm"], r[f"{side}SggNm"], r[f"{side}DongNm"])
                    lo, hi = names.get(cd, (nm, r["statsYm"], r["statsYm"]))[1:]
                    names[cd] = (nm, min(lo, r["statsYm"]), max(hi, r["statsYm"]))
        with con:
            con.executemany("INSERT OR REPLACE INTO moves VALUES (?,?,?,?,?,?)", [k + v for k, v in mv.items()])
            con.executemany("INSERT OR REPLACE INTO moves_age VALUES (?,?,?,?,?,?)", ag)
            for cd, (nm, lo, hi) in names.items():
                row = con.execute("SELECT first_month, last_month FROM admin WHERE cd = ?", (cd,)).fetchone()
                if row:
                    lo, hi = min(lo, row[0]), max(hi, row[1])
                con.execute("INSERT OR REPLACE INTO admin VALUES (?,?,?,?,?,?)", (cd, *nm, lo, hi))
            con.execute("INSERT INTO loaded VALUES (?,?,?,?)", (q, len(pages), len(mv), time.strftime("%Y-%m-%d %H:%M")))
        print(f"{q}: 페이지 {len(pages):,}, 이동 쌍 {len(mv):,}, 연령 행 {len(ag):,}, "
              f"이동자 {sum(v[0] for v in mv.values()):,}", flush=True)
    n = con.execute("SELECT COUNT(*), SUM(tot), MIN(month), MAX(month) FROM moves").fetchone()
    print(f"DB: 이동 쌍 {n[0]:,}, 이동자 {n[1] or 0:,}, {n[2]}~{n[3]}; 분기 "
          f"{[q for (q,) in con.execute('SELECT quarter FROM loaded ORDER BY quarter')]}")
    con.close()


if __name__ == "__main__":
    main()
