"""Does sprawl operate together with decline? Sprawl and old-core decline across all 시군, 1999-2024.

Groups as in supply_demand.py (감소 / 정체 / 성장 by population 2000 -> 2019 for the 9 도; 광역시; 수도권 as the
high-demand benchmark). Per 시군, on the 100 m grid:
  land       urban km2 (large class, share-weighted) 1999, 2009, 2019; new urban cells (< 10 % -> >= 50 %) 1999-09 and
             2009-19; leapfrog share (no urban neighbour at the start); mean distance of new urban cells from the
             기성시가지 (km) and share more than 2 km away
  density    residents per urban km2 (2000/1999, 2010/2009, 2019/2019); urban m2 per resident
  housing    share of the housing units added 2010-2019 and 2015-2024 that lie outside the 기성시가지, and more than
             500 m from it
  old core   기성시가지 residents (L1 2009 urban >= 50 %, >= 5 units in 2000, outside the zones) 2000-2024; change and
             change relative to the 시군
Questions
  1. levels       sprawl indicators by group: do shrinking 시군 sprawl less, as the growth view of sprawl predicts?
  2. elasticity   new urban rate and urban m2 per resident on population growth, all 시군: is there sprawl at zero or
                  negative growth (intercept), and does the slope differ for shrinking 시군?
  3. coexistence  old-core change on sprawl (new urban rate, share of new housing outside the old core) given
                  population growth, by group; count of 시군 that both expand and empty their old core
Output: outputs/partA/shrink_sprawl_sigun.csv, shrink_sprawl.txt, shrink_sprawl_models.csv
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\shrink_sprawl.py   (add "models" to skip the grid step)
"""
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
for p in (CODE, os.path.join(CODE, "02_grid"), HERE):
    sys.path.insert(0, p)
import paths

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partA")
ORDER = ["감소", "정체", "성장", "광역시", "수도권"]
NA = 2.5


def sgis(item, year, shape, na=NA):
    z = np.load(os.path.join(GRID, f"sgis_{item}.npz"))
    a = np.zeros(shape[0] * shape[1], np.float32)
    v = z[f"y{year}_val"]
    a[z[f"y{year}_idx"]] = np.where(v < 0, na, v)
    return a.reshape(shape)


def build():
    import sigun
    from scipy import ndimage
    l = {y: np.load(os.path.join(GRID, f"l1_{y}.npz")) for y in (1999, 2009, 2019)}
    x0, y0 = int(l[2009]["x0"]), int(l[2009]["y0"])
    shape = l[2009]["urb"].shape
    u = {y: l[y]["urb"].astype(np.int16) for y in l}
    sg, names, cap = sigun.raster(x0, y0, *shape)
    zone = np.load(os.path.join(GRID, "newcity_zone.npz"))["zone"] > 0
    h00 = sgis("house", 2000, shape, na=0)
    old = (u[2009] >= 50) & (h00 >= 5) & ~zone
    dist = ndimage.distance_transform_edt(~old) * 0.1          # km from the 기성시가지
    lab = sg.ravel().astype(np.int64)
    k = int(sg.max()) + 1
    by = lambda w: np.bincount(lab, weights=np.asarray(w, np.float64).ravel(), minlength=k)
    r = {"SG_ID": np.arange(k)}
    for y in u:
        r[f"urb{y % 100:02d}"] = by(u[y]) / 100 * 0.01
    for a, b, tag in [(1999, 2009, "pre"), (2009, 2019, "post")]:
        new = (u[a] < 10) & (u[b] >= 50)
        near = ndimage.binary_dilation(u[a] >= 50, structure=np.ones((3, 3), bool))
        r[f"new_{tag}"] = by(new) * 0.01
        r[f"leap_{tag}"] = by(new & ~near) * 0.01
        r[f"dist_{tag}"] = by(dist * new)                         # sum of km, divided later
        r[f"far_{tag}"] = by(new & (dist > 2)) * 0.01
    for y in (2000, 2005, 2010, 2015, 2019, 2024):
        p = sgis("pop", y, shape)
        r[f"pop{y}"] = by(p)
        r[f"old{y}"] = by(p * old)
    h = {y: sgis("house", y, shape, na=0) for y in (2010, 2015, 2019, 2024)}
    for a, b in [(2010, 2019), (2015, 2024)]:
        dh = np.clip(h[b] - h[a], 0, None)
        r[f"dh{a % 100:02d}{b % 100:02d}"] = by(dh)
        r[f"dh_out{a % 100:02d}{b % 100:02d}"] = by(dh * ~old)
        r[f"dh_far{a % 100:02d}{b % 100:02d}"] = by(dh * (dist > 0.5))
    t = pd.DataFrame(r)
    t = t[t.SG_ID > 0]
    t["sigun"] = t.SG_ID.map(names)
    t.to_csv(os.path.join(OUT, "shrink_sprawl_grid.csv"), index=False, encoding="utf-8-sig")


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def fmt(m, v):
    return f"{m.params[v]:+.3f} ({m.bse[v]:.3f}){stars(m.pvalues[v])}"


