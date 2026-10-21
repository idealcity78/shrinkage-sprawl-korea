"""Part A identification checks for the E1 (sprawl) results of partA_basic.py.

partA_basic.py found that 시군 with an innovation city (inno) or an enterprise city (ent) had more new urban land
2009 -> 2019 (new_rate), more of it detached from the 2009 urban area (leap_share), and, for ent, a larger rise in
urban m2 per person (d_lpcu). Three checks of whether that is the supply or the kind of 시군 chosen for it:

  1. pre-trend   the same outcomes for 1999 -> 2009 (large-class maps of the late 1990s and 2009; population 2000
                 and 2010), same model. The cities were designated 2005-2007 but land works started mostly after
                 2009, so a pre-period effect as large as the post effect means selection.
                 stacked:  y_sp = a_s + g_p + b (supply_s x post_p) + controls x post, errors clustered by 시군
  2. placebo     industrial complexes designated after the outcome period (ic_1624, 2016-2024) on the 1999 -> 2009
                 outcomes: future supply cannot cause past sprawl, so a coefficient here measures where complexes
                 are put.
  3. permutation the inno / ent labels given to as many randomly drawn other 시군 (1,000 draws, the other label
                 kept), post-period model re-estimated; p = share of draws with |b| >= the actual |b|.
Sample as in partA_basic.py: 비수도권 시군 without 김천시·영주시 (identical 2009 and 2019 large-class maps there).

Output: outputs/partA/sigun_pre.csv (1999 -> 2009 land by 시군), partA_ident.txt, partA_ident_models.csv
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\partA_ident.py   (add "models" to skip the grid step)
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "02_grid"))
sys.path.insert(0, HERE)
import paths
from partA_basic import L1_SAME, prepare

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partA")
NPERM = 1000
SUPPLY = "ic_0110 + inno + ent"
YS = {"new_rate": "신규 시가지 / 기초 시가지", "leap_share": "비연속 개발 비율", "d_lpcu": "1인당 시가지 로그변화"}


def grid_pre():
    """1999 -> 2009 urban land per 시군, same rules as sigun_panel.py for 2009 -> 2019."""
    import sigun
    from scipy import ndimage
    a, b = np.load(os.path.join(GRID, "l1_1999.npz")), np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(b["x0"]), int(b["y0"])
    sg, names, cap = sigun.raster(x0, y0, *b["urb"].shape)
    u99, u09 = a["urb"].astype(np.int16), b["urb"].astype(np.int16)
    new = (u99 < 10) & (u09 >= 50)
    leap = new & ~ndimage.binary_dilation(u99 >= 50, structure=np.ones((3, 3), bool))
    lab = sg.ravel().astype(np.int64)
    k = int(sg.max()) + 1
    by = lambda w: np.bincount(lab, weights=w.ravel().astype(np.float64), minlength=k)
    r = pd.DataFrame({"SG_ID": np.arange(k), "urb99": by(u99) / 100 * 0.01, "new_urb_pre": by(new) * 0.01,
                      "leap_pre_km2": by(leap) * 0.01})
    r = r[(r.SG_ID > 0) & ~r.SG_ID.isin(cap)]
    r.round(3).to_csv(os.path.join(OUT, "sigun_pre.csv"), index=False, encoding="utf-8-sig")


def data():
    d = prepare()
    p = pd.read_csv(os.path.join(OUT, "sigun_pre.csv"))
    d = d.merge(p, on="SG_ID", how="left")
    d = d[~d.sigun.isin(L1_SAME)].copy()
    d["new_rate_pre"] = d.new_urb_pre / d.urb99
    d["leap_share_pre"] = d.leap_pre_km2 / d.new_urb_pre
    d["d_lpcu_pre"] = np.log((d.urb09 / d.pop2010) / (d.urb99 / d.pop2000))
    d["urb_share99"] = d.urb99 / d.land_km2
    d["d_pop_pre"] = d.pop2010 / d.pop2000 - 1
    return d


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def fmt(m, v):
    return f"{m.params[v]:+.4f} ({m.bse[v]:.4f}){stars(m.pvalues[v])}"


def main():
    if "models" not in sys.argv[1:]:
        grid_pre()
    d = data()
    lines, rows = [], []

    def say(s=""):
        print(s)
        lines.append(s)

    say(f"표본: 비수도권 시군 {len(d)} (김천·영주 제외). 혁신도시 {int(d.inno.sum())}, 기업도시 {int(d.ent.sum())}, "
        f"2001-10 산업단지 1km2 이상 {int((d.ic_0110 >= 1).sum())}")
    t = d[["urb99", "urb09", "urb19", "new_urb_pre", "new_urb"]].sum()
    say(f"시가지 km2: 1999 {t.urb99:,.0f} -> 2009 {t.urb09:,.0f} -> 2019 {t.urb19:,.0f}; "
        f"신규 시가지 1999-2009 {t.new_urb_pre:,.0f}, 2009-2019 {t.new_urb:,.0f}")
    say("\n집단별 평균 (전기 1999-2009 / 후기 2009-2019)")
    grp = np.where(d.inno == 1, "혁신도시", np.where(d.ent == 1, "기업도시", np.where(d.ic_0110 >= 1, "산업단지", "그 외")))
    cols = {}
    for y in YS:
        cols[f"{y} 전기"] = d.groupby(grp)[f"{y}_pre"].mean()
        cols[f"{y} 후기"] = d.groupby(grp)[y].mean()
    say(pd.DataFrame(cols).round(3).to_string())

    # 1. pre-trend: same model on each period
    ctrl_post = "lpop10 + pre_pop + urb_share09 + si + metro"
    ctrl_pre = "lpop00 + urb_share99 + si + metro"
    say("\n1. 사전추세: 같은 모형을 두 기간에 (HC1 표준오차)")
    say("   후기: y(2009-19) ~ " + SUPPLY + " + " + ctrl_post)
    say("   전기: y(1999-09) ~ " + SUPPLY + " + " + ctrl_pre)
    for y, lab in YS.items():
        mp = smf.ols(f"{y} ~ {SUPPLY} + {ctrl_post}", data=d).fit(cov_type="HC1")
        mq = smf.ols(f"{y}_pre ~ {SUPPLY} + {ctrl_pre}", data=d).fit(cov_type="HC1")
        say(f"\n  {lab} ({y})")
        for v in ["inno", "ent", "ic_0110"]:
            say(f"    {v:8s} 후기 {fmt(mp, v)}   전기 {fmt(mq, v)}")
            rows += [["pre_trend", y, v, "post", mp.params[v], mp.bse[v], mp.pvalues[v], int(mp.nobs)],
                     ["pre_trend", y, v, "pre", mq.params[v], mq.bse[v], mq.pvalues[v], int(mq.nobs)]]

    say("\n   두 기간을 쌓은 모형: y ~ 시군 FE + 기간 FE + 공급 x 후기 + (lpop, 시가지 비율, 시, 광역시) x 후기, 시군 군집")
    say("   공급 x 후기 = 후기의 공급 효과가 전기보다 큰 만큼")
    st = []
    for per, sfx, lp, us in [(0, "_pre", "lpop00", "urb_share99"), (1, "", "lpop10", "urb_share09")]:
        x = d[["SG_ID", "inno", "ent", "ic_0110", "si", "metro"]].copy()
        x["post"] = per
        x["lpop"] = d[lp]
        x["us"] = d[us]
        for y in YS:
            x[y] = d[y + sfx]
        st.append(x)
    st = pd.concat(st, ignore_index=True)
    for y, lab in YS.items():
        g = st.dropna(subset=[y])
        m = smf.ols(f"{y} ~ C(SG_ID) + post + inno:post + ent:post + ic_0110:post + lpop:post + us:post + si:post "
                    f"+ metro:post", data=g).fit(cov_type="cluster", cov_kwds={"groups": g.SG_ID})
        say(f"    {lab:14s} inno x 후기 {fmt(m, 'inno:post')}   ent x 후기 {fmt(m, 'ent:post')}   "
            f"ic_0110 x 후기 {fmt(m, 'ic_0110:post')}")
        for v in ["inno:post", "ent:post", "ic_0110:post"]:
            rows.append(["stacked", y, v, "diff", m.params[v], m.bse[v], m.pvalues[v], int(m.nobs)])

    # 1b. ranks: the late-1990s map is noisier (a few mountain 군 and 음성 have new_rate_pre > 1), and map quality
    # differs between periods, so the same models on within-period percentile ranks (0-100)
    say("\n   순위 모형: 각 기간 안 백분위 순위(0-100)로 바꿔 같은 모형 (1990년대 말 지도의 이상값과 기간 간 지도 차이에 강건)")
    for y in YS:
        st[f"r_{y}"] = st.groupby("post")[y].rank(pct=True) * 100
        d[f"r_{y}"] = d[y].rank(pct=True) * 100
        d[f"r_{y}_pre"] = d[f"{y}_pre"].rank(pct=True) * 100
    for y, lab in YS.items():
        mp = smf.ols(f"r_{y} ~ {SUPPLY} + {ctrl_post}", data=d).fit(cov_type="HC1")
        mq = smf.ols(f"r_{y}_pre ~ {SUPPLY} + {ctrl_pre}", data=d).fit(cov_type="HC1")
        g = st.dropna(subset=[f"r_{y}"])
        m = smf.ols(f"r_{y} ~ C(SG_ID) + post + inno:post + ent:post + ic_0110:post + lpop:post + us:post + si:post "
                    f"+ metro:post", data=g).fit(cov_type="cluster", cov_kwds={"groups": g.SG_ID})
        say(f"    {lab:14s} inno 후기 {fmt(mp, 'inno')}, 전기 {fmt(mq, 'inno')}, 차이 {fmt(m, 'inno:post')}")
        say(f"    {'':14s} ent  후기 {fmt(mp, 'ent')}, 전기 {fmt(mq, 'ent')}, 차이 {fmt(m, 'ent:post')}")
        for v, mm, per in [("inno", mp, "post"), ("inno", mq, "pre"), ("ent", mp, "post"), ("ent", mq, "pre")]:
            rows.append(["rank", y, v, per, mm.params[v], mm.bse[v], mm.pvalues[v], int(mm.nobs)])
        for v in ["inno:post", "ent:post"]:
            rows.append(["rank_stacked", y, v, "diff", m.params[v], m.bse[v], m.pvalues[v], int(m.nobs)])

    say("\n   혁신·기업도시 시군별 신규 시가지 비율 순위 (백분위, 전기 -> 후기)")
    t = d[(d.inno == 1) | (d.ent == 1)].set_index("sigun")
    t = pd.DataFrame({"구분": np.where(t.inno == 1, np.where(t.ent == 1, "혁신+기업", "혁신"), "기업"),
                      "new_rate 전기": t.new_rate_pre.round(3), "new_rate 후기": t.new_rate.round(3),
                      "순위 전기": t.r_new_rate_pre.round(0), "순위 후기": t.r_new_rate.round(0),
                      "비연속 순위 전기": t.r_leap_share_pre.round(0), "비연속 순위 후기": t.r_leap_share.round(0)})
    say(t.to_string())

    # 2. placebo: future complexes on past sprawl
    say("\n2. 위약 처치: 결과 기간 뒤에 지정된 산업단지(2016-2024, ic_1624)와 2011-2015 지정분(ic_1115)")
    for y, lab in YS.items():
        mq = smf.ols(f"{y}_pre ~ ic_1624 + ic_1115 + {SUPPLY} + {ctrl_pre}", data=d).fit(cov_type="HC1")
        mp = smf.ols(f"{y} ~ ic_1624 + {SUPPLY} + {ctrl_post}", data=d).fit(cov_type="HC1")
        say(f"    {lab:14s} 전기 y ~ ic_1624 {fmt(mq, 'ic_1624')}, ic_1115 {fmt(mq, 'ic_1115')} | "
            f"후기 y ~ ic_1624 {fmt(mp, 'ic_1624')}  (참고: ic_0110 후기 {fmt(mp, 'ic_0110')})")
        rows += [["placebo", y, "ic_1624", "pre", mq.params["ic_1624"], mq.bse["ic_1624"], mq.pvalues["ic_1624"],
                  int(mq.nobs)],
                 ["placebo", y, "ic_1115", "pre", mq.params["ic_1115"], mq.bse["ic_1115"], mq.pvalues["ic_1115"],
                  int(mq.nobs)],
                 ["placebo", y, "ic_1624", "post", mp.params["ic_1624"], mp.bse["ic_1624"], mp.pvalues["ic_1624"],
                  int(mp.nobs)]]

    # 3. permutation inference for inno and ent
    say(f"\n3. 순열 추론 ({NPERM}회): 혁신·기업도시 표시를 같은 수의 다른 시군에 무작위로 줌 (후기 모형)")
    rng = np.random.default_rng(20261020)
    for v in ["inno", "ent"]:
        other = "ent" if v == "inno" else "inno"
        pool = d.index[(d[v] == 0) & (d[other] == 0)]
        nt = int(d[v].sum())
        for y, lab in YS.items():
            f = f"{y} ~ {SUPPLY} + {ctrl_post}"
            b = smf.ols(f, data=d).fit().params[v]
            g = d.copy()
            draws = []
            for _ in range(NPERM):
                g[v] = 0
                g.loc[rng.choice(pool, nt, replace=False), v] = 1
                draws.append(smf.ols(f, data=g).fit().params[v])
            draws = np.array(draws)
            p = float((np.abs(draws) >= abs(b)).mean())
            say(f"    {v:5s} {lab:14s} b = {b:+.4f}, 순열 p = {p:.3f} (위약 b 95% 범위 {np.percentile(draws, 2.5):+.4f} ~ "
                f"{np.percentile(draws, 97.5):+.4f})")
            rows.append(["permutation", y, v, "post", b, np.nan, p, len(d)])

    pd.DataFrame(rows, columns=["check", "y", "term", "period", "coef", "se", "p", "n"]).to_csv(
        os.path.join(OUT, "partA_ident_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "partA_ident.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
