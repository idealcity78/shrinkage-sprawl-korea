"""Part B: did innovation cities accelerate the decline of their parent cities' 기성시가지? Event-study DiD.

Treated : 기성시가지 of the non-metropolitan parent 시군 of innovation cities (원주, 진주, 김천, 나주, 진천, 음성,
          전주, 완주, 서귀포). Designation 2007; construction and agency relocation 2012-2016.
Control : 기성시가지 of 비수도권 시군 with no innovation or enterprise city, excluding 광역시 and 세종.
기성시가지: L1 2009 urban >= 50 % cells, minus every innovation / enterprise zone and a 500 m band around it.

A. Population on 500 m blocks (sum over 기성시가지 cells; SGIS grid 2000, 2005, 2010, 2015, 2019-2024; blocks
   with >= 100 residents in 2005). log(pop) on block and year effects plus treated x year, 2005 = reference;
   errors clustered by 시군. Also a pooled DiD with post = 2015+, by distance band to the zone within treated
   시군 (0-3, 3-6, 6+ km), and with controls restricted to the 25 시군 closest to the treated ones on 2005
   population, 2000-2005 change and 시/군 (nearest-neighbour on standardised values).
B. Aging on census blocks (집계구, 2000, 2005, 2010, 2015, 2019, 2020, 2022, 2024): 65+ share (%) in 기성시가지
   집계구 with >= 50 residents in 2005, same event-study.
Note: the 2010 -> 2015 census change hits treated and control alike and is absorbed by the year effects.

Output: outputs/partB/partB_event_pop.csv, partB_event_age.csv, partB_pooled.csv, partB_did.txt
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\partB_did.py
"""
import os
import sys
import tempfile

import arcpy
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "02_grid"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "03_partA"))
import paths
import sigun
from oa_aging import OA, CSV, OLD65, TOTAL, NA_VALUE

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partB")
TREATED = ["원주시", "진주시", "김천시", "나주시", "진천군", "음성군", "전주시", "완주군", "서귀포시"]
ENTERPRISE = ["원주시", "충주시", "태안군", "영암군", "해남군"]
POP_YEARS = [2000, 2005, 2010, 2015, 2019, 2020, 2021, 2022, 2023, 2024]
AGE_YEARS = [2000, 2005, 2010, 2015, 2019, 2020, 2022, 2024]
REF = 2005
BLOCK = 5
BUFFER = 5  # cells (500 m)


def sgis_pop(year, shape):
    z = np.load(os.path.join(GRID, "sgis_pop.npz"))
    a = np.zeros(shape[0] * shape[1], np.float32)
    v = z[f"y{year}_val"]
    a[z[f"y{year}_idx"]] = np.where(v < 0, 2.5, v)
    return a.reshape(shape)


def blocks(a):
    r, c = a.shape[0] // BLOCK, a.shape[1] // BLOCK
    return a[:r * BLOCK, :c * BLOCK].reshape(r, BLOCK, c, BLOCK)


def event(df, y, unit, label, say, weights=None):
    """Event-study: y on unit and year effects plus treated x year (REF omitted), errors clustered by 시군.
    weights: column name for WLS (e.g. base-year population), else OLS (each unit counts once)."""
    for t in sorted(df.year.unique()):
        if t != REF:
            df[f"tr_{t}"] = ((df.year == t) & (df.treated == 1)).astype(int)
    terms = " + ".join(f"tr_{t}" for t in sorted(df.year.unique()) if t != REF)
    f = f"{y} ~ {terms} + C({unit}) + C(year)"
    fit = smf.wls(f, data=df, weights=df[weights]) if weights else smf.ols(f, data=df)
    m = fit.fit(cov_type="cluster", cov_kwds={"groups": df.sg})
    rows = []
    say(f"\n== {label}: {y}, 처치 x 연도 (기준 {REF}), n={int(m.nobs):,}, 단위 {df[unit].nunique():,}, "
        f"시군 {df.sg.nunique()} (처치 {df[df.treated == 1].sg.nunique()})")
    for t in sorted(df.year.unique()):
        if t == REF:
            rows.append([label, y, t, 0.0, 0.0, None])
            continue
        k = f"tr_{t}"
        p = m.pvalues[k]
        star = "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""
        say(f"   {t}: {m.params[k]:+.4f} ({m.bse[k]:.4f}){star}")
        rows.append([label, y, t, m.params[k], m.bse[k], p])
    return rows


