"""Old-core out-migration in the non-capital 도, 2001-2025, from the MDIS 읍면동 moves.

Every move between two 읍면동 (moves inside one 읍면동 dropped; they are missing before 2005) is split over the
parts of its two 읍면동 in proportion to where their residents live on the 100 m grid in that year:
  old   기성시가지 cells (L1 2009 urban >= 50 % and >= 5 housing units in 2000, outside the zones)
  zone  innovation / enterprise city zones
  new   cells with < 5 housing units in 2000 and >= 5 in the year (new residential land outside the zones)
  rest  everything else (villages, rural land, industrial land with few residents)
old and zone shares come from code_year.csv (each code on its own year's boundary); the new share is taken from the
SGIS 2020 행정동 through dong_xwalk.csv population weights.

Seen from 시군 S (frame 시군 of a non-capital 도; 광역시 and 세종 are not origins), a move ends
  in S         old / zone / new / rest
  outside S    same_do (another 시군 of the same 도), metro (the 광역시 / 세종 next to the 도: 광주 for 전남,
               부산·울산 for 경남, 대구 for 경북, 대전·세종 for 충남·충북), capital (서울·인천·경기),
               elsewhere, unknown (code without boundary)
Rows are kept for moves out of S (side = out, by origin part) and for moves into S from outside (side = in,
by destination part), so the old core's net exchange can be built.

Outputs (outputs/flows/)
  mdis_old_core_flows.csv   year, SG_ID, sigun, do, side, part (S end), other (other end), pers and age bands
  mdis_old_core_pop.csv     year, SG_ID, residents by part (grid population of the nearest grid year)
  mdis_old_core.txt         summary
Run with ArcGIS Pro Python:  propy.bat code\\05_flows\\flows_old_core_mdis.py
"""
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "02_grid"))
sys.path.insert(0, HERE)
import paths
from dong_class import dong_raster, sgis
from dong_xwalk import POP_YEARS

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
MDIS = os.path.join(paths.WORK, "flows", "mdis")
OUT = os.path.join(paths.OUTPUTS, "flows")
AGES = ["a00_14", "a15_24", "a25_39", "a40_64", "a65p"]
VALS = ["pers"] + AGES
PARTS = ["old", "zone", "new", "rest"]
SIDO_NOW = {"42": "51", "45": "52", "49": "50"}
DO = {"43": "충북", "44": "충남", "46": "전남", "47": "경북", "48": "경남", "50": "제주", "51": "강원", "52": "전북"}
METRO_OF = {"46": {"29"}, "48": {"26", "31"}, "47": {"27"}, "44": {"30", "36"}, "43": {"30", "36"}}
CAPITAL = {"11", "28", "41"}


def new_share_2020():
    """Share of residents on new residential cells, per SGIS 2020 행정동 and grid year."""
    a = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(a["x0"]), int(a["y0"])
    shape = a["urb"].shape
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    h00 = sgis("house", 2000, shape, na=0)
    did, codes = dong_raster(x0, y0, *shape)
    lab = did.ravel().astype(np.int64)
    k = len(codes) + 1
    out = {}
    for py in POP_YEARS:
        p = sgis("pop", py, shape).ravel().astype(np.float64)
        new = ((h00 < 5) & (sgis("house", py, shape, na=0) >= 5) & ~zone).ravel()
        P = np.bincount(lab, weights=p, minlength=k)
        N = np.bincount(lab, weights=p * new, minlength=k)
        out[py] = pd.Series(np.divide(N, P, out=np.zeros(k), where=P > 0)[1:], index=[c for c, _ in codes])
    return out


def shares():
    """Per (year, cd): old, zone, new, rest shares, SG_ID, sigun, sido (current code)."""
    cy = pd.read_csv(os.path.join(MDIS, "code_year.csv"), dtype={"cd": str})
    xw = pd.read_csv(os.path.join(MDIS, "dong_xwalk.csv"), dtype={"cd": str, "adm_cd2020": str})
    ns = new_share_2020()
    py = {y: min(POP_YEARS, key=lambda p: (abs(p - y), p)) for y in cy.year.unique()}
    xw["ns"] = [ns[py[y]].get(c, 0.0) for y, c in zip(xw.year, xw.adm_cd2020)]
    xw["ns"] = xw.ns * xw.pop_w
    cy = cy.merge(xw.groupby(["year", "cd"]).ns.sum().rename("new").reset_index(), on=["year", "cd"], how="left")
    cy["old"] = cy.old_share.fillna(0)
    cy["zone"] = cy.zone_share.fillna(0)
    cy["new"] = np.minimum(cy.new.fillna(0), 1 - cy.old - cy.zone).clip(lower=0)
    cy["rest"] = (1 - cy.old - cy.zone - cy.new).clip(lower=0)
    cy["sido"] = cy.cd.str[:2].replace(SIDO_NOW)
    cy["SG_ID"] = cy.SG_ID.fillna(0).astype(int)
    return cy[["year", "cd", "sido", "SG_ID", "sigun", "pop", "match"] + PARTS]


