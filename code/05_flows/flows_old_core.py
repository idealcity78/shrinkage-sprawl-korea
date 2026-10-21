"""Where do old-core residents move, and where do new-city residents come from? (행정동 moves, 2022.10 onward)

Input : data_work/flows/moves.sqlite (build_moves_db.py), data_work/flows/dong_class.csv (dong_class.py)
Matching: API names to the 2020 SGIS 동 by (시군, 동 name). 시군 = first word of the API 시군구 name
(전주시 완산구 -> 전주시); 고성군 by 시도; 광역시 / 특별시 / 세종 as a whole. 동 created after 2020 or with a name
used twice in one 시군 stay "unmatched" and are reported.

Classes of the other end of a move, seen from a 동 in 시군 S (non-capital, not a 광역시):
  in S        old (old-core 동), zone (innovation / enterprise city 동), other, unmatched
  outside S   metro (광역시 / 세종 of the same region, e.g. 광주 for 전남), same_do (another 시군 of the same 도),
              capital (서울, 인천, 경기), elsewhere
Moves within one 동 are dropped.

Outputs (outputs/flows/):
  old_core_flows.csv    per 시군: old-core out / in / net by class, per 1,000 old-core residents per year,
                        and by age band
  zone_origins.csv      per innovation / enterprise city 동: in-movers by origin class and age band
  flows_old_core.txt    summary
Run with ArcGIS Pro Python:  propy.bat code\\05_flows\\flows_old_core.py
"""
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
FLOWS = os.path.join(paths.WORK, "flows")
DB = os.path.join(FLOWS, "moves.sqlite")
OUT = os.path.join(paths.OUTPUTS, "flows")
AGES = ["a00_14", "a15_24", "a25_39", "a40_64", "a65p"]
DO = {"충청북도": "충북", "충청남도": "충남", "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
      "제주특별자치도": "제주", "강원특별자치도": "강원", "강원도": "강원", "전북특별자치도": "전북", "전라북도": "전북"}
CAPITAL = {"서울특별시", "인천광역시", "경기도"}
METRO_OF = {"전남": {"광주광역시"}, "경남": {"부산광역시", "울산광역시"}, "경북": {"대구광역시"},
            "충남": {"대전광역시", "세종특별자치시"}, "충북": {"대전광역시", "세종특별자치시"}, "전북": set(),
            "강원": set(), "제주": set()}


def sigun_of(ctpv, sgg):
    if ctpv.endswith("광역시") or ctpv.endswith("특별시"):
        return ctpv
    if ctpv == "세종특별자치시":
        return "세종시"
    s = sgg.split()[0] if sgg else ""
    if s == "고성군":
        return "강원고성군" if DO.get(ctpv) == "강원" else "경남고성군"
    return s