def pooled(df, y, unit, label, say, extra=""):
    df = df.copy()
    df["post"] = (df.year >= 2015).astype(int)
    df["tp"] = df.treated * df.post
    m = smf.ols(f"{y} ~ tp{extra} + C({unit}) + C(year)", data=df).fit(cov_type="cluster", cov_kwds={"groups": df.sg})
    out = []
    for k in [v for v in m.params.index if v.startswith("tp")]:
        p = m.pvalues[k]
        star = "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""
        say(f"   {label} {k}: {m.params[k]:+.4f} ({m.bse[k]:.4f}){star}  n={int(m.nobs):,}")
        out.append([label, y, k, m.params[k], m.bse[k], p, int(m.nobs)])
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    a = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(a["x0"]), int(a["y0"])
    shape = a["urb"].shape
    sg, names, cap = sigun.raster(x0, y0, *shape)
    by_name = {v: k for k, v in names.items()}
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"]
    near_zone = ndimage.binary_dilation(zone > 0, iterations=BUFFER)
    old = (a["urb"] >= 50) & ~near_zone
    excl = set(ENTERPRISE) | {"세종시"} | {n for n in names.values() if n.endswith("광역시")}
    treat_ids = {by_name[n] for n in TREATED}
    ctrl_ids = {i for i, n in names.items() if i not in cap and n not in excl and i not in treat_ids}
    say(f"처치 시군 {len(treat_ids)}, 비교 시군 {len(ctrl_ids)}")
    dist = (ndimage.distance_transform_edt(zone == 0) * 0.1).astype(np.float32)

    # A. population on 500 m blocks
    keep = old & np.isin(sg, list(treat_ids | ctrl_ids))
    pops = {y: blocks(sgis_pop(y, shape) * keep).sum(axis=(1, 3)).ravel() for y in POP_YEARS}
    bsg = blocks(np.where(keep, sg, 0)).max(axis=(1, 3)).ravel()
    bdist = blocks(np.where(keep, dist, 1e6)).min(axis=(1, 3)).ravel()
    ok = (bsg > 0) & (pops[REF] >= 100)
    for y in POP_YEARS:
        ok &= pops[y] > 0
    ids = np.nonzero(ok)[0]
    long = pd.DataFrame([(b, y, pops[y][b], bsg[b], bdist[b]) for y in POP_YEARS for b in ids],
                        columns=["block", "year", "pop", "sg", "dist"])
    long["treated"] = long.sg.isin(treat_ids).astype(int)
    long["lpop"] = np.log(long["pop"])
    say(f"기성시가지 블록 (2005년 100명 이상, 전 연도 인구 있음): {len(ids):,}개, 처치 {long[long.treated == 1].block.nunique():,}")
    tot = long.groupby(["treated", "year"])["pop"].sum().unstack(0)
    tot = tot / tot.loc[REF]
    say("\n기성시가지 인구 지수 (2005 = 1; 0 비교, 1 처치)")
    say(tot.round(3).to_string())

    ev = event(long.copy(), "lpop", "block", "인구(로그), 전체 비교군", say)
    long["w05"] = long.block.map(dict(zip(ids, pops[REF][ids])))
    ev += event(long.copy(), "lpop", "block", "인구(로그), 전체 비교군, 2005 인구 가중", say, weights="w05")

    # each treated 시군 against the control distribution: 기성시가지 population 2024 / 2005
    g = long[long.year.isin([REF, 2024])].groupby(["sg", "year"])["pop"].sum().unstack()
    g["idx"] = g[2024] / g[REF]
    ctrl = g.loc[g.index.isin(ctrl_ids), "idx"]
    say(f"\n시군별 기성시가지 인구 2024/2005: 비교 시군 중앙값 {ctrl.median():.3f} (사분위 {ctrl.quantile(.25):.3f}-{ctrl.quantile(.75):.3f})")
    for i in sorted(treat_ids, key=lambda i: names[i]):
        if i in g.index:
            pct = (ctrl < g.loc[i, "idx"]).mean()
            say(f"   {names[i]}: {g.loc[i, 'idx']:.3f}  (비교 시군 중 백분위 {pct:.0%}, 2005 기성시가지 인구 {g.loc[i, REF]:,.0f})")

    # matched controls on 시군 traits
    sp = pd.read_csv(os.path.join(paths.OUTPUTS, "partA", "sigun_panel.csv"))
    sp["lp05"] = np.log(sp.pop2005)
    sp["pre"] = sp.pop2005 / sp.pop2000 - 1
    feats = sp.set_index("SG_ID")[["lp05", "pre", "si"]]
    feats = (feats - feats.mean()) / feats.std()
    t_f = feats.loc[[i for i in treat_ids if i in feats.index]]
    c_f = feats.loc[[i for i in ctrl_ids if i in feats.index]]
    dmin = np.min(np.linalg.norm(c_f.values[:, None, :] - t_f.values[None, :, :], axis=2), axis=1)
    matched = set(c_f.index[np.argsort(dmin)[:25]])
    say(f"\n짝지은 비교 시군 25: {', '.join(sorted(names[i] for i in matched))}")
    sub = long[long.sg.isin(treat_ids | matched)].copy()
    ev += event(sub, "lpop", "block", "인구(로그), 짝지은 비교군", say)

    say("\n== 통합 DiD (post = 2015년 이후)")
    po = pooled(long, "lpop", "block", "전체 비교군", say)
    po += pooled(sub, "lpop", "block", "짝지은 비교군", say)
    long["tp_0_3"] = ((long.treated == 1) & (long.dist < 3)).astype(int)
    long["tp_3_6"] = ((long.treated == 1) & (long.dist >= 3) & (long.dist < 6)).astype(int)
    long["tp_6p"] = ((long.treated == 1) & (long.dist >= 6)).astype(int)
    lb = long.copy()
    lb["post"] = (lb.year >= 2015).astype(int)
    for k in ("tp_0_3", "tp_3_6", "tp_6p"):
        lb[k] = lb[k] * lb.post
    m = smf.ols("lpop ~ tp_0_3 + tp_3_6 + tp_6p + C(block) + C(year)", data=lb).fit(cov_type="cluster", cov_kwds={"groups": lb.sg})
    say("   혁신도시까지 거리별 (처치 시군 안):")
    for k in ("tp_0_3", "tp_3_6", "tp_6p"):
        p = m.pvalues[k]
        star = "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""
        n_b = lb[(lb[k] == 1)].block.nunique()
        say(f"     {k}: {m.params[k]:+.4f} ({m.bse[k]:.4f}){star}  블록 {n_b}")
        po.append(["거리대", "lpop", k, m.params[k], m.bse[k], p, int(m.nobs)])

    # B. aging on census blocks
    tmp = tempfile.mkdtemp(prefix="oa_")
    pts = os.path.join(arcpy.management.CreateFileGDB(tmp, "o.gdb")[0], "pts")
    arcpy.management.FeatureToPoint(OA, pts, "INSIDE")
    ytop = y0 + shape[0] * 100
    meta = {}
    with arcpy.da.SearchCursor(pts, ["TOT_OA_CD", "SHAPE@XY"]) as cur:
        for code, (x, y) in cur:
            r, c = int((ytop - y) // 100), int((x - x0) // 100)
            if 0 <= r < shape[0] and 0 <= c < shape[1] and keep[r, c]:
                meta[code] = int(sg[r, c])
    rows = []
    for year in AGE_YEARS:
        tot_, o65 = {}, {}
        with open(CSV.format(year), encoding="cp949") as fh:
            for line in fh:
                p = line.rstrip("\n").split(",")
                if len(p) < 4 or p[1] not in meta or p[2] not in TOTAL:
                    continue
                v = int(p[3]) if p[3].isdigit() else NA_VALUE
                tot_[p[1]] = tot_.get(p[1], 0) + v
                if p[2] in OLD65:
                    o65[p[1]] = o65.get(p[1], 0) + v
        rows += [(k, year, t, o65.get(k, 0), meta[k]) for k, t in tot_.items()]
    oa = pd.DataFrame(rows, columns=["oa", "year", "pop", "p65", "sg"])
    base = oa[(oa.year == REF) & (oa["pop"] >= 50)].oa
    oa = oa[oa.oa.isin(base) & (oa["pop"] > 0)]
    full = oa.groupby("oa").year.nunique()
    oa = oa[oa.oa.isin(full[full == len(AGE_YEARS)].index)].copy()
    oa["treated"] = oa.sg.isin(treat_ids).astype(int)
    oa["share65"] = oa.p65 / oa["pop"] * 100
    say(f"\n기성시가지 집계구 (2005년 50명 이상, 전 연도 있음): {oa.oa.nunique():,}개, 처치 {oa[oa.treated == 1].oa.nunique():,}")
    m65 = oa.groupby(["treated", "year"]).apply(lambda g: g.p65.sum() / g["pop"].sum() * 100).unstack(0)
    say("기성시가지 65세 이상 비율 (%; 0 비교, 1 처치)")
    say(m65.round(2).to_string())
    ag = event(oa.copy(), "share65", "oa", "65세 이상 비율(%p), 전체 비교군", say)
    po += pooled(oa, "share65", "oa", "65세 이상 비율 전체 비교군", say)

    pd.DataFrame(ev, columns=["model", "y", "year", "coef", "se", "p"]).to_csv(os.path.join(OUT, "partB_event_pop.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(ag, columns=["model", "y", "year", "coef", "se", "p"]).to_csv(os.path.join(OUT, "partB_event_age.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(po, columns=["model", "y", "term", "coef", "se", "p", "n"]).to_csv(os.path.join(OUT, "partB_pooled.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "partB_did.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
