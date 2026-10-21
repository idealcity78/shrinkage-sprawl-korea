"""Build the 2001-2025 internal-migration database from MDIS 국내인구이동통계 인구관련연간자료 (공공용 microdata).

Input   data_raw/mdis/migration/{year}/zip/*.zip   one CSV per year, no header, 41 fields, one row per 전입신고
        fields  0-2 전입 시도·시군구·읍면동 | 3-5 전입 년·월·일 | 6-8 전출 시도·시군구·읍면동 | 9 전입사유
                10-39 전입자 1-10 × (세대주관계, 만나이, 성별) | 40 일련번호
Output  data_work/flows/mdis/records/{year}.parquet   every record, typed (the full-detail store)
        data_work/flows/mdis/moves_mdis.sqlite
          flows_dong (year, in_cd, out_cd, reason, hh, pers, male, feml, a00_14, a15_24, a25_39, a40_64, a65p, age_na)
          flows_sgg  (year, month, in_sgg, out_sgg, reason, ...same counts)
          codes      (cd, first_year, last_year, hh_in, hh_out)   읍면동 codes seen in the data
          reasons    (year, reason, hh, pers)
          loaded     (year, zip, records, persons, same_dong_share, built_at)
hh = 전입신고 건수 (moving households), pers = persons. Codes are the 10-digit 행정기관코드 (TEXT), sgg = first 5 digits.
Coding notes found in the data:
  * 성별 uses the resident-number digit (1/3 male, 2/4 female, 3-4 = born 2000+); mapped odd -> male, even -> female.
  * 만나이 above 110 is treated as missing (2001 has values up to 201); missing ages are counted in age_na.
  * 전입사유 is 9 for every record before reasons were collected (e.g. 2001); codes are kept raw, see reasons.
  * Moves inside one 읍면동 are absent in early years (same_dong_share = 0 in 2001) but present later (0.22 in 2015);
    compare across years only after dropping in_cd = out_cd.
The SQLite file is built in the local temp folder and then copied over the old one, so a failed run leaves it intact.

Run:  propy.bat code\\05_flows\\build_mdis_db.py [years...]     (parquet files that exist are reused;
      with years given, the database goes to moves_mdis_partial.sqlite)
"""
import glob
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.csv as pc
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
RAW = os.path.join(paths.RAW, "mdis", "migration")
OUT = os.path.join(paths.WORK, "flows", "mdis")
REC = os.path.join(OUT, "records")
DB = os.path.join(OUT, "moves_mdis.sqlite")
YEARS = range(2001, 2026)
BANDS = [("a00_14", 0, 14), ("a15_24", 15, 24), ("a25_39", 25, 39), ("a40_64", 40, 64), ("a65p", 65, 110)]
COUNTS = ["hh", "pers", "male", "feml"] + [b for b, _, _ in BANDS] + ["age_na"]
SCHEMA = f"""
CREATE TABLE flows_dong (year INTEGER, in_cd TEXT, out_cd TEXT, reason INTEGER, {", ".join(c + " INTEGER" for c in COUNTS)},
                         PRIMARY KEY (year, in_cd, out_cd, reason)) WITHOUT ROWID;
CREATE TABLE flows_sgg (year INTEGER, month INTEGER, in_sgg TEXT, out_sgg TEXT, reason INTEGER,
                        {", ".join(c + " INTEGER" for c in COUNTS)},
                        PRIMARY KEY (year, month, in_sgg, out_sgg, reason)) WITHOUT ROWID;
CREATE TABLE codes (cd TEXT PRIMARY KEY, first_year INTEGER, last_year INTEGER, hh_in INTEGER, hh_out INTEGER);
CREATE TABLE reasons (year INTEGER, reason INTEGER, hh INTEGER, pers INTEGER, PRIMARY KEY (year, reason));
CREATE TABLE loaded (year INTEGER PRIMARY KEY, zip TEXT, records INTEGER, persons INTEGER, same_dong_share REAL,
                     built_at TEXT);
"""
INDEXES = """
CREATE INDEX flows_dong_in ON flows_dong (in_cd, year);
CREATE INDEX flows_dong_out ON flows_dong (out_cd, year);
CREATE INDEX flows_sgg_in ON flows_sgg (in_sgg, year);
CREATE INDEX flows_sgg_out ON flows_sgg (out_sgg, year);
"""


def zip_of(year):
    z = glob.glob(os.path.join(RAW, str(year), "zip", "*.zip"))
    if len(z) != 1:
        raise SystemExit(f"{year}: expected one zip, found {len(z)}")
    return z[0]


def to_parquet(year):
    """Read the year's CSV and write the typed record file; return its path."""
    out = os.path.join(REC, f"{year}.parquet")
    if os.path.exists(out):
        return out
    with zipfile.ZipFile(zip_of(year)) as zf:
        names = zf.namelist()
        if len(names) != 1:
            raise SystemExit(f"{year}: expected one CSV in the zip, found {names}")
        raw = zf.read(names[0])
    tb = pc.read_csv(io.BytesIO(raw), read_options=pc.ReadOptions(autogenerate_column_names=True),
                     convert_options=pc.ConvertOptions(column_types={f"f{i}": pa.string() for i in range(41)}))
    if tb.num_columns != 41:
        raise SystemExit(f"{year}: {tb.num_columns} fields, expected 41")
    d = tb.to_pandas()

    def num(c, hi=None):
        v = pd.to_numeric(d[f"f{c}"].replace("", None), errors="coerce")
        if hi is not None:
            v = v.where(v <= hi)
        return v.astype("Int16")

    rec = pd.DataFrame({
        "in_cd": d.f0 + d.f1.str.zfill(3) + d.f2.str.zfill(5),
        "out_cd": d.f6 + d.f7.str.zfill(3) + d.f8.str.zfill(5),
        "year": num(3), "month": num(4), "day": num(5), "reason": num(9)})
    if (rec.year != year).any():
        raise SystemExit(f"{year}: rows from another 전입연도")
    for k in range(10):
        rec[f"rel{k + 1}"] = num(10 + 3 * k)
        rec[f"age{k + 1}"] = num(11 + 3 * k, hi=110)
        rec[f"sex{k + 1}"] = num(12 + 3 * k)
    rec["serial"] = pd.to_numeric(d.f40, errors="coerce").astype("Int64")
    os.makedirs(REC, exist_ok=True)
    tmp = out + ".tmp"
    pq.write_table(pa.Table.from_pandas(rec, preserve_index=False), tmp, compression="zstd")
    os.replace(tmp, out)
    return out


