"""Download KOSIS 국내인구이동통계 tables (국가데이터처, orgId 101) into data_work/flows/kosis.sqlite.

Tables (annual):
  od_sgg     DT_1B26003_A02  전출지/전입지(시군구)/성별 이동자수, 2012-2025: (year, out_cd, out_nm, in_cd, in_nm,
                             sex, moves). Codes are KOSIS 시군구 codes (5 digits; 2-digit 시도 and 00 전국 rows kept).
  sgg_moves  DT_1B26001      시군구/성/연령(5세)별 이동자수, 2000-2025: (year, cd, nm, item, sex, age, value);
                             items 총전입, 총전출, 순이동, 시도내이동-시군구내, 시도내이동-시군구간 전입·전출, 시도간전입·전출.
  od_sido    DT_1B26003      전출지/전입지(시도)/성/연령(5세)별 이동자수, 2000-2025: (year, out_cd, out_nm, in_cd,
                             in_nm, sex, age, moves).
sex: 0 계, 1 남, 2 여. age: KOSIS code (000 계, 020 0-4세, ...) with its label in table age_labels.
One request per 전출지 (or 지역); raw JSON kept under data_raw/kosis/{tblId}/{code}.json.gz, so reruns only fetch
what is missing. The key is read from data_raw/kosis/api_key.txt (text after the colon).

Run:  propy.bat code\\05_flows\\fetch_kosis.py
"""
import gzip
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
RAW = os.path.join(paths.RAW, "kosis")
DB = os.path.join(paths.WORK, "flows", "kosis.sqlite")
DATA = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
META = "https://kosis.kr/openapi/statisticsData.do"
WORKERS = 4
TABLES = {
    "od_sgg": dict(tbl="DT_1B26003_A02", itm="T70", by="B", rest="objL2=ALL&objL3=ALL", years=(2012, 2025)),
    "sgg_moves": dict(tbl="DT_1B26001", itm="ALL", by="A", rest="objL2=ALL&objL3=ALL", years=(2000, 2025)),
    "od_sido": dict(tbl="DT_1B26003", itm="T70", by="B", rest="objL2=ALL&objL3=ALL&objL4=ALL", years=(2000, 2025)),
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS od_sgg (year INTEGER, out_cd TEXT, out_nm TEXT, in_cd TEXT, in_nm TEXT, sex TEXT,
                                   moves INTEGER, PRIMARY KEY (year, out_cd, in_cd, sex)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS sgg_moves (year INTEGER, cd TEXT, nm TEXT, item TEXT, sex TEXT, age TEXT, value INTEGER,
                                      PRIMARY KEY (year, cd, item, sex, age)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS od_sido (year INTEGER, out_cd TEXT, out_nm TEXT, in_cd TEXT, in_nm TEXT, sex TEXT,
                                    age TEXT, moves INTEGER, PRIMARY KEY (year, out_cd, in_cd, sex, age)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS age_labels (age TEXT PRIMARY KEY, label TEXT);
CREATE TABLE IF NOT EXISTS item_labels (item TEXT PRIMARY KEY, label TEXT);
CREATE TABLE IF NOT EXISTS source (tbl TEXT PRIMARY KEY, name TEXT, years TEXT, fetched_at TEXT);
"""


def key():
    with open(os.path.join(RAW, "api_key.txt"), encoding="utf-8") as f:
        return f.read().split(":", 1)[1].strip()


def get(url, k, **p):
    q = urllib.parse.urlencode(dict(apiKey=k, format="json", jsonVD="Y", **p), safe="+")
    for t in range(4):
        try:
            with urllib.request.urlopen(f"{url}?{q}", timeout=180) as r:
                return r.read().decode("utf-8")
        except Exception:
            if t == 3:
                raise
            time.sleep(10 * (t + 1))


def codes(k, tbl, obj):
    d = json.loads(get(META, k, method="getMeta", type="ITM", orgId="101", tblId=tbl))
    return [(x["ITM_ID"], x["ITM_NM"]) for x in d if x["OBJ_ID"] == obj]


def fetch(k, name, spec):
    tbl = spec["tbl"]
    d = os.path.join(RAW, tbl)
    os.makedirs(d, exist_ok=True)
    regions = codes(k, tbl, spec["by"])
    a, b = spec["years"]

    def one(cd):
        f = os.path.join(d, f"{cd}.json.gz")
        if os.path.exists(f):
            return 0
        url = (f"{DATA}?method=getList&apiKey={k}&format=json&jsonVD=Y&orgId=101&tblId={tbl}&itmId={spec['itm']}"
               f"&objL1={cd}&{spec['rest']}&prdSe=Y&startPrdDe={a}&endPrdDe={b}")
        for t in range(4):
            try:
                with urllib.request.urlopen(url, timeout=180) as r:
                    s = r.read().decode("utf-8")
                break
            except Exception:
                if t == 3:
                    raise
                time.sleep(10 * (t + 1))
        if '"err":"30"' in s:  # no data for this code (e.g. a retired 시도 code)
            s = "[]"
        if not s.lstrip().startswith("["):
            raise RuntimeError(f"{tbl} {cd}: {s[:300]}")
        with gzip.open(f + ".tmp", "wt", encoding="utf-8") as fh:
            fh.write(s)
        os.replace(f + ".tmp", f)
        return 1

    with ThreadPoolExecutor(WORKERS) as ex:
        n = sum(ex.map(one, [cd for cd, _ in regions]))
    print(f"{name} ({tbl}): 지역 {len(regions)}, 이번에 받은 요청 {n}", flush=True)
    return regions


def load(con, name, spec):
    d = os.path.join(RAW, spec["tbl"])
    rows = []
    for f in sorted(os.listdir(d)):
        with gzip.open(os.path.join(d, f), "rt", encoding="utf-8") as fh:
            for x in json.load(fh):
                v = x.get("DT")
                v = int(float(v)) if v not in (None, "", "-") else None
                if name == "od_sgg":
                    rows.append((int(x["PRD_DE"]), x["C1"], x["C1_NM"], x["C2"], x["C2_NM"], x["C3"], v))
                elif name == "sgg_moves":
                    rows.append((int(x["PRD_DE"]), x["C1"], x["C1_NM"], x["ITM_ID"], x["C2"], x["C3"], v))
                    con.execute("INSERT OR IGNORE INTO item_labels VALUES (?,?)", (x["ITM_ID"], x["ITM_NM"]))
                    con.execute("INSERT OR IGNORE INTO age_labels VALUES (?,?)", (x["C3"], x["C3_NM"]))
                else:
                    rows.append((int(x["PRD_DE"]), x["C1"], x["C1_NM"], x["C2"], x["C2_NM"], x["C3"], x["C4"], v))
    if not rows:
        return
    ph = ",".join("?" * len(rows[0]))
    with con:
        con.execute(f"DELETE FROM {name}")
        con.executemany(f"INSERT OR REPLACE INTO {name} VALUES ({ph})", rows)
        con.execute("INSERT OR REPLACE INTO source VALUES (?,?,?,?)",
                    (spec["tbl"], name, "{}-{}".format(*spec["years"]), time.strftime("%Y-%m-%d %H:%M")))
    print(f"  {name}: {len(rows):,} 행 적재", flush=True)


def main():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    k = key()
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    for name, spec in TABLES.items():
        fetch(k, name, spec)
        load(con, name, spec)
    con.close()


if __name__ == "__main__":
    main()
