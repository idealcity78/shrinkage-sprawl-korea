"""Industrial complexes in the non-capital regions: supply beyond demand (H0), and growth after designation.

1. Complex level. Each complex polygon (국토연구원 산업단지 기본정보: name, type, status, designation / construction
   start / completion year, designated area) is put on the 100 m grid. Per complex:
     urb99, urb09, urb19   mean urban share (large class) of its cells in the late 1990s, 2009, 2019
     ind22                 mean industrial share (middle class 2022)
     emp{y}, manuf{y}      employees and manufacturing employees (100 m employees x 1 km manufacturing share)
   joined by name to the KICOX status table (2026.06): sale rate of the industrial area, unsold area, firms that
   moved in and firms operating. Summaries by designation window, type and the 시군 group of supply_demand.py
   (감소 / 정체 / 성장, population 2000 -> 2019).
2. 시군 level. Does designating complexes bring growth later?
     y = growth 2010 -> 2024 of manufacturing employees, all employees, residents, households
     x = complex area designated 2006-2012 per km2 of 2009 urban land (ic_0612), 2001-2005 (ic_0105)
     controls: pre-trend of the same outcome 2000 -> 2005, log residents 2000, region dummies; HC1
   placebo: complexes designated 2016-2024 (ic_1624) on the same outcomes; the reverse question (growth 2000 -> 2005
   predicting designation 2006-2012) tells whether designation follows growth.

Output: outputs/partA/ic_complexes.csv, ic_unmet.txt, ic_unmet_models.csv
Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\ic_unmet.py   (add "models" to skip the grid step)
"""
import os
import re
import sys
import tempfile

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
for p in (CODE, os.path.join(CODE, "02_grid"), HERE):
    sys.path.insert(0, p)
import paths

sys.stdout.reconfigure(encoding="utf-8")
GRID = os.path.join(paths.WORK, "grid100")
OUT = os.path.join(paths.OUTPUTS, "partA")
IC = os.path.join(paths.L1, "ugm_national", "supply", "industrial_complex_tm.shp")
KICOX = os.path.join(paths.L1_SUPPLY, "한국산업단지공단_전국산업단지현황통계_{}_20260630.csv")
EMP_YEARS = [2000, 2005, 2010, 2015, 2019, 2024]
WINDOWS = [(0, 2000, "~2000"), (2001, 2005, "2001-05"), (2006, 2010, "2006-10"), (2011, 2015, "2011-15"),
           (2016, 2020, "2016-20"), (2021, 2030, "2021-")]
GROUPS = ["감소", "정체", "성장"]


def sgis(item, year, n, na):
    z = np.load(os.path.join(GRID, f"sgis_{item}.npz"))
    a = np.zeros(n, np.float64)
    v = z[f"y{year}_val"]
    a[z[f"y{year}_idx"]] = np.where(v < 0, na, v)
    return a


def complex_raster(x0, y0, nrow, ncol):
    import arcpy
    tmp = tempfile.mkdtemp(prefix="icid_")
    fc = os.path.join(arcpy.management.CreateFileGDB(tmp, "i.gdb")[0], "ic")
    arcpy.env.outputCoordinateSystem = None
    arcpy.env.extent = None
    arcpy.management.Project(IC, fc, arcpy.SpatialReference(5179))
    arcpy.management.AddField(fc, "cid", "LONG")
    attrs = []
    with arcpy.da.UpdateCursor(fc, ["code", "name", "type", "status", "appn_yr", "strwrk_yr", "compet_yr", "appn_ar",
                                    "SHAPE@AREA", "cid"]) as cur:
        for r in cur:
            attrs.append(dict(code=r[0], name=r[1], type=r[2], status=r[3], appn_yr=r[4], strwrk_yr=r[5],
                              compet_yr=r[6], appn_ar=r[7], poly_km2=r[8] / 1e6))
            cur.updateRow(list(r[:-1]) + [len(attrs)])
    arcpy.env.extent = arcpy.Extent(x0, y0, x0 + ncol * 100, y0 + nrow * 100)
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(5179)
    out = os.path.join(tmp, "c.tif")
    arcpy.conversion.PolygonToRaster(fc, "cid", out, "MAXIMUM_AREA", "", 100)
    a = arcpy.RasterToNumPyArray(out, arcpy.Point(x0, y0), ncol, nrow, nodata_to_value=0)
    arcpy.env.extent = None
    arcpy.env.outputCoordinateSystem = None
    t = pd.DataFrame(attrs)
    t.insert(0, "cid", np.arange(1, len(t) + 1))
    return a.astype(np.int32), t


