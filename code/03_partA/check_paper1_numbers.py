"""Double-check every number in docs/paper1_results_draft.md against the output files.

Each check names the value as written in the draft, the output file, and a regular expression whose first group
captures the value from that file. The script
  1. re-reads the value from the output file and compares it with the draft value (after the stated scaling),
  2. confirms the draft text contains the value as written,
  3. counts the words of the abstract and the submission rationale,
and writes docs/paper1_numbers_check.md (the verification table). Exit status 1 if any check fails.

Run with ArcGIS Pro Python:  propy.bat code\\03_partA\\check_paper1_numbers.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.join(paths.OUTPUTS, "partA")
DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs")
SUP = os.path.join("..", "paper1", "supplement_tables.md")
DRAFT = os.path.join(DOCS, sys.argv[1] if len(sys.argv) > 1 else "paper1_results_draft.md")

# (claim, value as written in the draft, file, regex capturing the source value, scale applied to the source value)
C = [
    # 5.1 shrinkage sprawl
    ("non-capital provincial si/gun with falling registered population 2009-19", "84", "shrink_sprawl.txt", r"비수도권 도 시군 121 가운데 2009-19 주민등록인구가 준 시군 (\d+)", 1),
    ("of which expanded urban land", "81", "shrink_sprawl.txt", r"그중 시가지가 늘어난 시군 (\d+) \(", 1),
    ("all si/gun with falling population, count", "96", "shrink_sprawl.txt", r"2009-19 주민등록인구가 준 시군 (\d+):", 1),
    ("share of them expanding (%)", "97", "shrink_sprawl.txt", r"시군 \d+: 시가지가 늘어난 시군 (\d+)%", 1),
    ("median new-urban-land rate (%)", "13.0", "shrink_sprawl.txt", r"신규 시가지 비율 중앙값 ([\d.]+)%, 1인당", 1),
    ("slope of new-urban rate on population growth", "0.256", "shrink_sprawl.txt", r"후기 \(토지 2009-19, 주민등록인구 2009-19\):\n\s+new_rate\s+상수\(인구 증가 0\) \+[\d.]+, 인구 증가 1%p \+([\d.]+)", 1),
    ("intercept at zero growth (%)", "24.89", "shrink_sprawl.txt", r"주민등록인구 2009-19\):\n\s+new_rate\s+상수\(인구 증가 0\) \+([\d.]+)", 1),
    ("urban land growth 2009-19 shrinking (%)", "28.0", "shrink_sprawl.txt", r"시가지 증가 %\s+([\d.]+) \(", 1),
    ("urban land growth 2009-19 growing (%)", "49.8", "shrink_sprawl.txt", r"시가지 증가 %\s+[\d.]+ \([\d.]+\)\s+[\d.]+ \([\d.]+\)\s+([\d.]+) \(", 1),
    ("per-capita urban log change 1999-2009 shrinking", "26.7", "shrink_sprawl.txt", r"1999-2009 감소 ([\d.]+), 정체", 1),
    ("per-capita 1999-2009 growing", "16.4", "shrink_sprawl.txt", r"1999-2009 감소 [\d.]+, 정체 [\d.]+, 성장 ([\d.]+)", 1),
    ("per-capita 1999-2009 capital region", "1.1", "shrink_sprawl.txt", r"1999-2009 감소 [\d.]+, 정체 [\d.]+, 성장 [\d.]+, 광역시 [\d.]+, 수도권 ([\d.]+) /", 1),
    ("per-capita 2009-19 shrinking", "30.5", "shrink_sprawl.txt", r"/ 2009-2019 감소 ([\d.]+)", 1),
    ("per-capita 2009-19 growing", "31.0", "shrink_sprawl.txt", r"/ 2009-2019 감소 [\d.]+, 정체 [\d.]+, 성장 ([\d.]+)", 1),
    ("per-capita 2009-19 capital region", "15.5", "shrink_sprawl.txt", r"/ 2009-2019 감소 [\d.]+, 정체 [\d.]+, 성장 [\d.]+, 광역시 [\d.]+, 수도권 ([\d.]+)", 1),
    ("density shrinking 2000/1999", "6,794", "shrink_sprawl.txt", r"감소 ([\d,]+) -> [\d,]+ -> [\d,]+;", 1),
    ("density shrinking 2009", "5,216", "shrink_sprawl.txt", r"감소 [\d,]+ -> ([\d,]+) -> [\d,]+;", 1),
    ("density shrinking 2019", "3,871", "shrink_sprawl.txt", r"감소 [\d,]+ -> [\d,]+ -> ([\d,]+);", 1),
    ("density capital region 2000/1999", "21,572", "shrink_sprawl.txt", r"수도권 ([\d,]+) -> [\d,]+ -> [\d,]+", 1),
    ("density capital region 2019", "15,456", "shrink_sprawl.txt", r"수도권 [\d,]+ -> [\d,]+ -> ([\d,]+)", 1),
    ("new dwellings outside old core 2015-24, shrinking (%)", "90.2", "shrink_sprawl.txt", r"감소\s+[\d.]+\s+[\d.]+\s+([\d.]+)\s+-[\d.]+\s+-[\d.]+\s+-[\d.]+", 1),
    ("old-core population change 2015-24, shrinking (%)", "16.8", "shrink_sprawl.txt", r"감소\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+-[\d.]+\s+-[\d.]+\s+-([\d.]+)\s+-[\d.]+", 1),
    ("si/gun population change 2015-24, shrinking (%)", "3.2", "shrink_sprawl.txt", r"감소\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+-[\d.]+\s+-[\d.]+\s+-[\d.]+\s+-([\d.]+)", 1),
    ("old-core change per point of new housing outside core", "0.251", "shrink_sprawl.txt", r"out_share_1524  비수도권 도 시군  \(n=121\): -([\d.]+)", 1),
    ("expansion + core decline + pop decline 2009-24, shrinking (%)", "69", "shrink_sprawl.txt", r"감소\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)\n정체", 1),
    ("same, growing (%)", "20", "shrink_sprawl.txt", r"성장\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)\n광역시", 1),
    # 5.2 supply
    ("housing growth after population decline (%/yr)", "0.61", "supply_demand.txt", r"주택 증가율 ([\d.]+)%/년", 1),
    ("household growth after population decline (%/yr)", "0.94", "supply_demand.txt", r"가구 증가율 ([\d.]+)%/년", 1),
    ("housing growth on prior household growth", "0.425", "supply_demand.txt", r"직전 수요만\s+g_hh_lag \+([\d.]+)", 1),
    ("next-period household growth on housing, FE", "0.028", "supply_demand.txt", r"g_hh_lead\s+~ s_house: 시군 FE 없음 \+[\d.]+ \([\d.]+\)\*+, 시군 FE -([\d.]+)", 1),
    ("its s.e.", "0.152", "supply_demand.txt", r"g_hh_lead\s+~ s_house: 시군 FE 없음 \+[\d.]+ \([\d.]+\)\*+, 시군 FE -[\d.]+ \(([\d.]+)\)", 1),
    ("next-period population growth on housing, FE", "0.024", "supply_demand.txt", r"g_pop_lead\s+~ s_house: 시군 FE 없음 \+[\d.]+ \([\d.]+\), 시군 FE -([\d.]+)", 1),
    ("its s.e.", "0.162", "supply_demand.txt", r"g_pop_lead\s+~ s_house: 시군 FE 없음 \+[\d.]+ \([\d.]+\), 시군 FE -[\d.]+ \(([\d.]+)\)", 1),
    ("next-period housing on household growth, FE", "0.249", "supply_demand.txt", r"s_house_lead\s+~ g_hh: 시군 FE 없음 \+[\d.]+ \([\d.]+\)\*, 시군 FE \+([\d.]+)", 1),
    ("its s.e.", "0.092", "supply_demand.txt", r"s_house_lead\s+~ g_hh: 시군 FE 없음 \+[\d.]+ \([\d.]+\)\*, 시군 FE \+[\d.]+ \(([\d.]+)\)", 1),
    ("same-period net in-migration per point of housing", "7.839", "supply_demand.txt", r"sg_net\s+~ s_house \+([\d.]+)", 1),
    ("next-period net in-migration", "1.481", "supply_demand.txt", r"sg_net_lead\s+~ s_house -([\d.]+)", 1),
    ("its s.e.", "1.180", "supply_demand.txt", r"sg_net_lead\s+~ s_house -[\d.]+ \(([\d.]+)\)", 1),
    ("industrial complexes", "926", "ic_unmet.txt", r"산업단지 (\d+)개", 1),
    ("their area (km2)", "691", "ic_unmet.txt", r"지정 면적 (\d+) km2", 1),
    ("2006-10 designated area (km2)", "144.5", "ic_unmet.txt", r"2006-10\s+[\d.]+\s+([\d.]+)", 1),
    ("2006-10 urbanised by 2019 (%)", "31.5", "ic_unmet.txt", r"2006-10\s+[\d.]+\s+[\d.]+\s+([\d.]+)", 1),
    ("2006-10 industrial use 2022 (%)", "14.0", "ic_unmet.txt", r"2006-10\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)", 1),
    ("post-2006 designations, shrinking (km2)", "123.2", "ic_unmet.txt", r"감소\s+265\.0\s+([\d.]+)", 1),
    ("post-2006 complexes, shrinking", "265", "ic_unmet.txt", r"감소\s+(\d+)\.0\s+123", 1),
    ("post-2006 designations, growing (km2)", "136.7", "ic_unmet.txt", r"성장\s+176\.0\s+([\d.]+)", 1),
    ("sale rate shrinking (%)", "90.2", "ic_unmet.txt", r"감소\s+265\.0\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)", 1),
    ("sale rate growing (%)", "96.1", "ic_unmet.txt", r"성장\s+176\.0\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)", 1),
    ("manufacturing workers/km2 shrinking", "512", "ic_unmet.txt", r"감소\s+265\.0(?:\s+[\d.]+){7}\s+([\d.]+)", 1),
    ("manufacturing workers/km2 growing", "672", "ic_unmet.txt", r"성장\s+176\.0(?:\s+[\d.]+){7}\s+([\d.]+)", 1),
    ("2006-12 designation -> later manufacturing growth", "1.132", "ic_unmet.txt", r"제조업 종사자  2006-12 지정 \+([\d.]+)", 1),
    ("placebo 2016-24 designation -> 2005-15 growth", "0.947", "ic_unmet.txt", r"제조업 종사자[^\n]*2005-15 성장 \+([\d.]+)", 1),
    ("prior manufacturing growth -> designation", "0.089", "ic_unmet.txt", r"pre_manuf \+([\d.]+)", 1),
    # 5.3 vacancy
    ("vacancy shrinking 2015 (%)", "12.5", "vacancy.txt", r"감소\s+[\d.]+\s+[\d.]+\s+([\d.]+)\s+[\d.]+\s+[\d.]+\s+[\d.]+\n정체", 1),
    ("vacancy shrinking 2025 (%)", "15.0", "vacancy.txt", r"감소\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)\n정체", 1),
    ("vacancy capital 2015 (%)", "3.7", "vacancy.txt", r"수도권\s+[\d.]+\s+[\d.]+\s+([\d.]+)\s+[\d.]+\s+[\d.]+\s+[\d.]+\n", 1),
    ("vacancy capital 2025 (%)", "5.5", "vacancy.txt", r"수도권\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)\n", 1),
    ("pre-2000 share of vacant, shrinking 2015 (%)", "80.8", "vacancy.txt", r"감소\s+([\d.]+)\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\n정체\s+67", 1),
    ("pre-2000 share of vacant, shrinking 2024 (%)", "73.0", "vacancy.txt", r"감소\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)\s+[\d.]+\n정체\s+67", 1),
    ("si/gun ever >10 unsold/1,000, shrinking (%)", "41", "vacancy.txt", r"감소 (\d+), 정체 \d+, 성장 \d+, 광역시", 1),
    ("same, growing (%)", "100", "vacancy.txt", r"감소 \d+, 정체 \d+, 성장 (\d+), 광역시", 1),
    ("old-unit vacancies per 1,000 added, shrinking", "225", "vacancy.txt", r"감소\s+\(시군 86\): d_vac \+[\d.]+ \([\d.]+\)\*+, d_vac_old \+([\d.]+)", 1000),
    ("its s.e. (x1000)", "29", "vacancy.txt", r"감소\s+\(시군 86\): d_vac \+[\d.]+ \([\d.]+\)\*+, d_vac_old \+[\d.]+ \(([\d.]+)\)", 1000),
    ("stagnant", "241", "vacancy.txt", r"정체\s+\(시군 11\): d_vac \+[\d.]+ \([\d.]+\)\*+, d_vac_old \+([\d.]+)", 1000),
    ("growing", "120", "vacancy.txt", r"성장\s+\(시군 25\): d_vac \+[\d.]+ \([\d.]+\)\*+, d_vac_old \+([\d.]+)", 1000),
    ("metropolitan and capital", "62", "vacancy.txt", r"광역시·수도권\s+\(시군 40\): d_vac \+[\d.]+ \([\d.]+\)\*+, d_vac_old \+([\d.]+)", 1000),
    # 5.4 plans
    ("plan vintages", "520", "plan_pop.txt", r"계획\(시군 × 수립일\) (\d+)개", 1),
    ("si/gun with plans", "130", "plan_pop.txt", r"(\d+)개 \(연구 시군", 1),
    ("plans after decline, shrinking", "158", "plan_pop.txt", r"감소 시군에서 직전 5년 인구가 줄던 때 세운 계획 (\d+)개", 1),
    ("of which projected growth (%)", "93", "plan_pop.txt", r"감소 시군에서 .*?인구 증가를 계획한 비율 (\d+)%", 1),
    ("planned above population at adoption (%)", "34", "plan_pop.txt", r"감소 시군에서 .*?수립 당시 인구의 (\d+)% 위", 1),
    ("planned growth shrinking (%/yr)", "2.18", "plan_pop.txt", r"감소\s+172\s+([\d.]+)", 1),
    ("prior trend shrinking", "0.96", "plan_pop.txt", r"감소\s+172\s+[\d.]+\s+-([\d.]+)", 1),
    ("realised shrinking", "0.76", "plan_pop.txt", r"감소\s+172\s+[\d.]+\s+-[\d.]+\s+-([\d.]+)", 1),
    ("attainment shrinking", "0.66", "plan_pop.txt", r"감소\s+172(?:\s+-?[\d.]+){4}\s+([\d.]+)", 1),
    ("attainment capital region", "0.82", "plan_pop.txt", r"수도권\s+159(?:\s+-?[\d.]+){4}\s+([\d.]+)", 1),
    ("slope planned on trend", "0.25", "plan_pop.txt", r"기울기 ([\d.]+)\*", 1),
    ("its s.e.", "0.13", "plan_pop.txt", r"기울기 [\d.]+\*+ \(se ([\d.]+)\)", 1),
    ("planned growth at zero trend, mean over regions", "3.30", "plan_pop.txt", r"표본 권역 평균\) ([\d.]+)", 1),
    ("its s.e.", "0.28", "plan_pop.txt", r"표본 권역 평균\) [\d.]+ \(se ([\d.]+)\)", 1),
    ("reserve per added resident, shrinking (m2)", "384", "plan_pop.txt", r"감소\s+[\d.]+\s+[\d.]+\s+([\d.]+)\n정체\s+17", 1),
    ("reserve per added resident, capital (m2)", "82", "plan_pop.txt", r"수도권\s+11\.3\s+[\d.]+\s+([\d.]+)", 1),
    ("cap effect (%p/yr)", "2.13", "plan_pop.txt", r"2019년 이후 수립\(추세·권역 통제\): -([\d.]+)", 1),
    ("its s.e.", "0.60", "plan_pop.txt", r"2019년 이후 수립.*?\(se ([\d.]+)\)", 1),
    ("2019-25 shrinking plans projecting growth (%)", "90", "plan_pop.txt", r"2019-25\s+48\s+[\d.]+\s+-[\d.]+\s+([\d.]+)", 1),
    ("2019-25 shrinking planned growth", "0.95", "plan_pop.txt", r"2019-25\s+48\s+([\d.]+)", 1),
    ("2019-25 shrinking trend", "1.15", "plan_pop.txt", r"2019-25\s+48\s+[\d.]+\s+-([\d.]+)", 1),
    ("2009 plan overstatement, shrinking (%)", "44", "plan_pop.txt", r"감소 시군 2009 계획 초과 중앙값 (\d+)%", 1),
    ("2009 plan overstatement, growing (%)", "49", "plan_pop.txt", r"성장 시군 (\d+)%", 1),
    ("new urban on overstatement", "0.018", "plan_pop.txt", r"계획 초과\(2009 계획인구 ÷ 2009 인구 − 1\): ([\d.]+)", 1),
    ("its s.e.", "0.038", "plan_pop.txt", r"계획 초과\(2009.*?\(se ([\d.]+)\)", 1),
    ("new urban on reserve share", "0.019", "plan_pop.txt", r"예정용지 ÷ 시가화용지 \(2009\): -([\d.]+)", 1),
    ("its s.e.", "0.012", "plan_pop.txt", r"예정용지 ÷ 시가화용지 \(2009\): -[\d.]+ \(se ([\d.]+)\)", 1),
    ("realised population change", "0.786", "plan_pop.txt", r"실제 인구 변화 ([\d.]+)\*", 1),
    ("new plans 2009-25", "176", "plan_event.txt", r"새 계획 시행 (\d+)건", 1),
    ("reserve-enlarging plans", "70", "plan_event.txt", r"시가화예정용지 증가 (\d+)건", 1),
    ("population-raising plans", "32", "plan_event.txt", r"계획인구 증가 (\d+)건", 1),
    ("reserve-enlarging plan -> zoning, cumulative", "2.39", "plan_event.txt", r"\[예정용지를 늘린 새 계획\(0/1\) → 용도지역\(주거·상업·공업\) 증가, 전체\].*?누적 -([\d.]+)", 1),
    ("its s.e.", "3.42", "plan_event.txt", r"\[예정용지를 늘린 새 계획\(0/1\) → 용도지역\(주거·상업·공업\) 증가, 전체\].*?\(se ([\d.]+)\)", 1),
    ("pre-period joint p (zoning)", "0.57", "plan_event.txt", r"\[예정용지를 늘린 새 계획\(0/1\) → 용도지역\(주거·상업·공업\) 증가, 전체\].*?결합검정 p=([\d.]+)", 1),
    ("continuous reserve -> zoning cumulative", "0.002", "plan_event.txt", r"\[예정용지 증가 1%p → 용도지역\(주거·상업·공업\) 증가, 전체\].*?누적 ([\d.]+)", 1),
    ("its s.e.", "0.004", "plan_event.txt", r"\[예정용지 증가 1%p → 용도지역\(주거·상업·공업\) 증가, 전체\].*?\(se ([\d.]+)\)", 1),
    ("median reserve increase (points)", "19.8", "plan_event.txt", r"예정용지 \+([\d.]+)%", 1),
    ("permits 3 years after new plan, shrinking", "4.669", "plan_event.txt", r"\[새 계획 시행\(0/1\) → 토지형질변경 허가, 감소\][^\n]*\n[^\n]*\+3:-([\d.]+)", 1),
    # zoning routes
    ("new urban outside urban-use zones, shrinking (%)", "65.5", "zoning_route.txt", r"신규 시가지 2009→19: 용도지역별 비중\(%\)\n.*?\n.*?\n감소\s+([\d.]+)", -1),
    ("planned-management share, shrinking (%)", "25.8", "zoning_route.txt", r"신규 시가지 2009→19.*?\n감소\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)", 1),
    ("natural-green share, shrinking (%)", "14.2", "zoning_route.txt", r"신규 시가지 2009→19.*?\n감소\s+[\d.]+\s+([\d.]+)", 1),
    ("outside, growing (%)", "54.5", "zoning_route.txt", r"신규 시가지 2009→19.*?\n성장\s+([\d.]+)", -1),
    ("outside, metropolitan (%)", "46.8", "zoning_route.txt", r"신규 시가지 2009→19.*?\n광역시\s+([\d.]+)", -1),
    ("new dwellings outside urban-use zones, shrinking (%)", "70.3", "zoning_route.txt", r"원도심 밖 주택 증가.*?\n감소\s+([\d.]+)", -1),
    ("same, growing (%)", "35.8", "zoning_route.txt", r"원도심 밖 주택 증가.*?\n성장\s+([\d.]+)", -1),
    ("same, capital region (%)", "27.9", "zoning_route.txt", r"원도심 밖 주택 증가.*?\n수도권\s+([\d.]+)", -1),
    ("gap vs growing (points)", "17.1", "zoning_route.txt", r"감소 \(성장 대비\): \+([\d.]+)", 1),
    ("gap with controls (points)", "12.6", "zoning_route.txt", r"군 여부 통제: 감소 \+([\d.]+)", 1),
    ("urban-use zone growth 2008-19, shrinking (km2)", "156.7", "zoning_route.txt", r"예정용지 변화\n.*?\n감소\s+([\d.]+)", 1),
    ("new urban inside them (km2)", "60.6", "zoning_route.txt", r"예정용지 변화\n.*?\n감소\s+[\d.]+\s+([\d.]+)", 1),
    ("reserve 2009, shrinking (km2)", "758.6", "zoning_route.txt", r"예정용지 변화\n.*?\n감소(?:\s+[\d.]+){3}\s+([\d.]+)", 1),
    ("reserve 2019, shrinking (km2)", "832.8", "zoning_route.txt", r"예정용지 변화\n.*?\n감소(?:\s+[\d.]+){4}\s+([\d.]+)", 1),
    ("reserve 2009, growing (km2)", "725.6", "zoning_route.txt", r"예정용지 변화\n(?:.*\n)*?성장(?:\s+[\d.]+){3}\s+([\d.]+)", 1),
    ("reserve 2019, growing (km2)", "565.9", "zoning_route.txt", r"예정용지 변화\n(?:.*\n)*?성장(?:\s+[\d.]+){4}\s+([\d.]+)", 1),
    ("reserve share -> off-plan, per 10 points", "0.21", "zoning_route.txt", r"10%p: \+([\d.]+)", 1),
    ("its s.e.", "0.20", "zoning_route.txt", r"10%p: \+[\d.]+ \(se ([\d.]+)\)", 1),
    # added for the revised manuscript (paper1_text.md): data, method and sample-size statements
    ("grid/registered population, all groups, 2010", "0.960", SUP, r"All non-capital provincial and comparison groups \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|", 1),
    ("grid/registered population, all groups, 2015", "1.016", SUP, r"All non-capital provincial and comparison groups \| [\d.]+ \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|", 1),
    ("grid/registered population, shrinking, 2010", "0.971", SUP, r"\| Shrinking \| 0\.\d{3} \| [\d.]+ \| ([\d.]+) \|", 1),
    ("grid/registered population, shrinking, 2015", "1.049", SUP, r"\| Shrinking \| 0\.\d{3} \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|", 1),
    ("shrinking units in the housing panels", "86", "supply_demand.txt", r"감소 (\d+), 정체", 1),
    ("median non-contiguous share of new urban land 2009-19, shrinking (%)", "77.2", "shrink_sprawl.txt", r"비연속 비율 %\s+([\d.]+) \(", 1),
    ("median share > 2 km from old core, shrinking (%)", "8.7", "shrink_sprawl.txt", r"2km 넘는 신규 비율 %\s+([\d.]+) \(", 1),
    ("median share > 2 km from old core, capital region (%)", "0.4", "shrink_sprawl.txt", r"2km 넘는 신규 비율 %(?:\s+[\d.]+ \([\d.]+\)){4}\s+([\d.]+) \(", 1),
    ("old-dwelling vacancy per new dwelling, non-capital", "0.169", "vacancy.txt", r"\(시군 122\): d_vac \+[\d.]+ \([\d.]+\)\*+, d_vac_old \+([\d.]+)", 1),
    ("same, household change controlled 2020-24", "0.177", "vacancy.txt", r"가구 변화 통제 \(2020-2024\): d_vac_old ~ s \+([\d.]+)", 1),
    ("planned-route share of available land, shrinking (%)", "0.6", "zoning_route.txt", r"가용지\): 용도지역별 비중\(%\).*?감소\s+([\d.]+)", 1),
    ("lead regressions, observations", "488", SUP, r"\| Next-period household growth \| Housing growth \| [^|]+\| [^|]+\| (\d+) \|", 1),
    ("vacancy panel, si/gun-years", "1,220", SUP, r"Panel A\. Change in vacant[\s\S]*?\| Non-capital provincial \| [^|]+\| [^|]+\| [^|]+\| ([\d,]+) \|", 1),
    ("industrial-complex cross-section, si/gun", "122", SUP, r"Designation and later growth, cross-section of (\d+) si/gun", 1),
    ("event-study si/gun", "119", "plan_event.txt", r"시군 (\d+)개, 새 계획", 1),
    ("same-period household growth on housing growth, all periods", "1.035", SUP, r"\| Household growth \| ([\d.]+) \(", 1),
    ("same, excluding 2010-15", "0.994", SUP, r"\| Household growth \| [^|]+\| ([\d.]+) \(", 1),
    ("new-urban rate at zero growth 1999-2009 (%)", "18.35", SUP, r"census population 2000–2010\) \| New urban land rate \(%\) \| ([\d.]+) \(", 1),
    ("its s.e.", "4.37", SUP, r"census population 2000–2010\) \| New urban land rate \(%\) \| [\d.]+ \(([\d.]+)\)", 1),
    ("slope 1999-2009", "0.387", SUP, r"census population 2000–2010\) \| New urban land rate \(%\) \| [^|]+\| [^|]+\| ([\d.]+)", 1),
    ("s.e. of the 2009-19 prediction at zero growth", "2.27", SUP, r"registered population 2009–2019\) \| New urban land rate \(%\) \| 24\.89 \(([\d.]+)\)", 1),
    ("s.e. of the old-core coefficient", "0.077", SUP, r"New dwellings outside the old core 2015–24 \(%\) \| Non-capital provincial \| -0\.251 \(([\d.]+)\)", 1),
    ("housing growth after periods without decline (%/yr)", "1.50", SUP, r"\| No population decline \| ([\d.]+) \|", 1),
    ("household growth after periods without decline (%/yr)", "1.55", SUP, r"\| No population decline \| [\d.]+ \| ([\d.]+) \|", 1),
    ("housing growth after prior decline", "0.351", SUP, r"\| Prior-period population decline \(0/1\) \|\s*\| -([\d.]+)", 1),
    ("same, same-period households controlled", "0.019", SUP, r"\| Prior-period population decline \(0/1\) \|\s*\| [^|]+\| -([\d.]+)", 1),
    ("its s.e.", "0.057", SUP, r"\| Prior-period population decline \(0/1\) \|\s*\| [^|]+\| -[\d.]+ \(([\d.]+)\)", 1),
    ("urbanised 2019, complexes designated 2001-05 (%)", "58.1", SUP, r"\| 2001–05 \| \d+ \| [\d.]+ \| ([\d.]+) \|", 1),
    ("urbanised 2019, complexes designated 2011-15 (%)", "17.8", SUP, r"\| 2011–15 \| \d+ \| [\d.]+ \| ([\d.]+) \|", 1),
    ("urban in late-1990s map, shrinking, designated before 2006 (%)", "21.8", SUP, r"\| Shrinking \(before 2006\)(?: \| [\d.,]+){4} \| ([\d.]+) \|", 1),
    ("urban in late-1990s map, shrinking, designated after 2006 (%)", "3.1", SUP, r"\| Shrinking \(after 2006\)(?: \| [\d.,]+){4} \| ([\d.]+) \|", 1),
    ("placebo, all employment, designated 2016-24", "0.751", SUP, r"\| Placebo: growth 2010–24 \| Designated 2016–24 \| [^|]+\| ([\d.]+) \(", 1),
    ("all employment, designated 2006-12", "0.432", SUP, r"\| Growth 2010–24 \| Designated 2006–12 \| [^|]+\| ([\d.]+) \(", 1),
    ("placebo 2005-15 growth, all employment, designated 2016-24", "0.525", SUP, r"\| Placebo: growth 2005–15 \| Designated 2016–24 \| [^|]+\| ([\d.]+) \(", 1),
    ("next-period household growth on housing growth, no unit FE", "0.391", SUP, r"\| Next-period household growth \| Housing growth \| ([\d.]+) \(", 1),
    ("its s.e.", "0.119", SUP, r"\| Next-period household growth \| Housing growth \| [\d.]+ \(([\d.]+)\)", 1),
    ("2010 long-term vacancy share, shrinking (%)", "50.0", "vacancy.txt", r"12개월 이상 빈 주택 비중 \(%\): 감소 ([\d.]+)", 1),
    ("2010 long-term vacancy share, capital region (%)", "20.9", "vacancy.txt", r"12개월 이상 빈 주택 비중 \(%\):[^\n]*수도권 ([\d.]+)", 1),
    ("recent-dwelling vacancy per new dwelling, shrinking", "0.376", SUP, r"Panel A\. Change in vacant[\s\S]*?\| Shrinking \| [^|]+\| [^|]+\| ([\d.]+) \(", 1),
    ("recent-dwelling vacancy per new dwelling, growing", "0.356", SUP, r"Panel A\. Change in vacant[\s\S]*?\| Growing \| [^|]+\| [^|]+\| ([\d.]+) \(", 1),
    ("planned growth, shrinking, adopted 2013-18 (%/yr)", "5.97", SUP, r"\| Shrinking \| 2013–18 \| \d+ \| ([\d.]+)", 1),
    ("prior trend, same plans", "0.37", SUP, r"\| Shrinking \| 2013–18 \| \d+ \| [\d.]+ \| -([\d.]+)", 1),
    ("reserve share on planned increase", "0.076", SUP, r"Planned increase \(% of population at adoption\) \| -([\d.]+)", 1),
    ("its s.e.", "0.259", SUP, r"Planned increase \(% of population at adoption\) \| -[\d.]+ \(([\d.]+)\)", 1),
    ("concentration of new urban land in planned route, shrinking", "56.89", SUP, r"\| Shrinking \| (56\.\d+) \|", 1),
    ("planned-management share of available land, shrinking (%)", "10.8", SUP, r"\| Shrinking \| 0\.6 \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|", 1),
    ("planned-management share of added dwellings outside old core, shrinking (%)", "27.9", SUP, r"\| Shrinking \| 29\.7 \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|", 1),
    ("production/conservation management share, same", "16.2", SUP, r"\| Shrinking \| 29\.7(?: \| [\d.]+){3} \| ([\d.]+) \|", 1),
    ("metropolitan reserve 2009 (km2)", "150.5", SUP, r"\| Metropolitan \| 19\.4 \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|", 1),
    ("metropolitan reserve 2019 (km2)", "228.9", SUP, r"\| Metropolitan \| 19\.4(?: \| [\d.]+){3} \| ([\d.]+) \|", 1),
    ("event-study si/gun-years", "1,904", "plan_event.txt", r"n=(\d+), 사전 계수 결합검정 p=0\.57", 1),
]

# values derived from the checked ones (computed here, not read)
DERIVED = [
    ("density decline shrinking (%)", "43", lambda v: round((1 - v["3,871"] / v["6,794"]) * 100)),
    ("density decline capital (%)", "28", lambda v: round((1 - v["15,456"] / v["21,572"]) * 100)),
    ("study si/gun = 85 + 11 + 25 + 8 + 32 (group counts, shrink_sprawl.txt)", "161", lambda v: 85 + 11 + 25 + 8 + 32),
    ("cap effect rounded in section 3 (2.13 -> 2.1)", "2.1", lambda v: round(v["2.13"], 1)),
    ("upper bound of continuous effect, % of 6-yr zoning flow (about 3)", "3",
     lambda v: round((0.002 + 1.96 * 0.004) * 19.8 / (1.27 * 6) * 100)),
]


def num(s):
    return float(s.replace(",", ""))


def table_values():
    """Every number printed in Tables 1-4 and S2-S11 (absolute values)."""
    t = ""
    for fn in ("tables.md", "supplement_tables.md"):
        t += open(os.path.join(A, "..", "paper1", fn), encoding="utf-8").read()
    vals = set()
    for x in re.findall(r"-?[\d,]*\d(?:\.\d+)?", t):
        try:
            vals.add(abs(float(x.replace(",", ""))))
        except ValueError:
            pass
    return vals


def in_tables(val, vals):
    """The value as written, allowing the table to show more decimals or the text to scale by 1,000 (per dwelling)."""
    v = num(val)
    d = len(val.split(".")[1]) if "." in val else 0
    return any(abs(round(x, d) - v) < 1e-9 or abs(round(x * 1000, d) - v) < 1e-9 for x in vals)


def section_words(text, head):
    m = re.search(rf"## {head}.*?\n(.*?)(?=\n---|\n## )", text, re.S)
    if not m:
        return 0
    body = re.sub(r"\*\*Keywords:.*", "", m.group(1), flags=re.S)
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-.,%²]*", body))


def main():
    draft = open(DRAFT, encoding="utf-8").read()
    cache, rows, bad, seen = {}, [], 0, {}
    tv = table_values()
    for i, (claim, val, f, rx, scale) in enumerate(C, 1):
        text = cache.setdefault(f, open(os.path.join(A, f), encoding="utf-8").read())
        m = re.search(rx, text, re.S)
        if not m:
            src, ok = "NOT FOUND", False
        else:
            x = num(m.group(1))
            x = 100 - x if scale == -1 else x * scale
            d = len(val.split(".")[1]) if "." in val else 0
            src = f"{x:,.{d}f}" if "," in val else f"{x:.{d}f}"
            ok = abs(round(x, d) - num(val)) < 1e-9
        in_draft = val in draft
        bad += (not ok) + (not in_draft)
        seen[val] = num(val)
        rows.append((i, claim, val, f, src, "OK" if ok else "MISMATCH", "yes" if in_draft else "NO",
                     "yes" if in_tables(val, tv) else "text only"))
    for claim, val, fn in DERIVED:
        x = fn(seen)
        ok = abs(x - num(val)) < 1e-9
        in_draft = val in draft
        bad += (not ok) + (not in_draft)
        rows.append((len(rows) + 1, claim + " [derived]", val, "computed from rows above", str(x),
                     "OK" if ok else "MISMATCH", "yes" if in_draft else "NO", "derived"))
    w_abs, w_rat = section_words(draft, "Abstract"), section_words(draft, "Submission rationale")
    lines = ["# 논문 1 수치 대조표 (자동 생성: `code/03_partA/check_paper1_numbers.py`)", "",
             f"대상 `docs/paper1_results_draft.md`. 수치 {len(rows)}개, 불일치·미기재 {bad}건. "
             f"초록 {w_abs}단어(한도 250), 투고 사유서 {w_rat}단어(한도 300).", "",
             "출처 파일은 `outputs/partA/`. 부호는 본문 서술에 맞춰 절댓값으로 대조함(예: −0.028은 0.028). "
             "\"밖 비중\"은 100 − 주거·상업·공업 비중으로 환산.", "",
             "\"표에 있음\"은 값이 표 1–4 또는 보충표 S2–S11에 인쇄되어 독자가 확인할 수 있는지를 뜻함.", "",
             "| # | 내용 | 원고 값 | 출처 파일 | 출처에서 다시 읽은 값 | 대조 | 원고에 있음 | 표에 있음 |",
             "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {r[0]} | {r[1]} | {r[2]} | `{r[3]}` | {r[4]} | {r[5]} | {r[6]} | {r[7]} |" for r in rows]
    lines[2] = lines[2].replace("`docs/paper1_results_draft.md`", f"`docs/{os.path.basename(DRAFT)}`")
    out = "paper1_numbers_check.md" if DRAFT.endswith("paper1_results_draft.md") else "paper1_manuscript_numbers_check.md"
    with open(os.path.join(DOCS, out), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"checked {len(rows)}, problems {bad}; abstract {w_abs} words, rationale {w_rat} words")
    for r in rows:
        if r[5] != "OK" or r[6] != "yes":
            print("  ", r)
    print("text only (not printed in any table):", [(r[0], r[2]) for r in rows if r[7] == "text only"])
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
