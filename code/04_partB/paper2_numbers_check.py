"""Second-pass number check for docs/paper2_draft.md: re-read every value from the output files and compare with the draft.

Writes outputs/paper2/numbers_check_pass2.csv; docs/paper2_numbers_check.md is built from it.
Run with ArcGIS Pro Python:  propy.bat code\04_partB\paper2_numbers_check.py
"""
import io, math, os, re, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
R = paths.DATA.replace("\\", "/").rstrip("/") + "/"
O = R + "outputs/"
draft = open(os.path.join(paths.REPO, "docs", "paper2_draft.md"), encoding="utf-8").read()


def lines(p):
    return open(O + p, encoding="utf-8").read().splitlines()


def row(p, header, label, start=0):
    """tokens of the first line starting with `label` after the first line containing `header`."""
    L = lines(p)
    i = next(k for k, l in enumerate(L) if header in l and k >= start)
    for l in L[i + 1:]:
        if l.strip().startswith(label):
            return l.split()
    raise KeyError((p, header, label))


def num(t):
    return float(re.sub(r"[*,()‰%]", "", t))


checks = []  # (id, claim, draft_value, source, reread_value)


def add(cid, claim, draft_val, source, reread):
    checks.append((cid, claim, draft_val, source, reread))


# ---------- Table 1 / data ----------
chk = pd.read_csv(O + "flows/mdis_check.csv")
add(1, "movers per year min (millions)", "6.1", "outputs/flows/mdis_check.csv kosis_pers", f"{chk.kosis_pers.min() / 1e6:.1f}")
add(2, "movers per year max (millions)", "9.6", "outputs/flows/mdis_check.csv kosis_pers", f"{chk.kosis_pers.max() / 1e6:.1f}")
add(3, "MDIS = KOSIS totals all 25 years", "25", "mdis_check.csv diff_total==0", str(int((chk.diff_total == 0).sum())))
add(4, "2023 province pairs differing", "64", "mdis_check.csv pairs_off 2023", str(int(chk.loc[chk.year == 2023, "pairs_off"].iloc[0])))
bl = open(R + "data_work/logs/build_mdis_db.txt", encoding="utf-8").read()
rec = [int(x.replace(",", "")) for x in re.findall(r"records ([\d,]+)", bl)]
sd = [(int(y), float(s)) for y, s in re.findall(r"(\d{4}): records .*?same-dong ([\d.]+)", bl)]
add(5, "records per year min (millions)", "4.84", "data_work/logs/build_mdis_db.txt", f"{min(rec) / 1e6:.2f}")
add(6, "records per year max (millions)", "6.92", "build_mdis_db.txt", f"{max(rec) / 1e6:.2f}")
s05 = [s for y, s in sd if y >= 2005]
add(7, "within-neighbourhood share min 2005+ (%)", "17.7", "build_mdis_db.txt same-dong", f"{min(s05) * 100:.1f}")
add(8, "within-neighbourhood share max 2005+ (%)", "22.0", "build_mdis_db.txt same-dong", f"{max(s05) * 100:.1f}")
xl = open(R + "data_work/logs/dong_xwalk.txt", encoding="utf-8").read()
snaps = re.findall(r"^\s+(\d{8}) \d+$", xl, flags=re.M)
add(9, "boundary snapshots", "29", "data_work/logs/dong_xwalk.txt", str(len(snaps)))
add(10, "first/last snapshot years", "2000 to 2025", "dong_xwalk.txt", f"{snaps[0][:4]} to {snaps[-1][:4]}")
pop = pd.read_csv(O + "flows/mdis_old_core_pop.csv")
add(11, "cities and counties (origins)", "124", "outputs/flows/mdis_old_core_pop.csv SG_ID", str(pop.SG_ID.nunique()))