def outside(o_sido, d_sido, d_known):
    """Class of a destination outside the origin 시군."""
    if d_sido in CAPITAL:
        return "capital"
    if d_sido in METRO_OF.get(o_sido, set()):
        return "metro"
    if d_sido == o_sido:
        return "same_do" if d_known else "unknown"
    return "elsewhere"


def year_flows(con, y, sh):
    f = pd.read_sql(f"SELECT out_cd, in_cd, {', '.join('SUM(' + v + ') ' + v for v in VALS)} FROM flows_dong "
                    f"WHERE year = {y} AND in_cd <> out_cd GROUP BY out_cd, in_cd", con)
    s = sh[sh.year == y].set_index("cd")
    o = s.add_prefix("o_").reindex(f.out_cd)
    d = s.add_prefix("d_").reindex(f.in_cd)
    f = pd.concat([f.reset_index(drop=True), o.reset_index(drop=True), d.reset_index(drop=True)], axis=1)
    f["o_sido"] = f.o_sido.fillna(f.out_cd.str[:2].replace(SIDO_NOW))
    f["d_sido"] = f.d_sido.fillna(f.in_cd.str[:2].replace(SIDO_NOW))
    f[["o_SG_ID", "d_SG_ID"]] = f[["o_SG_ID", "d_SG_ID"]].fillna(0).astype(int)
    rows = []
    # moves out of a 시군 of a non-capital 도 (and moves inside it)
    out = f[f.o_sido.isin(DO) & (f.o_SG_ID > 0)]
    same = out.d_SG_ID == out.o_SG_ID
    for po in PARTS:
        w = out[f"o_{po}"]
        inside = out[same]
        for pd_ in PARTS:
            ww = (w[same] * inside[f"d_{pd_}"]).values[:, None]
            rows.append(pd.DataFrame(inside[VALS].values * ww, columns=VALS).assign(
                SG_ID=inside.o_SG_ID.values, sido=inside.o_sido.values, side="out", part=po, other=pd_))
        ex = out[~same]
        cls = [outside(a, b, c > 0) for a, b, c in zip(ex.o_sido, ex.d_sido, ex.d_SG_ID)]
        rows.append(pd.DataFrame(ex[VALS].values * w[~same].values[:, None], columns=VALS).assign(
            SG_ID=ex.o_SG_ID.values, sido=ex.o_sido.values, side="out", part=po, other=cls))
    # moves into such a 시군 from outside it
    inn = f[f.d_sido.isin(DO) & (f.d_SG_ID > 0) & (f.d_SG_ID != f.o_SG_ID)]
    cls = [outside(b, a, c > 0) for a, b, c in zip(inn.o_sido, inn.d_sido, inn.o_SG_ID)]
    for pd_ in PARTS:
        rows.append(pd.DataFrame(inn[VALS].values * inn[f"d_{pd_}"].values[:, None], columns=VALS).assign(
            SG_ID=inn.d_SG_ID.values, sido=inn.d_sido.values, side="in", part=pd_, other=cls))
    r = pd.concat(rows, ignore_index=True)
    r = r.groupby(["SG_ID", "sido", "side", "part", "other"], as_index=False)[VALS].sum()
    r.insert(0, "year", y)
    return r


