"""Yearly event study of new-city zones and old-core migration, 2001-2025 (MDIS 읍면동 moves).

Treated: 시군 whose innovation / enterprise city zone took in residents (김천, 나주, 서귀포, 완주, 원주, 음성, 전주,
진주, 진천, 충주). Onset = first year the zone's in-movers (from the rest of the 시군 and from outside) reach 25 % of
their 2013-2025 peak, read from the flows themselves. Controls: the other non-capital 시군 of the flows panel;
해남·영암·태안 (enterprise-city zones without residents) are dropped.

Outcomes per year: old-core flows per 1,000 old-core residents in 2005 and 시군 flows per 1,000 residents in 2005
(fixed pre-treatment denominators), as in flows_supply_panel.py:
  out_zone, out_new, out_rest, out_outside, out_capital, in_outside, net_old, sg_in, sg_out, sg_net
Moves inside one 읍면동 are not counted in any year.

Models
  event   y_st = a_s + g_{region,t} + sum_k b_k 1[t - onset_s = k] ; k = -8 (and earlier) ... +8 (and later), k = -1
          left out; errors clustered by 시군
  pooled  y_st = a_s + g_{region,t} + b post_st   (post = treated and t >= onset)
  permutation  the pooled b is re-estimated 1,000 times with the onsets given to 10 randomly drawn control 시군
               (real treated 시군 dropped); p = share of placebo |b| >= actual |b|
  by 시군     pooled b for each treated 시군 alone against all controls

Output: outputs/partB/zone_event.csv (b_k), zone_event_pooled.csv, zone_event_panel.csv, zone_event.txt
Run with ArcGIS Pro Python:  propy.bat code\\04_partB\\zone_event_study.py
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import paths
from flows_supply_panel import flow_panel

sys.stdout.reconfigure(encoding="utf-8")
OUT = os.path.join(paths.OUTPUTS, "partB")
YEARS = range(2001, 2026)
TREATED = ["김천시", "나주시", "서귀포시", "완주군", "원주시", "음성군", "전주시", "진주시", "진천군", "충주시"]
DROP = ["해남군", "영암군", "태안군"]
YS = ["out_zone", "out_new", "out_rest", "out_outside", "out_capital", "in_outside", "net_old", "sg_in", "sg_out",
      "sg_net"]
KMIN, KMAX = -8, 8
N_PERM = 1000


def stars(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


def onsets(f):
    """First year the zone's in-movers reach 25 % of their 2013-2025 peak, per treated 시군."""
    r = pd.read_csv(os.path.join(paths.OUTPUTS, "flows", "mdis_old_core_flows.csv"))
    z = pd.concat([r[(r.side == "out") & (r.other == "zone") & (r.part != "zone")],
                   r[(r.side == "in") & (r.part == "zone")]])
    t = z[z.year >= 2008].pivot_table(index="sigun", columns="year", values="pers", aggfunc="sum").fillna(0)
    on = {}
    for s in TREATED:
        row = t.loc[s]
        on[s] = int(row[row >= 0.25 * row.max()].index.min())
    return on, t


def fe_projector(df):
    """Residual-maker for 시군 + region x year dummies (rows in df order)."""
    X = pd.get_dummies(df[["SG_ID", "ry"]].astype(str), drop_first=False).values.astype(float)
    U, sv, _ = np.linalg.svd(X, full_matrices=False)  # the two sets of dummies overlap within each region
    Q = U[:, sv > sv.max() * 1e-10]
    return lambda v: v - Q @ (Q.T @ v)