# ---------- Section 5.1 (mdis_old_core.txt) ----------
P = "flows/mdis_old_core.txt"
per = ["2001-2005", "2006-2010", "2011-2015", "2016-2020", "2021-2025"]
lv = {p: row(P, "other           old", p) for p in per}   # old zone new rest same_do metro capital elsewhere unknown total
cols = ["old", "zone", "new", "rest", "same_do", "metro", "capital", "elsewhere", "unknown", "total"]
lv = {p: dict(zip(cols, map(num, v[1:]))) for p, v in lv.items()}
add(12, "out-moves excl. old-old 2001-05 (thousand)", "908,000", P, f"{round((lv[per[0]]['total'] - lv[per[0]]['old']) / 1000):,},000")
add(13, "out-moves excl. old-old 2021-25 (thousand)", "503,000", P, f"{round((lv[per[4]]['total'] - lv[per[4]]['old']) / 1000):,},000")
op = {p: row(P, "old_core_pop  net_per_1000", p) for p in per}
add(14, "gross out per 1,000 2001-05", "115.0", P, op[per[0]][3])
add(15, "gross out per 1,000 2021-25", "88.9", P, op[per[4]][3])
sh = {p: dict(zip(cols[1:9], map(num, row(P, "같은 비율", p)[1:]))) for p in per}
for k, p in enumerate(per):
    add(16 + k, f"share to new land {p} (%)", ["5.9", "12.5", "16.9", "19.7", "20.2"][k], P, f"{sh[p]['new']:.1f}")
add(21, "share to capital 2016-20 (%)", "19.1", P, f"{sh[per[3]]['capital']:.1f}")
add(22, "share to capital 2021-25 (%)", "19.7", P, f"{sh[per[4]]['capital']:.1f}")
add(23, "share to same province 2021-25 (%)", "19.5", P, f"{sh[per[4]]['same_do']:.1f}")
add(24, "new land largest destination 2021-25", "True", P, str(sh[per[4]]['new'] == max(sh[per[4]].values())))
add(25, "max share to new towns (%)", "1.2", P, f"{max(sh[p]['zone'] for p in per):.1f}")
nt = {p: dict(zip(["zone", "new", "rest", "same_do", "metro", "capital", "elsewhere", "unknown", "total"],
                  map(num, row(P, "원도심 순이동 (전입", p)[1:]))) for p in per}
add(26, "net loss min (per year)", "35,418", P, f"{-max(nt[p]['total'] for p in per):,.0f}")
add(27, "net loss max (per year)", "63,053", P, f"{-min(nt[p]['total'] for p in per):,.0f}")
add(28, "net loss per 1,000 min", "4.9", P, f"{min(-num(op[p][2]) for p in per):.1f}")
add(29, "net loss per 1,000 max", "10.1", P, f"{max(-num(op[p][2]) for p in per):.1f}")
add(30, "net loss to capital 2001-05", "51,770", P, f"{-nt[per[0]]['capital']:,.0f}")
add(31, "net loss to capital 2006-10", "20,488", P, f"{-nt[per[1]]['capital']:,.0f}")
add(32, "capital largest net loss 2001-10", "True", P, str(all(min(nt[p], key=lambda c: nt[p][c] if c != 'total' else 1e18) == "capital" for p in per[:2])))
for k, (p, a, b) in enumerate([(per[2], "22,197", "1,725"), (per[3], "26,653", "14,767"), (per[4], "12,168", "10,279")]):
    add(33 + 2 * k, f"net loss to new land {p}", a, P, f"{-nt[p]['new']:,.0f}")
    add(34 + 2 * k, f"net loss to capital {p}", b, P, f"{-nt[p]['capital']:,.0f}")
add(39, "new land largest net loss from 2011", "True", P, str(all(min(nt[p], key=lambda c: nt[p][c] if c != 'total' else 1e18) == "new" for p in per[2:])))
add(40, "net loss to new towns peak 2016-20", "4,632", P, f"{-nt[per[3]]['zone']:,.0f}")
# new-town origins 2011-25
L = lines(P)
i = next(k for k, l in enumerate(L) if l.startswith("신도시 전입자 출신"))
hdr = L[i + 1].split()[1:]
org = {}
for l in L[i + 3:]:
    t = l.split()
    if len(t) == len(hdr) + 1:
        org[t[0]] = dict(zip(hdr, [float(x) if x != "NaN" else 0 for x in t[1:]]))
for k, (c, v) in enumerate([("진주시", "28.7"), ("전주시", "26.3"), ("김천시", "19.8"), ("원주시", "18.2"), ("나주시", "4.9")]):
    add(41 + k, f"new-town in-movers from own old core, {c} (%)", v, P + " (2011-25, flows_old_core_mdis.py /15)", f"{org[c]['old'] / org[c]['total'] * 100:.1f}")
add(46, "Naju from adjacent metro (%)", "35.5", P, f"{org['나주시']['metro'] / org['나주시']['total'] * 100:.1f}")
add(47, "Naju from capital region (%)", "18.2", P, f"{org['나주시']['capital'] / org['나주시']['total'] * 100:.1f}")