def persons(rec):
    """One row per person: record index, sex (M/F/None), age (may be NA). A person exists when 관계, 나이 or 성별 is filled."""
    parts = []
    for k in range(1, 11):
        p = pd.DataFrame({"i": rec.index, "rel": rec[f"rel{k}"], "age": rec[f"age{k}"], "sex": rec[f"sex{k}"]})
        parts.append(p[p.rel.notna() | p.age.notna() | p.sex.notna()])
    p = pd.concat(parts, ignore_index=True)
    s = p.sex.astype("float")
    p["male"] = (s % 2 == 1).astype(np.int64)
    p["feml"] = ((s % 2 == 0) & s.notna()).astype(np.int64)
    a = p.age.astype("float")
    for b, lo, hi in BANDS:
        p[b] = ((a >= lo) & (a <= hi)).astype(np.int64)
    p["age_na"] = a.isna().astype(np.int64)
    return p


def aggregate(rec):
    """Return (flows_dong, flows_sgg) frames for one year."""
    p = persons(rec)
    per = p.groupby("i")[["male", "feml"] + [b for b, _, _ in BANDS] + ["age_na"]].sum()
    per["pers"] = p.groupby("i").size()
    r = rec[["in_cd", "out_cd", "year", "month", "reason"]].join(per).fillna(0)
    r["hh"] = 1
    r["reason"] = r.reason.astype("float").fillna(-1).astype(int)  # -1 = blank 전입사유
    r["in_sgg"], r["out_sgg"] = r.in_cd.str[:5], r.out_cd.str[:5]
    dong = r.groupby(["year", "in_cd", "out_cd", "reason"], as_index=False)[COUNTS].sum()
    sgg = r.groupby(["year", "month", "in_sgg", "out_sgg", "reason"], as_index=False)[COUNTS].sum()
    return dong, sgg, int(per.pers.sum())


def main():
    years = [int(a) for a in sys.argv[1:]] or list(YEARS)
    db = DB if years == list(YEARS) else DB.replace(".sqlite", "_partial.sqlite")  # a test run never replaces the full DB
    tmpdb = os.path.join(tempfile.gettempdir(), "moves_mdis_build.sqlite")
    if os.path.exists(tmpdb):
        os.remove(tmpdb)
    con = sqlite3.connect(tmpdb)
    con.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)
    codes = {}
    for y in years:
        t = time.time()
        rec = pd.read_parquet(to_parquet(y))
        dong, sgg, npers = aggregate(rec)
        ints = lambda df, c: [tuple(int(v) if isinstance(v, (np.integer, int)) else v for v in row)
                              for row in df[c].itertuples(index=False)]
        con.executemany(f"INSERT INTO flows_dong VALUES ({','.join('?' * (4 + len(COUNTS)))})",
                        ints(dong, ["year", "in_cd", "out_cd", "reason"] + COUNTS))
        con.executemany(f"INSERT INTO flows_sgg VALUES ({','.join('?' * (5 + len(COUNTS)))})",
                        ints(sgg, ["year", "month", "in_sgg", "out_sgg", "reason"] + COUNTS))
        rs = dong.groupby("reason")[["hh", "pers"]].sum()
        con.executemany("INSERT INTO reasons VALUES (?,?,?,?)",
                        [(y, int(k), int(v.hh), int(v.pers)) for k, v in rs.iterrows()])
        for side, col in (("in", "in_cd"), ("out", "out_cd")):
            for cd, n in rec[col].value_counts().items():
                c = codes.setdefault(cd, [y, y, 0, 0])
                c[0], c[1] = min(c[0], y), max(c[1], y)
                c[2 if side == "in" else 3] += int(n)
        same = float((rec.in_cd == rec.out_cd).mean())
        con.execute("INSERT INTO loaded VALUES (?,?,?,?,?,datetime('now','localtime'))",
                    (y, os.path.basename(zip_of(y)), len(rec), npers, round(same, 4)))
        con.commit()
        print(f"{y}: records {len(rec):,}  persons {npers:,}  dong rows {len(dong):,}  sgg rows {len(sgg):,}  "
              f"same-dong {same:.3f}  {time.time() - t:.0f}s", flush=True)
    con.executemany("INSERT INTO codes VALUES (?,?,?,?,?)", [(k, *v) for k, v in sorted(codes.items())])
    con.executescript(INDEXES)
    con.commit()
    con.close()
    os.makedirs(OUT, exist_ok=True)
    shutil.copyfile(tmpdb, db + ".tmp")
    os.replace(db + ".tmp", db)
    os.remove(tmpdb)
    print("written", db, f"{os.path.getsize(db) / 1e9:.2f} GB")


if __name__ == "__main__":
    main()
