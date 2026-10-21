"""Upper bound on old-core moves the MDIS data cannot see: moves inside one 읍면동 (old core -> new housing next door).

MDIS drops moves that start and end in the same 읍면동, so a resident of the old core who moves into a new
apartment block in the same 동 is not counted in out_new or net_old. Where new housing sits next to the old core,
net_old is then too favourable, which could make the positive coefficient of near supply (s_b1) an artefact.

For each 시군 S and period (t0, t1) of the supply panel, the grid population accounts give
  dOld = old-core residents at t1 - at t0
  dNew = residents at t1 - at t0 on the cells that are new residential land at t1 (outside the zones)
and the observed moves (flows_old_core_mdis.py, annual means x years in the period) give net_old and net_new.
The residuals
  R_old = dOld - n * net_old   = natural change(old) - H + other unseen moves + count error
  R_new = dNew - n * net_new   = natural change(new) + H + unseen moves from the rest of the 동 + count error
both carry the hidden flow H (old core -> new, same 동). With natural change >= 0 on new land (young households)
and <= 0 in the old core (ageing), both -R_old and R_new are upper bounds on H, so
  H_ub   = min(max(R_new, 0), max(-R_old, 0))
  H_ub2  = the same with R_new limited to new land in 2020 행정동 that also hold old core (>= 10 % of residents
           at t0); H cannot arise in a 동 without old core.
net_old is then lowered by H / n and the supply models of flows_supply_panel.py are run again.
The grid counts for 2000-2010 are census counts and the moves are registrations, so the residuals also carry the
census-register gap; the bound is loose there and the 2015-19 / 2019-24 (register census) periods are shown apart.

Output: outputs/partB/same_dong_bound.csv (시군 x 기간), same_dong_bound.txt
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\same_dong_bound.py
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
for p in (CODE, os.path.join(CODE, "02_grid"), os.path.join(CODE, "05_flows"), HERE):
    sys.path.insert(0, p)
import paths
import sigun
from dong_class import dong_raster
from flows_supply_panel import MDIS_YEARS, S, flow_panel, stars
from supply_panel import sgis

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partB")
FLOWS = os.path.join(paths.OUTPUTS, "flows")
PERIODS = [(2000, 2005), (2005, 2010), (2015, 2019), (2019, 2024)]
OLD_DONG = 0.10
TERMS = ["s_old", "s_zone", "s_b1", "s_b2", "s_b3", "s_b4"]


def grid_accounts():
    """Per 시군 and period: dOld, dNew, dNew in 동 with old core."""
    a = np.load(os.path.join(GRID, "l1_2009.npz"))
    x0, y0 = int(a["x0"]), int(a["y0"])
    shape = a["urb"].shape
    sg, names, cap = sigun.raster(x0, y0, *shape)
    did, _ = dong_raster(x0, y0, *shape)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    h00 = sgis("house", 2000, shape, na=0)
    old = (a["urb"] >= 50) & (h00 >= 5) & ~zone
    lab = sg.ravel().astype(np.int64)
    k = int(sg.max()) + 1
    dl = did.ravel().astype(np.int64)
    kd = int(did.max()) + 1
    by = lambda w: np.bincount(lab, weights=w.ravel().astype(np.float64), minlength=k)
    pop = {y: sgis("pop", y, shape) for y in sorted({y for p in PERIODS for y in p})}
    rows = []
    for t0, t1 in PERIODS:
        new = (h00 < 5) & (sgis("house", t1, shape, na=0) >= 5) & ~zone
        p0, p1 = pop[t0], pop[t1]
        dpop = np.bincount(dl, weights=p0.ravel().astype(np.float64), minlength=kd)
        dold = np.bincount(dl, weights=(p0 * old).ravel().astype(np.float64), minlength=kd)
        mixed = (np.divide(dold, dpop, out=np.zeros(kd), where=dpop > 0) >= OLD_DONG)[dl].reshape(shape) & (did > 0)
        dn = (p1 - p0) * new
        r = pd.DataFrame({"old0": by(p0 * old), "old1": by(p1 * old), "new0": by(p0 * new), "new1": by(p1 * new),
                          "dnew_mixed": by(dn * mixed)})
        r["SG_ID"] = np.arange(k)
        r["period"] = f"{t0}-{t1}"
        r["n"] = t1 - t0
        rows.append(r[(r.SG_ID > 0) & ~r.SG_ID.isin(cap)])
    g = pd.concat(rows, ignore_index=True)
    g["sigun"] = g.SG_ID.map(names)
    return g


def new_flows():
    """Observed net moves into the new-land part of each 시군 per period (annual means)."""
    r = pd.read_csv(os.path.join(FLOWS, "mdis_old_core_flows.csv"))
    rows = []
    for per, yrs in MDIS_YEARS.items():
        g = r[r.year.isin(yrs)]
        out = g[g.side == "out"]
        inn = (out[(out.other == "new") & (out.part != "new")].groupby("SG_ID").pers.sum()
               .add(g[(g.side == "in") & (g.part == "new")].groupby("SG_ID").pers.sum(), fill_value=0))
        outn = out[(out.part == "new") & (out.other != "new")].groupby("SG_ID").pers.sum()
        rows.append(pd.DataFrame({"net_new": inn.sub(outn, fill_value=0) / len(yrs)}).assign(period=per))
    return pd.concat(rows).reset_index().rename(columns={"index": "SG_ID"})


def main():
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    g = grid_accounts()
    f = flow_panel()[["SG_ID", "period", "net_old", "out_new"]].merge(new_flows(), on=["SG_ID", "period"], how="left")
    d = g.merge(f, on=["SG_ID", "period"], how="inner")
    d["net_new"] = d.net_new.fillna(0)
    d["r_old"] = d.old1 - d.old0 - d.n * d.net_old
    d["r_new"] = d.new1 - d.new0 - d.n * d.net_new
    share = np.where(d.new1 - d.new0 > 0, (d.dnew_mixed / (d.new1 - d.new0)).clip(0, 1), 0)
    d["h_ub"] = np.minimum(d.r_new.clip(lower=0), (-d.r_old).clip(lower=0))
    d["h_ub2"] = np.minimum((d.r_new * share).clip(lower=0), (-d.r_old).clip(lower=0))
    d.to_csv(os.path.join(OUT, "same_dong_bound.csv"), index=False, encoding="utf-8-sig")

    say("같은 동 안 이동(원도심 -> 바로 옆 신규 주거지)의 상한 추정")
    say("R_old = 원도심 인구 변화 - 관측 순이동, R_new = 신규 주거지 인구 변화 - 관측 순이동 (기간 합, 명)")
    say("H_ub = min(R_new+, -R_old+);  H_ub2 = R_new 를 원도심이 있는 동(2020 행정동, 원도심 인구 10% 이상)으로 한정\n")
    t = d.groupby("period")[["old0", "old1", "new0", "new1", "net_old", "net_new", "r_old", "r_new", "h_ub",
                             "h_ub2"]].sum()
    t[["net_old", "net_new"]] = t[["net_old", "net_new"]].mul(d.groupby("period").n.first(), axis=0)
    say("기간 합 (비수도권 8개 도 시군)")
    say(t.round(0).astype(int).to_string())
    say()
    t2 = pd.DataFrame({"관측 net_old(연, 천명당)": t.net_old / t.old0 * 1000 / d.groupby("period").n.first(),
                       "H_ub(연, 천명당)": t.h_ub / t.old0 * 1000 / d.groupby("period").n.first(),
                       "H_ub2(연, 천명당)": t.h_ub2 / t.old0 * 1000 / d.groupby("period").n.first(),
                       "H_ub / 관측 원도심->신규": t.h_ub / (d.groupby("period").apply(lambda x: (x.out_new * x.n).sum()))})
    say(t2.round(2).to_string())

    sp = pd.read_csv(os.path.join(OUT, "supply_panel.csv"))
    sp = sp[(sp.defn == "new") & (sp.sigun != "세종시")]
    df = sp.merge(d.drop(columns=["sigun"]), on=["SG_ID", "period"], how="inner")
    k = 1000 / df.old_pop0
    df["y_net"] = df.net_old * k
    df["y_net_ub"] = (df.net_old - df.h_ub / df.n) * k
    df["y_net_ub2"] = (df.net_old - df.h_ub2 / df.n) * k
    df["y_out_new"] = df.out_new * k
    df["y_out_new_ub"] = (df.out_new + df.h_ub / df.n) * k
    df["y_h_ub"] = df.h_ub / df.n * k
    ys = {"y_net": "net_old 관측", "y_net_ub2": "net_old - H_ub2", "y_net_ub": "net_old - H_ub",
          "y_h_ub": "H_ub 자체", "y_out_new": "out_new 관측", "y_out_new_ub": "out_new + H_ub"}

    def table(g, title):
        say(f"\n{title}: 시군 {g.SG_ID.nunique()}, 시군-기간 {len(g)}")
        tab = {}
        for y, lab in ys.items():
            m = smf.ols(f"{y} ~ {S} + C(SG_ID) + C(rp)", data=g).fit(cov_type="cluster",
                                                                     cov_kwds={"groups": g.SG_ID})
            tab[lab] = {v: f"{m.params[v]:+.2f}{stars(m.pvalues[v])} ({m.bse[v]:.2f})" for v in TERMS}
        say(pd.DataFrame(tab).T.to_string())

    say("\n공급 모형 다시 추정 (flows_supply_panel.py와 같은 모형: 시군 FE + 권역x기간 FE, 시군 군집)")
    say("단위: 원도심 인구 천 명당 연간 이동자. 계수 = 공급 1%p/년")
    table(df, "전 기간")
    table(df[df.t0 >= 2015], "등록센서스 기간만 (2015-19, 2019-24)")

    zs = df[df.s_zone > 0].groupby("sigun")[["y_net", "y_h_ub", "y_net_ub"]].mean()
    say("\n혁신·기업도시 공급이 있는 시군-기간: 평균 (천 명당 연)")
    say(zs.round(1).to_string())
    with open(os.path.join(OUT, "same_dong_bound.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