# ---------- Section 5.2 (flows_age.txt) ----------
A = "partB/flows_age.txt"
for k, (p, v) in enumerate(zip(per, ["7.1", "15.8", "22.3", "28.3", "30.1"])):
    add(48 + k, f"children to new land+towns {p} (%)", v, A, row(A, "신규개발지+혁신·기업도시", p)[1])
add(53, "children share among movers to new land 2021-25 (%)", "13.5", A, row(A, "  2021-2025", "신규개발지")[1])
add(54, "children share among all movers 2021-25 (%)", "9.5", A, row(A, "  2021-2025", "전체")[1])
cap15 = [num(row(A, "  수도권\n" if False else "수도권", p, start=next(k for k, l in enumerate(lines(A)) if l.strip() == "수도권"))[2]) for p in per]
add(55, "15-24 to capital min (%)", "26.5", A, f"{min(cap15):.1f}")
add(56, "15-24 to capital max (%)", "30.3", A, f"{max(cap15):.1f}")
add(57, "15-24 share among movers to capital 2021-25 (%)", "26.9", A, row(A, "  2021-2025", "수도권")[2])
na = row(A, "원도심 순이동 연령별", "2021-2025")
for k, (lab, v) in enumerate(zip(["15-24", "25-39", "0-14", "40-64", "65+"], ["2.38", "2.73", "0.49", "0.59", "0.09"])):
    idx = {"0-14": 1, "15-24": 2, "25-39": 3, "40-64": 4, "65+": 5}[lab]
    add(58 + k, f"net loss by age 2021-25 {lab}", v, A, f"{-num(na[idx]):.2f}")
add(63, "net loss 25-39 2016-20", "4.14", A, f"{-num(row(A, '원도심 순이동 연령별', '2016-2020')[3]):.2f}")

# ---------- Section 5.3 (same_dong_bound_vital.txt, flows_supply_panel.txt) ----------
V = "partB/same_dong_bound_vital.txt"
pp = ["2000-2005", "2005-2010", "2015-2019", "2019-2024"]
ub = {p: row(V, "상한 (원도심 인구 천 명당 연)", p) for p in pp}
ni = {p: row(V, "기대 자연증가 (연", p) for p in pp}
for k, (p, a, b, c) in enumerate(zip(pp, ["12.7", "10.7", "12.0", "9.4"], ["15.2", "12.0", "11.9", "6.2"], ["6.5", "13.6", "17.9", "17.9"])):
    add(64 + 3 * k, f"bound H_ub {p}", a, V, f"{num(ub[p][1]):.1f}")
    add(65 + 3 * k, f"bound H_v (natural increase) {p}", b, V, f"{num(ub[p][3]):.1f}")
    add(66 + 3 * k, f"observed old->new aggregate {p}", c, V, f"{num(ub[p][5]):.1f}")
add(76, "natural increase old core 2000-05", "+2.6", V, f"{num(ni['2000-2005'][1]):+.1f}")
add(77, "natural increase old core 2019-24", "−3.5", V, f"{num(ni['2019-2024'][1]):+.1f}".replace("-", "−"))
add(78, "hidden/observed 2015-19 (about two-thirds)", "0.66", V, f"{num(ub['2015-2019'][3]) / num(ub['2015-2019'][5]):.2f}")
add(79, "hidden/observed 2019-24 (about one-third)", "0.34", V, f"{num(ub['2019-2024'][3]) / num(ub['2019-2024'][5]):.2f}")
vt = lines(V)
fp = next(k for k, l in enumerate(vt) if l.startswith("전 기간"))
rp = next(k for k, l in enumerate(vt) if l.startswith("등록센서스 기간만"))


def mrow(start, label):
    for l in vt[start:]:
        if l.startswith(label):
            return re.findall(r"[+-]\d+\.\d+\**\s*\(\d+\.\d+\)", l)
    raise KeyError(label)


def cell(t):
    m = re.match(r"([+-]\d+\.\d+)(\**)\s*\((\d+\.\d+)\)", t)
    return m.group(1), m.group(3)


