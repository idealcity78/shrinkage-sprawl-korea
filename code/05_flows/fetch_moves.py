"""Download 행정동-to-행정동 moves (행정안전부 지역별 인구이동 현황 OpenAPI, data.go.kr 15108093).

API: apis.data.go.kr/1741000/ppltnDataStus/selectPpltnDataStus. Needs both 전입 (mvinAdmmCd) and 전출
(mvtAdmmCd) codes; a 시도 code returns every 동 in it. lv=3 gives 동 on both sides. Months 2022.10 onward,
at most three months per call, at most 100 rows per page. Current 시도 codes (강원 51, 전북 52) also return
the months before the renaming.

Coverage: every move out of, or into, a 동 of the non-metropolitan 도 and 세종 (origins ORIG), against all 17
시도. Pairs per quarter: (any 시도 <- ORIG) and (ORIG <- 시도 outside ORIG).

Raw pages are cached as gzip JSON under data_raw/movement/api/{quarter}/{mvin}_{mvt}_p{page}.json.gz, so the
script can stop when the daily traffic limit is reached and resume the next day.
The service key is read from data_raw/movement/api_key.txt (line with 인증키), never from the repo.

Usage (ArcGIS Pro Python or any Python 3):
  propy.bat code\\05_flows\\fetch_moves.py plan 2026Q2        # count rows / calls for one quarter
  propy.bat code\\05_flows\\fetch_moves.py get 2026Q2 2025Q3   # download quarters (newest first), resumable
  With no quarters, every quarter 2022Q4-2026Q2 (newest first). Three requests run at once; when the daily
  limit is hit the script sleeps until 00:10 and continues.
"""
import gzip
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
URL = "https://apis.data.go.kr/1741000/ppltnDataStus/selectPpltnDataStus"
DIR = os.path.join(paths.RAW, "movement")
API = os.path.join(DIR, "api")
ALL = {"11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전", "31": "울산", "36": "세종",
       "41": "경기", "43": "충북", "44": "충남", "46": "전남", "47": "경북", "48": "경남", "50": "제주", "51": "강원",
       "52": "전북"}
ORIG = ["36", "43", "44", "46", "47", "48", "50", "51", "52"]
FIRST = (2022, 4)
ROWS = 100
WORKERS = 3


class Quota(Exception):
    pass


def key():
    with open(os.path.join(DIR, "api_key.txt"), encoding="utf-8") as f:
        for line in f:
            if "인증키" in line:
                return line.split(":", 1)[1].strip()
    raise SystemExit("api_key.txt has no 인증키 line")


def quarter(q):
    y, n = int(q[:4]), int(q[-1])
    return f"{y}{3 * n - 2:02d}", f"{y}{3 * n:02d}"


def pairs():
    out = [(d, o) for o in ORIG for d in ALL]
    out += [(o, d) for o in ORIG for d in ALL if d not in ORIG]
    return [(a + "00000000", b + "00000000") for a, b in out]


def call(k, mvin, mvt, fr, to, n, page, tries=4):
    q = (f"?serviceKey={k}&mvinAdmmCd={mvin}&mvtAdmmCd={mvt}&srchFrYm={fr}&srchToYm={to}&lv=3&type=JSON"
         f"&numOfRows={n}&pageNo={page}")
    for t in range(tries):
        try:
            with urllib.request.urlopen(URL + q, timeout=120) as r:
                s = r.read().decode("utf-8")
            break
        except (urllib.error.URLError, TimeoutError) as e:
            body = e.read().decode("utf-8", "replace") if isinstance(e, urllib.error.HTTPError) else str(e)
            if "LIMITED_NUMBER" in body or "EXCEEDS" in body:
                raise Quota(body[:200])
            if t == tries - 1:
                raise
            time.sleep(5 * (t + 1))
    if "LIMITED_NUMBER" in s or "EXCEEDS" in s:
        raise Quota(s[:200])
    d = json.loads(s)
    h = d["Response"]["head"]
    if h["resultCode"] not in ("0", "3"):  # 3 = NODATA
        raise RuntimeError(f"{mvin} {mvt} {fr} p{page}: {h}")
    return d, s


def plan(q):
    k = key()
    fr, to = quarter(q)
    rows = calls = 0
    for mvin, mvt in pairs():
        d, _ = call(k, mvin, mvt, fr, to, 1, 1)
        n = int(d["Response"]["head"]["totalCount"])
        rows += n
        calls += max(1, math.ceil(n / ROWS))
    print(f"{q}: {len(pairs())} 시도 쌍, {rows:,} 행, 필요 호출 {calls:,}회 (+ 계획용 {len(pairs())}회)")


def load(f):
    try:
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, EOFError, json.JSONDecodeError):
        os.remove(f)  # partial file from an interrupted run
        return None


def fetch_pair(k, q, mvin, mvt, counter):
    fr, to = quarter(q)
    stem = os.path.join(API, q, f"{mvin[:2]}_{mvt[:2]}")
    if os.path.exists(stem + "_done"):
        return
    page, pages = 1, 1
    while page <= pages:
        f = f"{stem}_p{page}.json.gz"
        d = load(f) if os.path.exists(f) else None
        if d is None:
            d, s = call(k, mvin, mvt, fr, to, ROWS, page)
            counter.append(1)
            with gzip.open(f + ".tmp", "wt", encoding="utf-8") as fh:
                fh.write(s)
            os.replace(f + ".tmp", f)
        pages = math.ceil(int(d["Response"]["head"]["totalCount"]) / ROWS)
        page += 1
    open(stem + "_done", "w").close()


def get(quarters, workers=WORKERS):
    k = key()
    used = []
    for q in quarters:
        qd = os.path.join(API, q)
        os.makedirs(qd, exist_ok=True)
        done = os.path.join(qd, "_done")
        if os.path.exists(done):
            continue
        with ThreadPoolExecutor(workers) as ex:
            futs = [ex.submit(fetch_pair, k, q, a, b, used) for a, b in pairs()]
            for fu in as_completed(futs):
                fu.result()  # re-raises Quota and other errors
        open(done, "w").close()
        print(f"{time.strftime('%m-%d %H:%M')} {q}: 완료 (이번 실행 호출 {len(used):,}회)", flush=True)
    return len(used)


def get_all(quarters):
    """Keep going until every quarter is done; after the daily limit, wait for the reset (after midnight)."""
    while True:
        try:
            get(quarters)
            print("모든 분기 완료", flush=True)
            return
        except Quota as e:
            now = time.time()
            t = time.localtime(now)
            wake = time.mktime((t.tm_year, t.tm_mon, t.tm_mday + 1, 0, 10, 0, 0, 0, -1))
            print(f"{time.strftime('%m-%d %H:%M')} 일일 호출 한도 도달, {time.strftime('%m-%d %H:%M', time.localtime(wake))}"
                  f"까지 대기: {str(e)[:120]}", flush=True)
            time.sleep(max(60, wake - now))
        except Exception as e:  # network or server trouble: wait and retry
            print(f"{time.strftime('%m-%d %H:%M')} 오류, 10분 후 재시도: {str(e)[:200]}", flush=True)
            time.sleep(600)


def all_quarters():
    y, n = 2026, 2
    out = []
    while (y, n) >= FIRST:
        out.append(f"{y}Q{n}")
        y, n = (y, n - 1) if n > 1 else (y - 1, 4)
    return out


if __name__ == "__main__":
    cmd = sys.argv[1]
    qs = sys.argv[2:] or all_quarters()
    if cmd == "plan":
        for q in qs:
            plan(q)
    else:
        get_all(qs)
