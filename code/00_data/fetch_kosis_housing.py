"""Download KOSIS housing and population tables (vacant and unsold housing, registered population by 시군구)
into data_raw/kosis/{tblId}/.

Tables
  DT_1JU0511    2005 census, vacant housing by type and reason (매매임대이사, 미분양미입주, ...)
  DT_1JU0512    2005 census, vacant housing by type and how long vacant
  DT_1JU1012    2010 census, vacant housing by type, reason, how long vacant, damage
  DT_1JU1512    2015-2025 register census, vacant housing by type and construction year
  DT_1YL202005  2015-2025, vacant housing ratio (지역통계)
  DT_1YL202004E 2007-, monthly unsold housing by 시군구 (지역통계, from 국토교통부)
  DT_MLTM_5328  2007-, monthly unsold housing after completion by 시군구 (국토교통부; 부문·규모 = 계)
  DT_MLTM_2082  2000-, monthly unsold housing by 시군구 (국토교통부 original of DT_1YL202004E)
  DT_1B040A3    1992-2025, resident registration population by 시군구 and sex (December)
  TX_315_2009_H1004   2005-2025, 도시·군기본계획 주요지표(계획개요): 수립일, 목표년도, 계획인구 by 시군 (국토교통부 도시계획현황)
  TX_315_2009_H1004A  2005-2025, 도시·군기본계획 주요지표(토지이용계획): 시가화·시가화예정·보전용지 등 by 시군
  TX_315_2009_H1440   2008-2025, 용도지역(시군구)-도시지역: 주거·상업·공업·녹지지역 면적, 비율
  TX_315_2009_H1100   2005-2025, 개발행위허가(시군구): 건수, 면적 by 허가 종류
A request may return at most 40,000 cells, so the larger tables go one year (and one housing type or 시도) at a time.
Each request is kept as raw JSON (gzip); reruns only fetch what is missing. Then all rows are written to
data_work/housing/{tblId}.csv (prd, region code and name, second classification, item, value).
The key is read from data_raw/kosis/api_key.txt (text after the colon) and never printed.

Run with ArcGIS Pro Python:  propy.bat code\\00_data\\fetch_kosis_housing.py
"""
import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
RAW = os.path.join(paths.RAW, "kosis")
OUT = os.path.join(paths.WORK, "housing")
DATA = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
META = "https://kosis.kr/openapi/statisticsData.do"
# objs: one entry per classification in order (objL1, objL2, ...): "ALL", "split" (one request per code) or "first"
TABLES = {
    "DT_1JU0511": dict(org="101", prd="F", objs=["ALL", "ALL"]),
    "DT_1JU0512": dict(org="101", prd="F", objs=["ALL", "ALL"]),
    "DT_1JU1012": dict(org="101", prd="F", objs=["ALL", "ALL"]),
    "DT_1JU1512": dict(org="101", prd="Y", years=range(2015, 2026), objs=["ALL", "split"]),
    "DT_1YL202005": dict(org="101", prd="Y", years=range(2015, 2026), objs=["ALL"]),
    "DT_1YL202004E": dict(org="101", prd="M", years=range(2000, 2027), objs=["split", "ALL"]),
    "DT_MLTM_2082": dict(org="116", prd="M", years=range(2000, 2027), objs=["split", "ALL"]),
    "DT_1B040A3": dict(org="101", prd="Y", years=range(1992, 2026), objs=["ALL"]),
    "DT_MLTM_5328": dict(org="116", prd="M", years=range(2007, 2027), objs=["split", "ALL", "first", "first"]),
    "TX_315_2009_H1004": dict(org="460", prd="Y", years=range(2005, 2026), objs=["ALL"]),
    "TX_315_2009_H1004A": dict(org="460", prd="Y", years=range(2005, 2026), objs=["ALL", "ALL"]),
    "TX_315_2009_H1440": dict(org="460", prd="Y", years=range(2008, 2026), objs=["ALL", "ALL"]),
    "TX_315_2009_H1100": dict(org="460", prd="Y", years=range(2005, 2026), objs=["ALL", "ALL"]),
}


def key():
    with open(os.path.join(RAW, "api_key.txt"), encoding="utf-8") as f:
        return f.read().split(":", 1)[1].strip()