# columns: s_old s_zone s_b1 s_b2 s_b3 s_b4
obs = mrow(fp, "net_old 관측")
add(80, "obs 0-0.5km coef (se)", "+10.18 (1.44)", V, "{} ({})".format(*cell(obs[2])))
add(81, "obs 0.5-2km coef (se)", "+5.64 (1.28)", V, "{} ({})".format(*cell(obs[3])))
add(82, "obs old-core coef", "+10.28", V, cell(obs[0])[0])
add(83, "obs zone coef", "−0.77", V, cell(obs[1])[0].replace("-", "−"))
for k, (lab, v) in enumerate([("net_old - H_ub (기존)", "+2.39 (1.57)"), ("net_old - H_v (자연증가 반영)", "+2.08 (1.58)"),
                              ("net_old - H_v2", "+1.23 (1.53)")]):
    add(84 + k, f"corrected 0-0.5km: {lab}", v, V, "{} ({})".format(*cell(mrow(fp, lab)[2])))
olds = [num(cell(mrow(fp, l)[0])[0]) for l in ["net_old - H_ub (기존)", "net_old - H_ub2", "net_old - H_v (", "net_old - H_v2"]]
add(87, "corrected old-core coef min", "+21.04", V, f"{min(olds):+.2f}")
add(88, "corrected old-core coef max", "+22.18", V, f"{max(olds):+.2f}")
robs = mrow(rp, "net_old 관측")
add(89, "register-only obs 0-0.5km (se)", "+7.67 (4.26)", V, "{} ({})".format(*cell(robs[2])))
rc = [num(cell(mrow(rp, l)[2])[0]) for l in ["net_old - H_ub (기존)", "net_old - H_ub2", "net_old - H_v (", "net_old - H_v2"]]
add(90, "register-only corrected min", "−2.05", V, f"{min(rc):+.2f}".replace("-", "−"))
add(91, "register-only corrected max", "+0.20", V, f"{max(rc):+.2f}")
F = "partB/flows_supply_panel.txt"
add(92, "s_b2 in_outside", "6.16", F, row(F, "계수 = 공급", "in_outside")[4].replace("+", "").rstrip("*"))
add(93, "s_b1 out_new", "−3.34", F, row(F, "계수 = 공급", "out_new")[3].rstrip("*").replace("-", "−"))
add(94, "panel cities / city-periods", "122 cities and counties and the four periods (488", F, "122 cities and counties and the four periods (488" if "시군 122, 시군-기간 488" in lines(F)[0] else "MISMATCH")

# ---------- Section 5.4 (zone_event.txt, zone_event_pooled.csv, flows_age.txt, emp_supply.txt, partB_did.txt) ----------
Z = "partB/zone_event.txt"
zl = lines(Z)
bi = next(k for k, l in enumerate(zl) if l.startswith("== 사건연구"))
ev = {}
for l in zl[bi + 2: bi + 20]:
    t = l.split()
    if t and re.fullmatch(r"-?\d", t[0]):
        ev[int(t[0])] = dict(zip(["out_zone", "out_new", "out_rest", "out_outside", "out_capital", "in_outside", "net_old"], t[1:8]))
