"""Resident registration population by study 시군, 1992-2025 (KOSIS DT_1B040A3, December; Korean nationals).

The grid population switches from the field census (to 2010) to the register census (from 2015) and jumps by 4-6 %
between 2010 and 2015, so population change across that break is measured with this series instead.

KOSIS codes are 5-digit administrative codes on current 시도 numbering (강원 51, 전북 52, 세종 36). Kept rows: 시군구;
구 and 출장소 inside a 시 (same first four digits as the 시, last digit not 0) are dropped. Mapped to the study's
2022 시군: 광역시·세종 as one unit except 울주군 and 군위군; 마산·진해 -> 창원, 청원 -> 청주, 연기 -> 세종,
북·남제주 -> 제주·서귀포, 증평출장소 -> 증평군, 계룡출장소 -> 계룡시, a former 군 that became a 시 (양주, 화성, 광주, 포천,
여주, 당진, ...) -> that 시.

Output: outputs/partA/regpop_sigun.csv (sigun, year, regpop)
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

SRC = os.path.join(paths.WORK, "housing", "DT_1B040A3.csv")
OUT = os.path.join(paths.OUTPUTS, "partA", "regpop_sigun.csv")
METRO = {"11": "서울특별시", "26": "부산광역시", "27": "대구광역시", "28": "인천광역시", "29": "광주광역시",
         "30": "대전광역시", "31": "울산광역시", "36": "세종시"}
OLD = {"마산시": "창원시", "진해시": "창원시", "청원군": "청주시", "연기군": "세종시", "북제주군": "제주시",
       "남제주군": "서귀포시", "증평출장소": "증평군", "계룡출장소": "계룡시"}


def unit(code, name, units):
    s, name = code[:2], str(name).strip()
    if name in ("울주군", "군위군"):
        return name
    if s in METRO:
        return METRO[s]
    if name == "고성군":
        return "강원고성군" if s in ("42", "51") else "경남고성군"
    if name in OLD:
        return OLD[name]
    if name not in units and name.endswith("군") and name[:-1] + "시" in units:
        return name[:-1] + "시"
    return name


def build(units):
    d = pd.read_csv(SRC, dtype={"C1": str, "PRD_DE": str})
    d = d[(d.ITM_NM == "총인구수") & (d.C1.str.len() == 5)]
    # drop 구 and 출장소 inside a 시: the code shares its first four digits with a 시 ending in 0
    si = set(d.loc[d.C1_NM.str.strip().str.endswith("시") & (d.C1.str[-1] == "0"), "C1"])
    d = d[~((d.C1.str[:4] + "0").isin(si) & (d.C1.str[-1] != "0"))]
    d["sigun"] = [unit(c, n, units) for c, n in zip(d.C1, d.C1_NM)]
    d["year"] = d.PRD_DE.astype(int)
    r = d.groupby(["sigun", "year"]).DT.sum().rename("regpop").reset_index()
    miss = sorted(set(r.sigun) - set(units))
    r = r[r.sigun.isin(units)]
    r.to_csv(OUT, index=False, encoding="utf-8-sig")
    return r, miss


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    lv = pd.read_csv(os.path.join(paths.OUTPUTS, "partA", "supply_demand_levels.csv"))
    r, miss = build(set(lv.sigun))
    print(f"{r.sigun.nunique()} 시군, {r.year.min()}-{r.year.max()}; 연결 안 된 이름: {miss}")