def main():
    os.makedirs(OUT, exist_ok=True)
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    con = sqlite3.connect(DB)
    quarters = [q for (q,) in con.execute("SELECT quarter FROM loaded ORDER BY quarter")]
    if not quarters:
        raise SystemExit("moves.sqlite has no quarters yet (build_moves_db.py)")
    mv = pd.read_sql(f"""
        SELECT b.month AS statsYm, b.in_cd AS mvinAdmmCd, b.out_cd AS mvtAdmmCd, b.tot, {', '.join('b.' + a for a in AGES)},
               i.ctpv AS mvinCtpvNm, i.sgg AS mvinSggNm, i.dong AS mvinDongNm,
               o.ctpv AS mvtCtpvNm, o.sgg AS mvtSggNm, o.dong AS mvtDongNm
        FROM moves_band b JOIN admin i ON i.cd = b.in_cd JOIN admin o ON o.cd = b.out_cd""", con)
    con.close()
    months = mv.statsYm.nunique()
    say(f"분기 {len(quarters)}개 ({quarters[0]}~{quarters[-1]}), {mv.statsYm.min()}~{mv.statsYm.max()} ({months}개월), "
        f"행 {len(mv):,}, 이동자 {mv.tot.sum():,}")
    mv = mv[mv.mvinAdmmCd != mv.mvtAdmmCd]

    dc = pd.read_csv(os.path.join(FLOWS, "dong_class.csv"), encoding="utf-8-sig")
    dup = dc.duplicated(["sigun", "dong"], keep=False)
    look = dc[~dup].set_index(["sigun", "dong"])
    for side in ["mvin", "mvt"]:
        sg = [sigun_of(a, b) for a, b in zip(mv[f"{side}CtpvNm"], mv[f"{side}SggNm"])]
        mv[f"{side}_sg"] = sg
        key = pd.MultiIndex.from_arrays([sg, mv[f"{side}DongNm"]])
        mv[f"{side}_cls"] = look.cls.reindex(key).fillna("unmatched").values
        mv[f"{side}_do"] = mv[f"{side}CtpvNm"].map(DO).fillna("")

    def other_end(df, here, there):
        """class of the far end (there) seen from the near end (here)"""
        same = df[f"{here}_sg"] == df[f"{there}_sg"]
        cap = df[f"{there}CtpvNm"].isin(CAPITAL)
        metro = [c in METRO_OF.get(d, set()) for c, d in zip(df[f"{there}CtpvNm"], df[f"{here}_do"])]
        same_do = (df[f"{here}_do"] == df[f"{there}_do"]) & (df[f"{there}_do"] != "")
        return np.select([same, cap, np.array(metro), same_do],
                         [df[f"{there}_cls"], "capital", "metro", "same_do"], "elsewhere")

    # origin side = 전출 (mvt), destination side = 전입 (mvin)
    nc = dc[(dc.capital == 0) & ~dc.sigun.str.endswith("광역시") & (dc.SG_ID > 0)]
    ok_sg = set(nc.sigun)
    out = mv[mv.mvt_sg.isin(ok_sg)].copy()
    out["to"] = other_end(out, "mvt", "mvin")
    inn = mv[mv.mvin_sg.isin(ok_sg)].copy()
    inn["frm"] = other_end(inn, "mvin", "mvt")

    um_o = out[out.mvt_cls == "unmatched"].tot.sum() / out.tot.sum()
    um_i = inn[inn.mvin_cls == "unmatched"].tot.sum() / inn.tot.sum()
    say(f"동 이름 매칭 실패 비율 (이동자 기준): 전출 측 {um_o:.1%}, 전입 측 {um_i:.1%}")

    yr = months / 12
    oldpop = nc[nc.cls == "old"].groupby("sigun").pop2024.sum()
    o = out[out.mvt_cls == "old"].groupby(["mvt_sg", "to"])[["tot"] + AGES].sum()
    i = inn[inn.mvin_cls == "old"].groupby(["mvin_sg", "frm"])[["tot"] + AGES].sum()
    o.index.names = i.index.names = ["sigun", "cls"]
    t = o.add_prefix("out_").join(i.add_prefix("in_"), how="outer").fillna(0)
    for c in ["tot"] + AGES:
        t[f"net_{c}"] = t[f"in_{c}"] - t[f"out_{c}"]
    t = t.reset_index()
    t["old_pop"] = t.sigun.map(oldpop)
    for c in ["out_tot", "in_tot", "net_tot"]:
        t[c + "_rate"] = t[c] / yr / t.old_pop * 1000
    t.to_csv(os.path.join(OUT, "old_core_flows.csv"), index=False, encoding="utf-8-sig")

    order = ["old", "zone", "other", "unmatched", "metro", "same_do", "capital", "elsewhere"]
    say("\n== 비수도권 원도심 동 전체: 상대 지역별 전출·전입·순이동 (명/년)")
    g = t.groupby("cls")[["out_tot", "in_tot", "net_tot"]].sum().reindex(order).fillna(0) / yr
    g["out_share"] = g.out_tot / g.out_tot.sum()
    say(g.round(0).astype({"out_share": float}).round({"out_share": 3}).to_string())
    say(f"원도심 인구 {oldpop.sum():,.0f}명, 순이동 {g.net_tot.sum():+,.0f}명/년 "
        f"({g.net_tot.sum() / oldpop.sum() * 1000:+.1f}‰)")
    say("\n원도심 순이동 연령대 (명/년)")
    say((t.groupby("cls")[[f"net_{a}" for a in AGES]].sum().reindex(order).fillna(0) / yr).round(0).to_string())

    zs = sorted(set(t[t.cls == "zone"].sigun))
    say("\n== 혁신·기업도시가 있는 시군: 원도심 순이동 (명/년, 원도심 1천 명당)")
    w = t[t.sigun.isin(zs)].pivot_table(index="sigun", columns="cls", values="net_tot", aggfunc="sum").reindex(
        columns=order).fillna(0) / yr
    w["total"] = w.sum(axis=1)
    w["old_pop"] = w.index.map(oldpop)
    w["to_zone_share_of_net_loss"] = -w.zone / -w.total.where(w.total < 0)
    w["per1000"] = w.total / w.old_pop * 1000
    say(w.round(2).to_string())

    zo = inn[inn.mvin_cls == "zone"].copy()
    zo["frm2"] = np.where(zo.frm.isin(["old", "other", "unmatched"]), "same_sigun_" + zo.frm, zo.frm)
    z = zo.groupby(["mvin_sg", "mvinDongNm", "frm2"])[["tot"] + AGES].sum().reset_index()
    z.to_csv(os.path.join(OUT, "zone_origins.csv"), index=False, encoding="utf-8-sig")
    say("\n== 혁신·기업도시 동 전입자 출발지 비중")
    p = z.pivot_table(index=["mvin_sg", "mvinDongNm"], columns="frm2", values="tot", aggfunc="sum").fillna(0)
    n = p.sum(axis=1)
    p = p.div(n, axis=0)
    p["inmovers_per_year"] = n / yr
    say(p.round(3).to_string())
    with open(os.path.join(OUT, "flows_old_core.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