g = lambda k, c: ev[k][c].rstrip("*")
add(95, "out_zone k=0", "7.9", Z, g(0, "out_zone").lstrip("+"))
add(96, "out_zone k=1,2 range", "7.4–7.5", Z, f"{min(num(g(1,'out_zone')), num(g(2,'out_zone'))):.1f}–{max(num(g(1,'out_zone')), num(g(2,'out_zone'))):.1f}")
add(97, "out_zone k=8", "2.0", Z, g(8, "out_zone").lstrip("+"))
pre = [num(g(k, "out_zone")) for k in range(-8, -1)]
add(98, "out_zone pre range", "−1.9 to −0.9", Z, f"{min(pre):.1f} to {max(pre):.1f}".replace("-", "−"))
add(99, "net_old k=0", "9.6", Z, g(0, "net_old").lstrip("-"))
add(100, "net_old k=1", "8.3", Z, g(1, "net_old").lstrip("-"))
add(101, "net_old insignificant from k=2", "True", Z, str(all("*" not in ev[k]["net_old"] for k in range(2, 9))))
add(102, "net_old k=-3 (significant)", "−6.6", Z, ev[-3]["net_old"].rstrip("*").replace("-", "−") if "*" in ev[-3]["net_old"] else "not sig")
zp = pd.read_csv(O + "partB/zone_event_pooled.csv").set_index("y")
add(103, "pooled out_zone (se)", "6.23 per 1,000 (cluster s.e. 1.43", "zone_event_pooled.csv", f"{zp.coef.out_zone:.2f} per 1,000 (cluster s.e. {zp.se.out_zone:.2f}")
add(104, "pooled out_zone perm p", "< 0.001", "zone_event_pooled.csv", "< 0.001" if zp.p_perm.out_zone < 0.001 else str(zp.p_perm.out_zone))
add(105, "pooled net_old (se)", "−4.21 (s.e. 2.48", "zone_event_pooled.csv", f"{zp.coef.net_old:.2f} (s.e. {zp.se.net_old:.2f}".replace("-", "−"))
add(106, "pooled net_old perm p", "0.152", "zone_event_pooled.csv", f"{zp.p_perm.net_old:.3f}")
add(107, "pooled out_outside", "+3.23", "zone_event_pooled.csv", f"{zp.coef.out_outside:+.2f}")
add(108, "pooled out_outside perm p", "0.582", "zone_event_pooled.csv", f"{zp.p_perm.out_outside:.3f}")
add(109, "pooled sg_in", "24.75", "zone_event_pooled.csv", f"{zp.coef.sg_in:.2f}")
add(110, "pooled sg_net / perm p", "5.96 (permutation p = 0.066", "zone_event_pooled.csv", f"{zp.coef.sg_net:.2f} (permutation p = {zp.p_perm.sg_net:.3f}")
add(111, "sg_in perm p < 0.001", "< 0.001", "zone_event_pooled.csv", "< 0.001" if zp.p_perm.sg_in < 0.001 else str(zp.p_perm.sg_in))
add(112, "age post net 0-14", "−1.10", A, row(A, "3. 혁신·기업도시 입주 전후", "0-14")[1].rstrip("*").replace("-", "−"))
add(113, "age post zone 25-39", "+2.08", A, row(A, "3. 혁신·기업도시 입주 전후", "25-39")[2].rstrip("*"))
add(114, "age post zone 40-64", "+1.97", A, row(A, "3. 혁신·기업도시 입주 전후", "40-64")[2].rstrip("*"))
E = "partB/emp_supply.txt"
add(115, "l_comm_old coef / perm p", "+0.026 log points, permutation p = 0.468", E,
    "{} log points, permutation p = {}".format(row(E, "C. 신도시 입주", "l_comm_old")[1], row(E, "C. 신도시 입주", "l_comm_old")[-1].split("=")[-1]))
add(116, "l_comm_rel coef", "0.146", E, row(E, "C. 신도시 입주", "l_comm_rel")[1].lstrip("-"))
add(117, "l_comm_rel in percent", "14%", E, f"{(1 - math.exp(-0.146)) * 100:.0f}%")
cs = {}
i = next(k for k, l in enumerate(zl) if l.startswith("== 시군별 통합 DiD"))
for l in zl[i + 2:]:
    t = l.split()
    if len(t) == 7:
        cs[t[0]] = num(t[5])
add(118, "city net_old Jeonju", "−12.2", Z, f"{cs['전주시']:.1f}".replace("-", "−"))
add(119, "city net_old Eumseong", "−12.0", Z, f"{cs['음성군']:.1f}".replace("-", "−"))
add(120, "city net_old Seogwipo", "+21.6", Z, f"{cs['서귀포시']:+.1f}")
ncomp = re.search(r"비교 시군 (\d+)", open(O + Z, encoding="utf-8").read()).group(1)
add(121, "event: treated / comparison", "109 comparison", Z, ncomp + " comparison")
D = "partB/partB_did.txt"
dl = open(O + D, encoding="utf-8").read()
add(122, "DiD treated / comparison", "nine innovation-city hosts with 111", D, "nine innovation-city hosts with 111" if "처치 시군 9, 비교 시군 111" in dl else "MISMATCH")
u = re.search(r"전체 비교군: lpop.*?2024: ([+-]\d+\.\d+) \((\d+\.\d+)\)", dl, re.S)
w = re.search(r"2005 인구 가중.*?2024: ([+-]\d+\.\d+) \((\d+\.\d+)\)", dl, re.S)
add(123, "DiD 2024 unweighted", "−0.0006 log points, s.e. 0.0429", D, f"{u.group(1)} log points, s.e. {u.group(2)}".replace("-", "−"))
add(124, "DiD 2024 weighted", "−0.0290, s.e. 0.0307", D, f"{w.group(1)}, s.e. {w.group(2)}".replace("-", "−"))
mv = re.search(r"입주 시작 연도.*", open(O + Z, encoding="utf-8").read()).group(0)
yrs = sorted({int(y) for y in re.findall(r"(\d{4})", mv)})
add(125, "move-in start years range", "between 2013 and 2018", Z, f"between {yrs[0]} and {yrs[-1]}")

