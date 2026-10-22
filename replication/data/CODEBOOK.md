# Codebook: estimation data of papers 1 and 2

Each paper has its own folder (`paper1/`, `paper2/`). Each file `{paper}/frames/{model id}.csv` holds the data of one regression, exactly as passed to the estimator
(rows with missing values in the model variables are dropped by the estimator, in Python and in R alike).
`models.csv` gives the formula, the standard-error type and N of each model; `python_estimates.csv` the
published estimates. All files are UTF-8; group and unit names are in Korean.

Units are the 161 cities and counties (*si/gun*) on 2022 boundaries (metropolitan cities and Sejong as one unit).
Growth rates are in percent; "log growth" is 100 × ln(x1/x0).

# Paper 1

## Identifiers and fixed effects

| Variable | Meaning |
|---|---|
| `SG_ID`, `sigun` | Unit identifier (numeric) and unit name |
| `group` | 감소 shrinking, 정체 stagnant, 성장 growing (non-capital provincial units; registered population change 2000–2019 below −5, −5 to +5, above +5 percent), 광역시 metropolitan city, 수도권 capital region |
| `region` | Province, with each metropolitan city grouped with the province around it (eight non-capital regions plus the capital region) |
| `rp`, `ry` | Region × five-year period and region × year cells (fixed effects) |
| `cluster_id` | Cluster for standard errors (the unit) |
| `gun` | 1 for counties (*gun*) |

## Shrinkage sprawl (`shrink_sprawl_*`; Table 1, Supplementary Tables S3–S4)

| Variable | Meaning |
|---|---|
| `new_rate_pre`, `new_rate_post` | New urban land 1999–2009 / 2009–2019 (cells rising from <10 to ≥50 percent urban), percent of urban land at the start |
| `leap_share_pre`, `leap_share_post` | Share of new urban land with no urban neighbour at the start (percent) |
| `d_lpcu_pre`, `d_lpcu_rp_post` | 100 × change in log urban land per resident (census population 2000–2010; registered population 2009–2019) |
| `gp` | Population growth of the period (percent); `neg` = 1 if `gp` < 0 |
| `lpop10` | Log population 2010 |
| `g_old_0010`, `g_old_1524` | Population change of the old core 2000–2010 / 2015–2024 (percent) |
| `g_pop_0010`, `g_pop_1524` | Unit population change, same periods (percent) |
| `out_share_1524` | Share of dwellings added 2015–2024 that lie outside the old core (percent) |

## Housing supply and demand (`supply_demand_*`; Table 2, Supplementary Table S5)

Unit × five-year period panel (2000–05, 2005–10, 2010–15, 2015–19, 2019–24), non-capital provincial units.

| Variable | Meaning |
|---|---|
| `s_house`, `g_hh`, `g_pop` | Annual growth of dwellings, households, population (percent per year, SGIS 100 m grid) |
| `*_lag`, `*_lead` | Same variable in the previous / next period |
| `shrink_lag` | 1 if population fell in the previous period |
| `sg_in`, `sg_net` | In-migration and net in-migration from outside the unit per 1,000 residents (MDIS microdata) |

## Industrial complexes (`ic_unmet_*`; Table 2, Supplementary Table S7)

Cross-section of 122 non-capital provincial units.

| Variable | Meaning |
|---|---|
| `ic_pre`, `ic_0105`, `ic_0612`, `ic_1624` | Complex area designated up to 2000, 2001–05, 2006–12, 2016–24, percent of 2009 urban land |
| `km2_0105`, `km2_0612` | The same in km² |
| `g_v` for v in `manuf`, `emp`, `pop`, `hh` | Log growth 2010–2024 of manufacturing employees, all employees, residents, households |
| `g05_v` | Log growth 2005–2015 (placebo outcome) |
| `pre_v` | Log growth 2000–2005 (pre-trend control) |
| `d_manuf` | Change in manufacturing employees 2010–2024 |
| `lpop00` | Log population 2000 |

## Vacancy (`vacancy_*`; Table 3, Supplementary Table S6)

Unit × year panel 2016–2025.

| Variable | Meaning |
|---|---|
| `s` | Net additions to the dwelling stock per 1,000 dwellings of the previous year |
| `d_vac`, `d_vac_old`, `d_vac_new5` | Change in vacant dwellings (all; built before 2000; built in the previous five years) per 1,000 dwellings of the previous year |
| `d_hh` | Change in households per 1,000 dwellings of the previous year (2020–2024) |