def get(url, **p):
    q = urllib.parse.urlencode(p, safe="+")
    for t in range(4):
        try:
            with urllib.request.urlopen(f"{url}?{q}", timeout=180) as r:
                return r.read().decode("utf-8")
        except Exception:
            if t == 3:
                raise
            time.sleep(10 * (t + 1))


def meta(k, org, tbl):
    d = json.loads(get(META, method="getMeta", type="ITM", apiKey=k, format="json", jsonVD="Y", orgId=org, tblId=tbl))
    objs = []
    for r in d:
        if r["OBJ_ID"] == "ITEM":
            continue
        if not objs or objs[-1][0] != r["OBJ_ID"]:
            objs.append((r["OBJ_ID"], []))
        objs[-1][1].append(r["ITM_ID"])
    return objs


def fetch(k, tbl, spec):
    d = os.path.join(RAW, tbl)
    os.makedirs(d, exist_ok=True)
    objs = meta(k, spec["org"], tbl)
    sel = []
    for (oid, codes), how in zip(objs, spec["objs"]):
        sel.append(codes[:1] if how == "first" else codes if how == "split" else ["ALL"])
    periods = [None] if spec["prd"] == "F" else list(spec["years"])
    jobs = [(p, c) for p in periods for c in _product(sel)]
    n = 0
    for p, c in jobs:
        tag = "_".join([str(p or "all")] + [x for x in c if x != "ALL"]).replace(".", "-")
        f = os.path.join(d, f"{tag}.json.gz")
        if os.path.exists(f):
            continue
        q = dict(method="getList", apiKey=k, format="json", jsonVD="Y", orgId=spec["org"], tblId=tbl, itmId="ALL",
                 prdSe=spec["prd"])
        for i, x in enumerate(c):
            q[f"objL{i + 1}"] = x
        if p is None:
            q["newEstPrdCnt"] = "1"
        elif spec["prd"] == "M":
            q["startPrdDe"], q["endPrdDe"] = f"{p}01", f"{p}12"
        else:
            q["startPrdDe"] = q["endPrdDe"] = str(p)
        s = get(DATA, **q)
        if '"err":"30"' in s:          # no data for this period
            s = "[]"
        if not s.lstrip().startswith("["):
            raise RuntimeError(f"{tbl} {tag}: {s[:200]}")
        with gzip.open(f + ".tmp", "wt", encoding="utf-8") as fh:
            fh.write(s)
        os.replace(f + ".tmp", f)
        n += 1
    print(f"{tbl}: 요청 {len(jobs)}, 이번에 받음 {n}", flush=True)


def _product(sel):
    out = [[]]
    for codes in sel:
        out = [o + [c] for o in out for c in codes]
    return out


def tidy(tbl):
    rows = []
    d = os.path.join(RAW, tbl)
    for f in sorted(os.listdir(d)):
        with gzip.open(os.path.join(d, f), "rt", encoding="utf-8") as fh:
            rows += json.load(fh)
    t = pd.DataFrame(rows)
    keep = [c for c in ["PRD_DE", "C1", "C1_NM", "C2", "C2_NM", "C3", "C3_NM", "C4", "C4_NM", "ITM_ID", "ITM_NM",
                        "UNIT_NM", "DT"] if c in t]
    t = t[keep].drop_duplicates()
    for c in [c for c in t if c.endswith("_NM")]:
        t[c] = t[c].str.strip()
    num = pd.to_numeric(t.DT, errors="coerce")
    if (num.isna() & t.DT.notna()).any():  # text values such as 수립일 dates
        t["DT_TXT"] = t.DT.astype(str).str.strip()
    t["DT"] = num
    os.makedirs(OUT, exist_ok=True)
    t.to_csv(os.path.join(OUT, f"{tbl}.csv"), index=False, encoding="utf-8-sig")
    print(f"  {tbl}: {len(t):,} rows, 기간 {t.PRD_DE.min()} - {t.PRD_DE.max()}", flush=True)


def main():
    k = key()
    for tbl, spec in TABLES.items():
        if len(sys.argv) > 1 and tbl not in sys.argv[1:]:
            continue
        fetch(k, tbl, spec)
        tidy(tbl)


if __name__ == "__main__":
    main()