def main():
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    sp = pd.read_csv(os.path.join(OUT, "supply_panel.csv"))
    sp = sp[(sp.defn == "new") & (sp.sigun != "세종시")]
    base = sp[sp.t0 == 2005].set_index("SG_ID")[["sigun", "region", "old_pop0", "pop0"]]
    f = flow_panel({str(y): [y] for y in YEARS}).rename(columns={"period": "year"})
    f["year"] = f.year.astype(int)
    df = f.merge(base, left_on="SG_ID", right_index=True)
    df = df[~df.sigun.isin(DROP) & (df.old_pop0 >= 1000)].copy()
    for y in YS:
        df[y] = df[y] / (df.pop0 if y.startswith("sg_") else df.old_pop0) * 1000
    on, zin = onsets(f)
    say("신도시 지구 전입자 (같은 시군 + 시군 밖, 명/년)")
    say(zin.loc[TREATED].round(0).astype(int).to_string())
    say("\n입주 시작 연도 (전입자가 최대치의 25%에 처음 도달): " + ", ".join(f"{s} {y}" for s, y in on.items()))
    df["onset"] = df.sigun.map(on)
    df["treated"] = df.onset.notna().astype(int)
    df["k"] = (df.year - df.onset).clip(KMIN, KMAX)
    df["post"] = ((df.treated == 1) & (df.year >= df.onset)).astype(int)
    df["ry"] = df.region + "_" + df.year.astype(str)
    df = df.sort_values(["SG_ID", "year"]).reset_index(drop=True)
    df.to_csv(os.path.join(OUT, "zone_event_panel.csv"), index=False, encoding="utf-8-sig")
    say(f"\n표본: 처치 시군 {df[df.treated == 1].SG_ID.nunique()}, 비교 시군 {df[df.treated == 0].SG_ID.nunique()}, "
        f"연도 {df.year.min()}-{df.year.max()}")

    # event study
    ks = [k for k in range(KMIN, KMAX + 1) if k != -1]
    for k in ks:
        df[f"e{k}".replace("-", "m")] = ((df.treated == 1) & (df.k == k)).astype(int)
    ev = " + ".join(f"e{k}".replace("-", "m") for k in ks)
    erows = []
    say("\n== 사건연구 b_k (기준 k = -1; 원도심 천 명당, sg_* 는 시군 천 명당)")
    tab = {}
    for y in YS:
        m = smf.ols(f"{y} ~ {ev} + C(SG_ID) + C(ry)", data=df).fit(cov_type="cluster",
                                                                   cov_kwds={"groups": df.SG_ID})
        col = {}
        for k in ks:
            v = f"e{k}".replace("-", "m")
            col[k] = f"{m.params[v]:+.1f}{stars(m.pvalues[v])}"
            erows.append([y, k, m.params[v], m.bse[v], m.pvalues[v]])
        tab[y] = col
    say(pd.DataFrame(tab).to_string())
    pd.DataFrame(erows, columns=["y", "k", "coef", "se", "p"]).to_csv(os.path.join(OUT, "zone_event.csv"),
                                                                       index=False, encoding="utf-8-sig")

    # pooled + permutation
    say(f"\n== 통합 DiD (입주 후 = 1) 와 순열 추론 ({N_PERM}회, 비교 시군 {len(TREATED)}곳에 입주 연도를 무작위 배정)")
    rng = np.random.default_rng(20261019)
    ctrl = df[df.treated == 0].reset_index(drop=True)
    resid_c = fe_projector(ctrl)
    ctrl_ids = ctrl.SG_ID.unique()
    onset_list = list(on.values())
    placebo_post = []
    for _ in range(N_PERM):
        pick = rng.choice(ctrl_ids, size=len(onset_list), replace=False)
        o = dict(zip(pick, rng.permutation(onset_list)))
        po = ctrl.SG_ID.map(o)
        placebo_post.append(resid_c(((po.notna()) & (ctrl.year >= po)).astype(float).values))
    prow = []
    for y in YS:
        m = smf.ols(f"{y} ~ post + C(SG_ID) + C(ry)", data=df).fit(cov_type="cluster",
                                                                   cov_kwds={"groups": df.SG_ID})
        b = m.params["post"]
        yr = resid_c(ctrl[y].values.astype(float))
        pb = np.array([(d @ yr) / (d @ d) for d in placebo_post])
        p_perm = float((np.abs(pb) >= abs(b)).mean())
        prow.append([y, b, m.bse["post"], m.pvalues["post"], p_perm, np.percentile(pb, 2.5), np.percentile(pb, 97.5)])
        say(f"   {y:12s} {b:+8.2f} (군집 SE {m.bse['post']:.2f}{stars(m.pvalues['post'])})  순열 p={p_perm:.3f}  "
            f"위약 95% 구간 [{np.percentile(pb, 2.5):+.2f}, {np.percentile(pb, 97.5):+.2f}]")
    pd.DataFrame(prow, columns=["y", "coef", "se", "p_cluster", "p_perm", "placebo_lo", "placebo_hi"]).to_csv(
        os.path.join(OUT, "zone_event_pooled.csv"), index=False, encoding="utf-8-sig")

    # by 시군
    say("\n== 시군별 통합 DiD (각 처치 시군 하나 + 비교 시군 전체)")
    by = {}
    for s in TREATED:
        g = df[(df.treated == 0) | (df.sigun == s)]
        col = {}
        for y in ["out_zone", "out_new", "out_outside", "in_outside", "net_old", "sg_net"]:
            m = smf.ols(f"{y} ~ post + C(SG_ID) + C(ry)", data=g).fit()
            col[y] = round(m.params["post"], 1)
        by[s] = col
    say(pd.DataFrame(by).T.to_string())
    say("   (시군 하나라 표준오차는 쓰지 않음; 크기와 방향만 비교)")

    with open(os.path.join(OUT, "zone_event.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