## Master plans (`plan_pop_*`; Table 4, Figure 2, Supplementary Table S8)

| Variable | Meaning |
|---|---|
| `plan_g` | Planned population growth, percent per year, equation (2) |
| `trend_g` | Registered population growth in the five years before adoption, percent per year, equation (3) |
| `post` | 1 for plans adopted in 2019 or later (after the 2017–2018 cap) |
| `excess_pct` | Planned increase over the plan horizon, percent of population at adoption |
| `reserve_share` | Reserve for future urbanisation ÷ planned urbanised land (percent) |
| `plan_excess` | 2009 plan: planned population ÷ 2009 registered population − 1 (percent) |
| `new_urb` | Urban land growth 2009–2019 (percent) |
| `g_reg` | Registered population change 2009–2019 (percent) |

## Event study of plan adoptions (`plan_event_*`; Figure 3, Supplementary Table S9)

Unit × year panel 2010–2025, 119 non-capital provincial units.

| Variable | Meaning |
|---|---|
| `zone`, `zone_res`, `devp` | Annual change in residential + commercial + industrial zoning; in residential zoning; land-form-change permit area. Percent of the unit's median urban zoning area 2008–2025, winsorised at the 1st/99th percentiles |
| `Em4`, `Em3`, `Em2`, `E0` … `E6` | Event-time indicators k = −4 (binned, k ≤ −4) … 6 (binned, k ≥ 6), k = −1 omitted. The treatment (new plan; plan enlarging the reserve; plan raising planned population; or the size of the increase) differs by model, see `models.csv` |

## Zoning routes (`zoning_route_*`; Table 4, Figure 4, Supplementary Table S10)

| Variable | Meaning |
|---|---|
| `out_A` | Share of 2009–2019 new urban land outside residential, commercial and industrial zones (2026 zoning, percent) |
| `lnew` | Log new urban land |
| `avail_urb` | Share of land not urban in 2009 that lies inside urban areas (percent) |
| `old_inA` | Share of the old core in residential, commercial and industrial zones (percent) |
| `reserve_share09` | 2009 reserve ÷ planned urbanised land (percent) |

# Paper 2

Units are the non-capital provincial cities and counties with at least 1,000 old-core residents (Sejong excluded).
The old core is 2009 urban land (L1 land cover ≥ 50 percent of the 100 m cell) that already held at least five
dwellings in 2000, outside the innovation and enterprise city zones. Migration counts come from the MDIS microdata
2001–2025; moves within one neighbourhood (*eup/myeon/dong*) are not observed in any year.

## Identifiers and fixed effects

| Variable | Meaning |
|---|---|
| `SG_ID` | Unit identifier (fixed effect) |
| `rp`, `ry` | Region × period and region × year cells (fixed effects; eight non-capital regions) |
| `block` | 500 m block of old-core cells (fixed effect, `partB_did_*`) |
| `oa` | SGIS census block (*jipgyegu*) code (fixed effect, `partB_did_*`) |
| `year` | Year (fixed effect, `partB_did_*`) |
| `cluster_id` | Cluster for standard errors (the unit) |
| `w_` | WLS weight: block population in 2005 (`partB_did_*`, weighted model) |

## Supply-location panel (`flows_supply_panel_*`, `same_dong_bound_vital_*`, `emp_supply_*`, `flows_age_*`; Tables 3–4, Sections 4.2–4.3)

Unit × period panel, four periods (2000–05, 2005–10, 2015–19, 2019–24; migration years 2001–05, 2006–10, 2016–19,
2020–24), 122 units, 488 unit-periods.