def build():
    import sigun
    l99, l09, l19 = (np.load(os.path.join(GRID, f"l1_{y}.npz")) for y in (1999, 2009, 2019))
    l22 = np.load(os.path.join(GRID, "l2_2022.npz"))
    x0, y0 = int(l09["x0"]), int(l09["y0"])
    nrow, ncol = l09["urb"].shape
    n = nrow * ncol
    cid, t = complex_raster(x0, y0, nrow, ncol)
    sg, names, cap = sigun.raster(x0, y0, nrow, ncol)
    lab = cid.ravel().astype(np.int64)
    k = len(t) + 1
    by = lambda w: np.bincount(lab, weights=np.asarray(w, np.float64).ravel(), minlength=k)[1:]
    t["cells"] = by(np.ones(n))
    for nm, arr in [("urb99", l99["urb"]), ("urb09", l09["urb"]), ("urb19", l19["urb"]), ("ind22", l22["ind"])]:
        t[nm] = np.divide(by(arr), t.cells, out=np.full(len(t), np.nan), where=t.cells > 0)
    # 시군 = the 시군 holding most of the complex's cells
    m = lab > 0
    pair = pd.DataFrame({"cid": lab[m], "SG_ID": sg.ravel()[m]})
    top = pair.groupby(["cid", "SG_ID"]).size().reset_index(name="c").sort_values("c").groupby("cid").tail(1)
    t = t.merge(top[["cid", "SG_ID"]], on="cid", how="left")
    t["sigun"] = t.SG_ID.map(names)
    t["capital"] = t.SG_ID.isin(cap).astype(int)
    ind = np.load(os.path.join(GRID, "ind_share.npz"))
    rr, cc = np.meshgrid(ind["r1k"], ind["c1k"], indexing="ij")
    for y in EMP_YEARS:
        e = sgis("emp", y, n, 1.5)
        ms = np.nan_to_num(ind[f"y{y}_manuf"][rr, cc].ravel(), nan=0.0)
        t[f"emp{y}"], t[f"manuf{y}"] = by(e), by(e * ms)
    t.to_csv(os.path.join(OUT, "ic_complexes_grid.csv"), index=False, encoding="utf-8-sig")


def norm(s):
    s = re.sub(r"\(.*?\)|[①-⑳]|\s|·|ㆍ", "", str(s))
    for w in ("국가산업단지", "일반산업단지", "도시첨단산업단지", "농공단지", "산업단지", "지방산업단지"):
        s = s.replace(w, "")
    return s


def kicox():
    rows = []
    for kind in ("국가산업단지", "일반", "농공"):
        f = pd.read_csv(KICOX.format(kind), encoding="cp949")
        f.columns = [c.strip() for c in f.columns]
        rows.append(f)
    k = pd.concat(rows, ignore_index=True)
    k = k.rename(columns={"단지명": "kname", "시군": "k_sigun", "조성상태": "k_status", "지정면적(천제곱미터)": "k_area",
                          "산업시설구역_분양대상(천제곱미터)": "k_sale_target", "산업시설구역_분양(천제곱미터)": "k_sold",
                          "산업시설구역_미분양(천제곱미터)": "k_unsold", "입주업체(개)": "k_firms", "가동업체(개)": "k_oper"})
    for c in ("k_area", "k_sale_target", "k_sold", "k_unsold", "k_firms", "k_oper"):
        k[c] = pd.to_numeric(k[c].astype(str).str.replace(",", ""), errors="coerce")
    k["key"] = k.kname.map(norm)
    k = k.drop_duplicates(["key", "k_sigun"])
    return k


def complexes():
    t = pd.read_csv(os.path.join(OUT, "ic_complexes_grid.csv"))
    t["key"] = t.name.map(norm)
    k = kicox()
    by_key = k.groupby("key").filter(lambda g: len(g) == 1).set_index("key")
    t = t.join(by_key[["k_status", "k_area", "k_sale_target", "k_sold", "k_unsold", "k_firms", "k_oper"]], on="key")
    t["window"] = pd.cut(t.appn_yr.fillna(0), [w[0] - 0.5 for w in WINDOWS] + [2030.5], labels=[w[2] for w in WINDOWS])
    grp = pd.read_csv(os.path.join(OUT, "supply_demand_panel.csv")).groupby("SG_ID").group.first()
    t["group"] = t.SG_ID.map(grp)
    t["km2"] = t.appn_ar.fillna(t.poly_km2 * 1e6) / 1e6
    t.to_csv(os.path.join(OUT, "ic_complexes.csv"), index=False, encoding="utf-8-sig")
    return t


def stars(p):
    return "***" if p < .01 else "**" if p < .05 else "*" if p < .1 else ""