# ---------- crosswalk statistics (outputs/paper2/xwalk_stats.txt, paper2_xwalk_stats.py) ----------
X = open(O + "paper2/xwalk_stats.txt", encoding="utf-8").read()
add(126, "neighbourhood codes used", "5,120", "outputs/paper2/xwalk_stats.txt", re.search(r"코드 수 \(2001-2025\): ([\d,]+)", X).group(1))
add(127, "code-years", "90,361", "xwalk_stats.txt", re.search(r"코드-연도 ([\d,]+)개", X).group(1))
add(128, "movers linked at origin (%)", "99.58", "xwalk_stats.txt", re.search(r"out_cd: .*?\(([\d.]+)%\)", X).group(1))
add(129, "movers linked at destination (%)", "99.56", "xwalk_stats.txt", re.search(r"in_cd: .*?\(([\d.]+)%\)", X).group(1))
rtot = int(re.search(r"합계 ([\d,]+)", X).group(1).replace(",", ""))
add(130, "registrations total (millions)", "147.5", "xwalk_stats.txt", f"{rtot / 1e6:.1f}")
tb = open(O + "paper2/tables.md", encoding="utf-8").read()
add(131, "Tables section identical to generated tables.md", "True", "outputs/paper2/tables.md", str(tb in draft))

# ---------- revision 2026-10-20: vacancy by construction year (companion paper source) and Figure 5 ----------
V = "partA/vacancy.txt"
vl = lines(V)
iv = next(k for k, l in enumerate(vl) if "빈집 가운데 2000년 전에 지은 주택 비중" in l)
vrow = next(l.split() for l in vl[iv + 1:] if l.startswith("감소"))
add(132, "pre-2000 share of vacant, shrinking, max 2015-24 (%)", "80.8%", V, f"{max(num(vrow[1]), num(vrow[3]), num(vrow[5])):.1f}%")
add(133, "pre-2000 share of vacant, shrinking, min 2015-24 (%)", "73.0%", V, f"{min(num(vrow[1]), num(vrow[3]), num(vrow[5])):.1f}%")
F5 = open(O + "paper2/fig5_case_cities.txt", encoding="utf-8").read()
for cid, (city, val) in zip((134, 135, 136), [("진주시", "28.7%"), ("전주시", "26.3%"), ("나주시", "4.9%")]):
    add(cid, f"Figure 5 share of new-town in-movers from own old core, {city}", val, "outputs/paper2/fig5_case_cities.txt",
        re.search(rf"{city}:.*= ([\d.]+%)", F5).group(1))

# ---------- revision 2026-10-20: old-core housing age and size (old_core_housing.py) ----------
H = pd.read_csv(O + "partB/old_core_housing.csv")
hq = lambda y, t, c: H[(H.year == y) & (H.scope == "비수도권 도 시군") & (H.type == t)][c].iloc[0]
for cid, (y, t, c, val) in zip(range(137, 143), [(2024, "old core", "pre2000", "72.5%"), (2024, "new", "pre2000", "4.8%"),
                                                  (2022, "old core", "le60", "42.9%"), (2022, "new", "le60", "32.2%"),
                                                  (2022, "old core", "gt85", "19.9%"), (2022, "new", "gt85", "14.9%")]):
    add(cid, f"{t} census blocks, {c} {y} (%)", val, "outputs/partB/old_core_housing.csv", f"{hq(y, t, c):.1f}%")

# ---------- compare ----------
out = []
bad = 0
for cid, claim, dv, src, rr in checks:
    ok = (dv == rr) or (dv.replace("−", "-") == rr.replace("−", "-"))
    present = dv in draft or dv in ("True", "0.66", "0.34", "25", "124", "+10.18 (1.44)") or dv.replace("−", "-") in draft
    if not ok or not present:
        bad += 1
    out.append((cid, claim, dv, src, rr, "OK" if ok else "MISMATCH", "yes" if present else "NOT IN DRAFT"))
df = pd.DataFrame(out, columns=["#", "claim", "draft", "source", "reread", "match", "in_draft"])
print(df.to_string(index=False))
print(f"\nchecked {len(df)}, problems {bad}")
df.to_csv(R + "outputs/paper2/numbers_check_pass2.csv", index=False, encoding="utf-8-sig")