| Variable | Meaning |
|---|---|
| `s_old`, `s_zone` | Added dwellings inside the old core / inside the new-town zones, percent of the unit's dwellings at the start, per year |
| `s_b1` … `s_b4` | Added dwellings elsewhere, 0–0.5, 0.5–2, 2–5 and more than 5 km from the main old core (same unit) |
| `out_new`, `out_zone`, `out_rest` | Old core → new residential land / new-town zone / rest of the same unit, movers per 1,000 old-core residents at the start, per year |
| `out_inside`, `out_all` | Sum of the three; `out_all` = `out_inside` + `out_outside` |
| `out_outside` | Old core → outside the unit; split into `out_same_do` (same province), `out_metro` (metropolitan city), `out_capital` (capital region), `out_far` (elsewhere or unknown) |
| `in_inside`, `in_outside` | Into the old core from the rest of the unit / from outside it |
| `net_old` | Old-core net migration (in minus out) |
| `sg_in`, `sg_out`, `sg_net` | Moves across the unit boundary per 1,000 unit residents at the start |
| `y_net` | `net_old` (same as above) in the bound models |
| `y_net_h_ub`, `y_net_h_ub2` | `net_old` minus the upper bound of hidden same-neighbourhood moves (natural change assumed ≥ 0 on new land, ≤ 0 in the old core; `2` = neighbourhoods that also hold old core) |
| `y_net_h_v`, `y_net_h_v2` | The same with expected natural increase subtracted (local age structure, national survival and child–woman ratios) |
| `g_old` | Old-core population growth (percent per year, log) |
| `g_emp_old`, `g_comm_old` | Old-core employees / commerce employees (retail, accommodation, food), growth percent per year (log) |
| `rel_comm_old` | `g_comm_old` minus the unit's commerce employee growth (points per year) |
| `g_manuf`, `g_emp` | Unit manufacturing / all employee growth (percent per year), demand controls |

In `flows_age_*` the outcome columns (`net_old`, `out_new`, `out_zone`, `out_outside`, `out_capital`) hold the movers
of one age band (0–14, 15–24, 25–39, 40–64, 65+; see `models.csv` order and `code/04_partB/flows_age.py`), still per
1,000 old-core residents of all ages, so the band coefficients add up to the all-age coefficient. `net_a*`, `zone_a*`
are old-core net migration and old core → zone moves by age band in the new-town models.

## New-town event study (`zone_event_study_*`, `emp_supply_*`, `flows_age_*`; Table 5, Section 4.4)

Unit × year panel 2001–2025: 10 treated units (innovation or enterprise city with move-in) and 109 comparison units.

| Variable | Meaning |
|---|---|
| outcome columns | As in the supply panel, per year; denominators fixed at 2005 (old-core residents; unit residents for `sg_*`) |
| `em8` … `em2`, `e0` … `e8` | Event-time indicators k = −8 (binned) … 8 (binned), k = −1 omitted; move-in onset = first year the zone's in-movers reach 25 percent of their 2013–2025 peak |
| `post` | 1 for treated units from the onset year |
| `l_emp_old`, `l_comm_old` | Log old-core employees / commerce employees (SGIS grid, 2000, 2005, 2010, 2015, 2019, 2020, 2024) |
| `l_comm_rel` | `l_comm_old` minus log unit commerce employees |

Models without `cluster_id` are the one-treated-unit estimates (classical standard errors, not reported in the
paper). Permutation tests: `perm/{script}_controls.csv` is the comparison units' panel, `perm/{script}_draws.csv`
the 1,000 placebo assignments (draw, unit, onset year) made by the Python script, `perm/python_perm.csv` the
reported coefficient and permutation p.

## Innovation-city DiD (`partB_did_*`; Section 5.4)

| Variable | Meaning |
|---|---|
| `lpop` | Log population of a 500 m block of old core (SGIS grid 2000, 2005, 2010, 2015, 2019–2024; blocks with ≥ 100 residents in 2005) |
| `share65` | Share of residents aged 65+ in an old-core census block (percent; 2000, 2005, 2010, 2015, 2019, 2020, 2022, 2024) |
| `tr_{year}` | Treated (nine innovation-city hosts) × year, 2005 omitted |
| `tp` | Treated × (year ≥ 2015) |
| `tp_0_3`, `tp_3_6`, `tp_6p` | `tp` for blocks 0–3, 3–6 and more than 6 km from the innovation city |

## Sources

Land cover: Ministry of Environment. Grid statistics: Statistics Korea (SGIS). Registered population, vacancy,
unsold housing, urban-planning statistics: KOSIS. Migration: Statistics Korea MDIS (aggregated here to units;
the microdata cannot be redistributed). Zoning: MOLIT V-World. Industrial complexes: KRIHS and KICOX.
Full list: Supplementary Table S1 of paper 1, Table 1 of paper 2 and `DATA_SOURCES.md`.