def fmt(m, v):
    return f"{m.params[v]:+.3f} ({m.bse[v]:.3f}){stars(m.pvalues[v])}"


def main():
    if "models" not in sys.argv[1:]:
        build()
    t = complexes()
    lines, rows = [], []

    def say(s=""):
        print(s)
        lines.append(s)

    nc = t[(t.capital == 0) & t.group.isin(GROUPS + ["광역시"])].copy()
    nc = nc[nc.group.isin(GROUPS)]
    say(f"비수도권 도 시군의 산업단지 {len(nc)}개, 지정 면적 {nc.km2.sum():,.0f} km2. "
        f"산업단지공단 현황과 이름으로 연결 {nc.k_sale_target.notna().sum()}개 ({nc.k_sale_target.notna().mean():.0%})")

    def summary(g):
        w = g.km2
        s = {"단지": len(g), "지정 km2": w.sum(),
             "2019 시가화 %": np.average(g.urb19.fillna(0), weights=w),
             "2022 공업용지 %": np.average(g.ind22.fillna(0), weights=w),
             "지정 전 시가화 %": np.average(g.urb99.fillna(0), weights=w)}
        kk = g.dropna(subset=["k_sale_target"])
        kk = kk[kk.k_sale_target > 0]
        s["분양률 %"] = kk.k_sold.sum() / kk.k_sale_target.sum() * 100 if len(kk) else np.nan
        s["미분양 km2"] = kk.k_unsold.sum() / 1000 if len(kk) else np.nan
        s["가동/입주 %"] = kk.k_oper.sum() / kk.k_firms.sum() * 100 if len(kk) and kk.k_firms.sum() else np.nan
        s["제조업 종사자/km2 2024"] = g.manuf2024.sum() / w.sum()
        s["제조업 종사자 증가 2010-24"] = (g.manuf2024 - g.manuf2010).sum()
        return pd.Series(s)

    say("\n1. 지정 시기별 (비수도권 도 시군; 면적 가중)")
    say(nc.groupby("window", observed=True).apply(summary).round(1).to_string())
    say("\n   시군 집단별, 2006년 이후 지정")
    say(nc[nc.appn_yr >= 2006].groupby("group").apply(summary).reindex(GROUPS).round(1).to_string())
    say("\n   시군 집단별, 2005년 이전 지정 (비교)")
    say(nc[(nc.appn_yr > 0) & (nc.appn_yr <= 2005)].groupby("group").apply(summary).reindex(GROUPS).round(1)
        .to_string())
    say("\n   유형별, 2006년 이후 지정")
    say(nc[nc.appn_yr >= 2006].groupby("type").apply(summary).round(1).to_string())

    # 2. 시군 level
    sp = pd.read_csv(os.path.join(OUT, "supply_demand_panel.csv"))
    lv = pd.read_csv(os.path.join(OUT, "supply_demand_levels.csv")).pivot_table(index="SG_ID", columns="year",
                                                                               values=["pop", "hh"])
    es = pd.read_csv(os.path.join(paths.OUTPUTS, "partB", "emp_sigun_year.csv")).pivot_table(
        index="SG_ID", columns="year", values=["emp", "manuf"])
    pa = pd.read_csv(os.path.join(OUT, "sigun_panel.csv"))[["SG_ID", "urb09", "land_km2"]]
    s = sp.groupby("SG_ID")[["sigun", "group", "region"]].first().join(pa.set_index("SG_ID"))
    s = s[s.group.isin(GROUPS)]
    for a, b, c in [(2001, 2005, "ic_0105"), (2006, 2012, "ic_0612"), (2016, 2024, "ic_1624"), (0, 2000, "ic_pre")]:
        x = t[(t.appn_yr >= max(a, 1)) & (t.appn_yr <= b)].groupby("SG_ID").km2.sum()
        s[c] = x.reindex(s.index).fillna(0) / s.urb09 * 100   # km2 per 100 km2 of 2009 urban land
    for v, src in [("manuf", es), ("emp", es), ("pop", lv), ("hh", lv)]:
        s[f"g_{v}"] = np.log(src[(v, 2024)] / src[(v, 2010)]).reindex(s.index) * 100
        s[f"pre_{v}"] = np.log(src[(v, 2005)] / src[(v, 2000)]).reindex(s.index) * 100
        s[f"g05_{v}"] = np.log(src[(v, 2015)] / src[(v, 2005)]).reindex(s.index) * 100
    s["lpop00"] = np.log(lv[("pop", 2000)].reindex(s.index))
    s = s.replace([np.inf, -np.inf], np.nan)
    say(f"\n2. 시군 단위 (비수도권 도 시군 {len(s)}): 산업단지 지정이 뒤의 성장을 부르는가")
    say("   x = 지정 면적 / 2009 시가지 면적 (%), y = 2010 -> 2024 로그 증가 (x100), 통제: 같은 y의 2000 -> 2005, "
        "log 인구 2000, 권역; HC1")
    say(f"   평균 ic_0612 {s.ic_0612.mean():.2f}% (지정 시군 {(s.ic_0612 > 0).sum()}), ic_1624 {s.ic_1624.mean():.2f}%")
    for v, lab in [("manuf", "제조업 종사자"), ("emp", "전체 종사자"), ("pop", "인구"), ("hh", "가구")]:
        g = s.dropna(subset=[f"g_{v}", f"pre_{v}"])
        m = smf.ols(f"g_{v} ~ ic_0612 + ic_0105 + ic_pre + pre_{v} + lpop00 + C(region)", data=g).fit(cov_type="HC1")
        mp = smf.ols(f"g_{v} ~ ic_1624 + ic_0612 + ic_0105 + ic_pre + pre_{v} + lpop00 + C(region)",
                     data=g).fit(cov_type="HC1")
        mq = smf.ols(f"g05_{v} ~ ic_1624 + ic_pre + pre_{v} + lpop00 + C(region)", data=g).fit(cov_type="HC1")
        say(f"   {lab:8s} 2006-12 지정 {fmt(m, 'ic_0612')}, 2001-05 {fmt(m, 'ic_0105')} | 위약: 2016-24 지정이 "
            f"2010-24 성장 {fmt(mp, 'ic_1624')}, 2005-15 성장 {fmt(mq, 'ic_1624')}")
        rows += [["growth", v, "ic_0612", m.params["ic_0612"], m.bse["ic_0612"], m.pvalues["ic_0612"], int(m.nobs)],
                 ["growth", v, "ic_0105", m.params["ic_0105"], m.bse["ic_0105"], m.pvalues["ic_0105"], int(m.nobs)],
                 ["placebo_1024", v, "ic_1624", mp.params["ic_1624"], mp.bse["ic_1624"], mp.pvalues["ic_1624"],
                  int(mp.nobs)],
                 ["placebo_0515", v, "ic_1624", mq.params["ic_1624"], mq.bse["ic_1624"], mq.pvalues["ic_1624"],
                  int(mq.nobs)]]
    say("\n   역방향: 2006-12 지정 면적 ~ 2000 -> 2005 성장 + log 인구 2000 + 권역 (지정이 성장을 따라가는가)")
    for v in ["manuf", "pop", "hh"]:
        g = s.dropna(subset=[f"pre_{v}"])
        m = smf.ols(f"ic_0612 ~ pre_{v} + lpop00 + C(region)", data=g).fit(cov_type="HC1")
        say(f"   pre_{v} {fmt(m, f'pre_{v}')}")
        rows.append(["reverse", v, f"pre_{v}", m.params[f"pre_{v}"], m.bse[f"pre_{v}"], m.pvalues[f"pre_{v}"],
                     int(m.nobs)])
    say("\n   지정 면적 대비 성과: 2006-12 지정 면적 1 km2당 2010 -> 2024 시군 제조업 종사자 증가 (계수 환산)")
    g = s.dropna(subset=["g_manuf", "pre_manuf"]).copy()
    g["d_manuf"] = (es[("manuf", 2024)] - es[("manuf", 2010)]).reindex(g.index)
    g["km2_0612"] = g.ic_0612 * g.urb09 / 100
    g["km2_0105"] = g.ic_0105 * g.urb09 / 100
    m = smf.ols("d_manuf ~ km2_0612 + km2_0105 + pre_manuf + lpop00 + C(region)", data=g).fit(cov_type="HC1")
    say(f"   제조업 종사자 증가 ~ 2006-12 지정 km2: {fmt(m, 'km2_0612')} 명/km2 "
        f"(참고: 2005년 이전 지정 단지의 2024년 제조업 종사자 밀도 "
        f"{nc[(nc.appn_yr > 0) & (nc.appn_yr <= 2005)].manuf2024.sum() / nc[(nc.appn_yr > 0) & (nc.appn_yr <= 2005)].km2.sum():,.0f} 명/km2)")
    rows.append(["jobs_per_km2", "manuf", "km2_0612", m.params["km2_0612"], m.bse["km2_0612"], m.pvalues["km2_0612"],
                 int(m.nobs)])
    s.to_csv(os.path.join(OUT, "ic_sigun.csv"), encoding="utf-8-sig")
    pd.DataFrame(rows, columns=["block", "y", "term", "coef", "se", "p", "n"]).to_csv(
        os.path.join(OUT, "ic_unmet_models.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "ic_unmet.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
