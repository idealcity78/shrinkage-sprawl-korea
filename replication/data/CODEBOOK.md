# Codebook: estimation data of paper 1

Each file `frames/{model id}.csv` holds the data of one regression, exactly as passed to the estimator
(rows with missing values in the model variables are dropped by the estimator, in Python and in R alike).
`models.csv` gives the formula, the standard-error type and N of each model; `python_estimates.csv` the
published estimates. All files are UTF-8; group and unit names are in Korean.

Units are the 161 cities and counties (*si/gun*) on 2022 boundaries (metropolitan cities and Sejong as one unit).
Growth rates are in percent; "log growth" is 100 × ln(x1/x0).

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

## Sources

Land cover: Ministry of Environment. Grid statistics: Statistics Korea (SGIS). Registered population, vacancy,
unsold housing, urban-planning statistics: KOSIS. Migration: Statistics Korea MDIS (aggregated here to units;
the microdata cannot be redistributed). Zoning: MOLIT V-World. Industrial complexes: KRIHS and KICOX.
Full list: Supplementary Table S1 of the paper and `DATA_SOURCES.md`.