def all_terms(block, y, m, lp, mean_lp):
    """Every term of an elasticity model, plus the prediction at zero growth and mean log population (non-capital,
    N = 0) with its delta-method standard error: a + delta * mean(ln P)."""
    cap = "C(group == '수도권')[T.True]"
    out = [[block, y, v, m.params[v], m.bse[v], m.pvalues[v], int(m.nobs)] for v in ("Intercept", "gp", "gp:neg", "neg", lp, cap)]
    V = m.cov_params()
    pred = m.params["Intercept"] + m.params[lp] * mean_lp
    se = float(np.sqrt(V.at["Intercept", "Intercept"] + mean_lp ** 2 * V.at[lp, lp] + 2 * mean_lp * V.at["Intercept", lp]))
    p = 2 * (1 - norm.cdf(abs(pred / se)))
    return out + [[block, y, "pred_zero_growth", pred, se, p, int(m.nobs)]]


def main():
    if "models" not in sys.argv[1:]:
        build()
    t = pd.read_csv(os.path.join(OUT, "shrink_sprawl_grid.csv"))
    sp = pd.read_csv(os.path.join(OUT, "supply_demand_panel.csv"))
    t = t.merge(sp.groupby("SG_ID")[["group", "region"]].first().reset_index(), on="SG_ID")
    t = t[(t.urb09 > 0.5) & (t.pop2000 > 0)].copy()
    for tag, a, b, pa, pb in [("pre", "urb99", "urb09", "pop2000", "pop2010"),
                              ("post", "urb09", "urb19", "pop2010", "pop2019")]:
        t[f"new_rate_{tag}"] = t[f"new_{tag}"] / t[a] * 100
        t[f"leap_share_{tag}"] = t[f"leap_{tag}"] / t[f"new_{tag}"] * 100
        t[f"dist_{tag}"] = t[f"dist_{tag}"] / (t[f"new_{tag}"] * 100)
        t[f"far_share_{tag}"] = t[f"far_{tag}"] / t[f"new_{tag}"] * 100
        t[f"g_pop_{tag}"] = (t[pb] / t[pa] - 1) * 100
        t[f"g_urb_{tag}"] = (t[b] / t[a] - 1) * 100
        t[f"d_lpcu_{tag}"] = np.log((t[b] / t[pb]) / (t[a] / t[pa])) * 100
        t[f"dens0_{tag}"], t[f"dens1_{tag}"] = t[pa] / t[a], t[pb] / t[b]
    # population 2000-2010 is census, 2015- register census: changes across 2010 -> 2015 carry a level break of about
    # +4-6 % in every group, so population changes are taken within one method only (2000-10, 2015-24)
    t["g_pop_0010"] = (t.pop2010 / t.pop2000 - 1) * 100
    t["g_pop_1524"] = (t.pop2024 / t.pop2015 - 1) * 100
    t["g_old_0010"] = (t.old2010 / t.old2000 - 1) * 100
    t["g_old_1524"] = (t.old2024 / t.old2015 - 1) * 100
    t["g_old_1019"] = (t.old2019 / t.old2010 - 1) * 100
    t["g_old_1924"] = (t.old2024 / t.old2019 - 1) * 100
    t["g_pop_1924"] = (t.pop2024 / t.pop2019 - 1) * 100
    t["rel_old_1019"] = t.g_old_1019 - t.g_pop_post
    t["out_share_1019"] = t.dh_out1019 / t.dh1019 * 100
    t["far_house_1019"] = t.dh_far1019 / t.dh1019 * 100
    t["out_share_1524"] = t.dh_out1524 / t.dh1524 * 100
    t["shrink"] = (t.g_pop_1524 < 0).astype(int)
    t["lpop10"] = np.log(t.pop2010)
    t = t.replace([np.inf, -np.inf], np.nan)
    t.to_csv(os.path.join(OUT, "shrink_sprawl_sigun.csv"), index=False, encoding="utf-8-sig")
    lines, rows = [], []

    def say(s=""):
        print(s)
        lines.append(s)

    n = t.groupby("group").size().reindex(ORDER)
    say("시군 집단: " + ", ".join(f"{g} {v}" for g, v in n.items()))
    say("\n1. 확산 지표, 집단 중앙값 (후기 2009-2019; 괄호 안 전기 1999-2009)")
    cols = {"시가지 증가 %": "g_urb", "신규 시가지/기초 시가지 %": "new_rate",
            "비연속 비율 %": "leap_share", "기성시가지에서 평균 거리 km": "dist",
            "2km 넘는 신규 비율 %": "far_share"}
    tab = {}
    for lab, c in cols.items():
        post = t.groupby("group")[f"{c}_post"].median()
        pre = t.groupby("group")[f"{c}_pre"].median()
        tab[lab] = [f"{a:.1f} ({b:.1f})" for a, b in zip(post.reindex(ORDER), pre.reindex(ORDER))]
    say(pd.DataFrame(tab, index=ORDER).T.to_string())
    say("   인구 변화 (중앙값, %): 2000-10 센서스 " + ", ".join(f"{k} {v:.1f}" for k, v in
        t.groupby("group").g_pop_0010.median().reindex(ORDER).items()) + " / 2015-24 등록센서스 " + ", ".join(
        f"{k} {v:.1f}" for k, v in t.groupby("group").g_pop_1524.median().reindex(ORDER).items()))
    say("   1인당 시가지 로그변화 x100 (중앙값, 1999-2009 시가지 / 2000-2010 인구): " + ", ".join(
        f"{k} {v:.1f}" for k, v in t.groupby("group").d_lpcu_pre.median().reindex(ORDER).items()))
    g = t.groupby("group")
    say("\n   집단 합계: 시가지 밀도 (인구 / 시가지 km2)")
    say(pd.DataFrame({"2000/1999": g.pop2000.sum() / g.urb99.sum(), "2010/2009": g.pop2010.sum() / g.urb09.sum(),
                      "2019/2019 (등록)": g.pop2019.sum() / g.urb19.sum()}).reindex(ORDER).round(0).to_string())
    say("   (2010 -> 2019 밀도 변화에는 센서스 -> 등록센서스 단절(인구 +4~6%)이 들어 있어 실제 밀도 하락은 더 큼)")
    say("\n   새 주택이 기성시가지 밖에 지어진 비율 (집단 합계, %) 와 기성시가지 인구 변화 (%)")
    say(pd.DataFrame({"밖 2010-19": g.dh_out1019.sum() / g.dh1019.sum() * 100,
                      "500m 밖 2010-19": g.dh_far1019.sum() / g.dh1019.sum() * 100,
                      "밖 2015-24": g.dh_out1524.sum() / g.dh1524.sum() * 100,
                      "기성시가지 2000-10": (g.old2010.sum() / g.old2000.sum() - 1) * 100,
                      "시군 2000-10": (g.pop2010.sum() / g.pop2000.sum() - 1) * 100,
                      "기성시가지 2015-24": (g.old2024.sum() / g.old2015.sum() - 1) * 100,
                      "시군 2015-24": (g.pop2024.sum() / g.pop2015.sum() - 1) * 100}).reindex(ORDER).round(1)
        .to_string())

    say("\n2. 확산의 인구 성장 탄력성 (전 시군, HC1). 성장 관점: 확산 = 인구 증가에 비례 → 인구 증가 0이면 확산 0")
    say("   전기: 토지 1999-09, 인구 2000-10 (모두 센서스). 후기: 토지 2009-19, 인구 2015-24 (등록센서스, 시점 근사)")
    for tag, lp, gpop in [("pre", "lpop10", "g_pop_0010"), ("post", "lpop10", "g_pop_1524")]:
        say(f"   {'후기 2009-19' if tag == 'post' else '전기 1999-09'}")
        for y in ("new_rate", "leap_share") + (("d_lpcu",) if tag == "pre" else ()):
            g_ = t.dropna(subset=[f"{y}_{tag}", gpop])
            g_ = g_.assign(gp=g_[gpop], neg=(g_[gpop] < 0).astype(int))
            m = smf.ols(f"{y}_{tag} ~ gp + neg + gp:neg + {lp} + C(group == '수도권')", data=g_).fit(cov_type="HC1")
            say(f"     {y:10s} 상수(인구 증가 0) {m.params['Intercept'] + m.params[lp] * g_[lp].mean():+.2f}, 인구 증가 1%p "
                f"{fmt(m, 'gp')}, 감소 시군 기울기 차이 {fmt(m, 'gp:neg')}, 감소 시군 절편 차이 {fmt(m, 'neg')}")
            rows += [["elasticity_" + tag, y, v, m.params[v], m.bse[v], m.pvalues[v], int(m.nobs)]
                     for v in ("gp", "neg", "gp:neg")]
            rows += all_terms("elasticity_full_" + tag, y, m, lp, g_[lp].mean())
    say("   2015-24 인구가 준 시군의 2009-19 신규 시가지 비율 중앙값 "
        f"{t[t.shrink == 1].new_rate_post.median():.1f}% (시군 {t.shrink.sum()}), 그중 시가지가 늘어난 시군 "
        f"{(t[t.shrink == 1].g_urb_post > 0).mean() * 100:.0f}%"
        f"; 2000-10 인구가 준 시군 {(t.g_pop_0010 < 0).sum()}의 1999-09 시가지 증가 비율 "
        f"{(t[t.g_pop_0010 < 0].g_urb_pre > 0).mean() * 100:.0f}%, 신규 시가지 비율 중앙값 "
        f"{t[t.g_pop_0010 < 0].new_rate_pre.median():.1f}%")

    say("\n3. 확산과 원도심 쇠퇴의 결합: 기성시가지 인구 변화 (%) ~ 확산 + 시군 인구 변화 + log 인구 + 권역, HC1")
    say("   (가) 센서스 창: 기성시가지 2000-10 ~ 신규 시가지 1999-09 / (나) 등록센서스 창: 기성시가지 2015-24 ~ 새 주택 위치 2015-24")
    nm = t[t.group.isin(["감소", "정체", "성장"])]
    for x, yv, gp in [("new_rate_pre", "g_old_0010", "g_pop_0010"), ("leap_share_pre", "g_old_0010", "g_pop_0010"),
                      ("new_rate_post", "g_old_1524", "g_pop_1524"), ("out_share_1524", "g_old_1524", "g_pop_1524")]:
        for lab, g_ in [("비수도권 도 시군", nm), ("감소 시군", nm[nm.group == "감소"]),
                        ("성장·정체 시군", nm[nm.group != "감소"]), ("수도권·광역시", t[t.group.isin(["수도권", "광역시"])])]:
            g_ = g_.dropna(subset=[x, yv, gp])
            reg = " + C(region)" if lab != "수도권·광역시" else ""
            m = smf.ols(f"{yv} ~ {x} + {gp} + lpop10{reg}", data=g_).fit(cov_type="HC1")
            say(f"   {yv} ~ {x:15s} {lab:10s} (n={int(m.nobs)}): {fmt(m, x)}")
            rows.append(["coexist", x, lab, m.params[x], m.bse[x], m.pvalues[x], int(m.nobs)])
            rows += [["coexist_full", x, lab + "|" + v, m.params[v], m.bse[v], m.pvalues[v], int(m.nobs)]
                     for v in ("Intercept", x, gp, "lpop10")]
    say("\n   시가지는 늘고 기성시가지 인구는 준 시군 비율 (%), 그중 시군 인구도 준 시군 (%)")
    tb = {}
    for lab, ex, em, pdn in [("1999-2010", "g_urb_pre", "g_old_0010", "g_pop_0010"),
                             ("2009-24", "g_urb_post", "g_old_1524", "g_pop_1524")]:
        f1 = (t[ex] > 0) & (t[em] < 0)
        tb[f"확산+원도심 감소 {lab}"] = f1.groupby(t.group).mean() * 100
        tb[f"+인구 감소 {lab}"] = (f1 & (t[pdn] < 0)).groupby(t.group).mean() * 100
    say(pd.DataFrame(tb).reindex(ORDER).round(0).to_string())

    # 4. the same with the resident registration series (regpop.py), which has no method break
    rp = pd.read_csv(os.path.join(OUT, "regpop_sigun.csv")).pivot(index="sigun", columns="year", values="regpop")
    for y in (2000, 2009, 2010, 2015, 2019, 2024):
        t[f"rp{y}"] = t.sigun.map(rp[y])
    t["g_rp_0010"] = (t.rp2010 / t.rp2000 - 1) * 100
    t["g_rp_0919"] = (t.rp2019 / t.rp2009 - 1) * 100
    t["g_rp_0019"] = (t.rp2019 / t.rp2000 - 1) * 100
    t["d_lpcu_rp_post"] = np.log((t.urb19 / t.rp2019) / (t.urb09 / t.rp2009)) * 100
    t["d_lpcu_rp_pre"] = np.log((t.urb09 / t.rp2010) / (t.urb99 / t.rp2000)) * 100
    say("\n4. 주민등록인구(KOSIS, 조사 방식 단절 없음)로 다시 잰 결과")
    say("   인구 변화 중앙값 (%): 2000-10 " + ", ".join(f"{k} {v:.1f}" for k, v in
        t.groupby("group").g_rp_0010.median().reindex(ORDER).items()) + " / 2009-19 " + ", ".join(
        f"{k} {v:.1f}" for k, v in t.groupby("group").g_rp_0919.median().reindex(ORDER).items()))
    say("   1인당 시가지 로그변화 x100 중앙값: 1999-2009 " + ", ".join(f"{k} {v:.1f}" for k, v in
        t.groupby("group").d_lpcu_rp_pre.median().reindex(ORDER).items()) + " / 2009-2019 " + ", ".join(
        f"{k} {v:.1f}" for k, v in t.groupby("group").d_lpcu_rp_post.median().reindex(ORDER).items()))
    g = t.groupby("group")
    say("   시가지 밀도 (주민등록인구 / 시가지 km2, 1999·2000 / 2009 / 2019): " + "; ".join(
        f"{k} {a:,.0f} -> {b:,.0f} -> {c:,.0f}" for k, a, b, c in zip(
            ORDER, (g.rp2000.sum() / g.urb99.sum()).reindex(ORDER), (g.rp2009.sum() / g.urb09.sum()).reindex(ORDER),
            (g.rp2019.sum() / g.urb19.sum()).reindex(ORDER))))
    dn = t[t.g_rp_0919 < 0]
    say(f"   2009-19 주민등록인구가 준 시군 {len(dn)}: 시가지가 늘어난 시군 {(dn.g_urb_post > 0).mean() * 100:.0f}%, "
        f"신규 시가지 비율 중앙값 {dn.new_rate_post.median():.1f}%, 1인당 시가지 로그변화 중앙값 "
        f"{dn.d_lpcu_rp_post.median():.1f}")
    nm4 = t[t.group.isin(["감소", "정체", "성장"])]
    dn = nm4[nm4.g_rp_0919 < 0]
    say(f"   비수도권 도 시군 {len(nm4)} 가운데 2009-19 주민등록인구가 준 시군 {len(dn)}, 그중 시가지가 늘어난 시군 "
        f"{(dn.g_urb_post > 0).sum()} (Part A 1차의 격자 2010-19 기준 '11개 중 10개'를 대신함)")
    say("   확산의 인구 성장 탄력성, 후기 (토지 2009-19, 주민등록인구 2009-19):")
    for y in ("new_rate", "d_lpcu_rp", "leap_share"):
        yy = f"{y}_post"
        g_ = t.dropna(subset=[yy, "g_rp_0919"])
        g_ = g_.assign(gp=g_.g_rp_0919, neg=(g_.g_rp_0919 < 0).astype(int))
        m = smf.ols(f"{yy} ~ gp + neg + gp:neg + lpop10 + C(group == '수도권')", data=g_).fit(cov_type="HC1")
        say(f"     {y:10s} 상수(인구 증가 0) {m.params['Intercept'] + m.params['lpop10'] * g_.lpop10.mean():+.2f}, "
            f"인구 증가 1%p {fmt(m, 'gp')}, 감소 시군 기울기 차이 {fmt(m, 'gp:neg')}, 감소 시군 절편 차이 {fmt(m, 'neg')}")
        rows += [["elasticity_rp_post", y, v, m.params[v], m.bse[v], m.pvalues[v], int(m.nobs)]
                 for v in ("gp", "neg", "gp:neg")]
        rows += all_terms("elasticity_full_rp_post", y, m, "lpop10", g_.lpop10.mean())
    t["grp_rp"] = np.where(t.group.isin(["광역시", "수도권"]), t.group,
                           np.where(t.g_rp_0019 < -5, "감소", np.where(t.g_rp_0019 <= 5, "정체", "성장")))
    say("   집단 분류 비교 (행: 격자 인구 2000-19 기준, 열: 주민등록인구 2000-19 기준)")
    say(pd.crosstab(t.group, t.grp_rp).reindex(index=ORDER, columns=ORDER, fill_value=0).to_string())
    f1 = (t.g_urb_post > 0) & (t.g_rp_0919 < 0)
    say("   2009-19 시가지 증가 + 주민등록인구 감소 시군 비율 (%): " + ", ".join(
        f"{k} {v:.0f}" for k, v in (f1.groupby(t.group).mean() * 100).reindex(ORDER).items()))
    t.to_csv(os.path.join(OUT, "shrink_sprawl_sigun.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(rows, columns=["block", "y", "term", "coef", "se", "p", "n"]).to_csv(
        os.path.join(OUT, "shrink_sprawl_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "shrink_sprawl.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