def main():
    os.makedirs(OUT, exist_ok=True)
    sh = shares()
    names = sh[sh.SG_ID > 0].groupby("SG_ID").sigun.agg(lambda s: s.mode().iat[0])
    con = sqlite3.connect(os.path.join(MDIS, "moves_mdis.sqlite"))
    res = []
    for y in sorted(sh.year.unique()):
        res.append(year_flows(con, int(y), sh))
        print(y, flush=True)
    r = pd.concat(res, ignore_index=True)
    r.insert(2, "sigun", r.SG_ID.map(names))
    r.insert(4, "do", r.sido.map(DO))
    r = r.drop(columns="sido")
    r[VALS] = r[VALS].round(2)
    r.to_csv(os.path.join(OUT, "mdis_old_core_flows.csv"), index=False, encoding="utf-8-sig")

    sp = sh[sh.sido.isin(DO) & (sh.SG_ID > 0)].copy()
    for p in PARTS:
        sp[p] = sp[p] * sp["pop"]
    pop = sp.groupby(["year", "SG_ID"])[PARTS].sum().round().reset_index()
    pop.to_csv(os.path.join(OUT, "mdis_old_core_pop.csv"), index=False, encoding="utf-8-sig")
    summary(r, pop)


def summary(r, pop):
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    per = lambda y: f"{(y - 1) // 5 * 5 + 1}-{(y - 1) // 5 * 5 + 5}"
    r = r.assign(period=r.year.map(per))
    pop = pop.assign(period=pop.year.map(per))
    old_out = r[(r.side == "out") & (r.part == "old")]
    say("비수도권 8개 도 시군 원도심(기성시가지) 전출, 읍면동 간 이동, 연평균 (명)")
    t = old_out.pivot_table(index="period", columns="other", values="pers", aggfunc="sum") / 5
    order = ["old", "zone", "new", "rest", "same_do", "metro", "capital", "elsewhere", "unknown"]
    t = t[[c for c in order if c in t]]
    t["total"] = t.sum(axis=1)
    say(t.round(0).to_string())
    say()
    say("같은 비율 (원도심 안 이동 old 제외, %)")
    u = t.drop(columns=["old", "total"])
    say((u.div(u.sum(axis=1), axis=0) * 100).round(1).to_string())
    say()
    # net exchange of the old core: in from other parts of S and from outside, minus out to them
    inn = pd.concat([r[(r.side == "out") & (r.other == "old") & (r.part != "old")].assign(src=lambda d: d.part),
                     r[(r.side == "in") & (r.part == "old")].assign(src=lambda d: d.other)])
    outx = old_out[old_out.other != "old"].assign(src=lambda d: d.other)
    net = (inn.groupby(["period", "src"]).pers.sum() - outx.groupby(["period", "src"]).pers.sum()).unstack() / 5
    net = net[[c for c in order[1:] if c in net]]
    net["total"] = net.sum(axis=1)
    oldpop = pop.groupby(["period", "year"]).old.sum().groupby("period").mean()
    say("원도심 순이동 (전입 - 전출, 연평균, 명) / 원도심 인구 천 명당")
    say(net.round(0).to_string())
    say(pd.DataFrame({"old_core_pop": oldpop.round(0), "net_per_1000": (net["total"] / oldpop * 1000).round(1),
                      "out_per_1000": (outx.groupby("period").pers.sum() / 5 / oldpop * 1000).round(1)}).to_string())
    say()
    say("혁신·기업도시가 있는 시군: 원도심 -> 같은 시군 신도시 이동 (명/년)")
    zs = r[(r.side == "out") & (r.part == "old") & (r.other == "zone")]
    zz = zs.pivot_table(index="sigun", columns="period", values="pers", aggfunc="sum") / 5
    zz = zz[zz.max(axis=1) >= 50]
    say(zz.round(0).to_string())
    say()
    say("신도시 전입자 출신 (연평균, 명): 같은 시군의 원도심 / 신규개발지 / 기타 / 시군 밖")
    zin = pd.concat([r[(r.side == "out") & (r.other == "zone") & (r.part != "zone")].assign(src=lambda d: d.part),
                     r[(r.side == "in") & (r.part == "zone")].assign(src=lambda d: d.other)])
    zt = zin[zin.period.isin(["2011-2015", "2016-2020", "2021-2025"])].pivot_table(
        index="sigun", columns="src", values="pers", aggfunc="sum") / 15
    zt = zt[zt.sum(axis=1) >= 300]
    zt = zt[[c for c in order[:1] + order[2:] if c in zt]]
    zt["total"] = zt.sum(axis=1)
    say((zt.round(0)).to_string())
    with open(os.path.join(OUT, "mdis_old_core.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
