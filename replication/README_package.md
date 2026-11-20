# Replication package: shrinkage sprawl and old-core decline in Korea's non-capital regions

This package reproduces every table, figure and number reported in two companion papers:

- **Paper 1.** *Planning for growth that never comes: Permissive developmentalism and shrinkage sprawl in South
  Korea's non-capital regions* (main text Tables 1–5, Figures 1–5; Supplementary Tables S2–S13).
- **Paper 2.** *Where do the residents of new peripheral housing come from? Origin–destination evidence on old-core
  decline in Korea's shrinking cities, 2001–2025* (Tables 1–5, Figures 1–5).

One command runs the whole analysis from the data in `data/`, checks every number reported in the two papers
against the new output (181 numbers in paper 1, 152 in paper 2), and re-estimates every regression independently in
R (919 and 961 terms):

```
python run_all.py
```

## 1. Overview

The analysis has two stages.

1. **Raw-data stage** (not run by this package). National land-cover maps, the SGIS 100 m grid and census-block
   statistics, MDIS migration microdata, zoning polygons and administrative boundaries are rasterised to a common
   100 m grid (ArcGIS Pro 3.3 with `arcpy`) and aggregated to cities and counties (*si/gun*), 500 m blocks, census
   blocks (*jipgyegu*) and neighbourhoods (*dong*). The scripts are included in `code/` (folders `00_data`,
   `01_landcover`, `02_grid`, `05_flows`, and the build step of each analysis script) so that every step can be read,
   but most raw data may not be redistributed (Section 2).
2. **Analysis stage** (run by this package). The aggregates written by the raw-data stage are the analysis data in
   `data/`. Every analysis script has a `models` mode that starts from these files and needs neither the raw data nor
   ArcGIS. `run_all.py` runs the scripts in this mode, in order, writing all output to `results/`.

## 2. Data availability and provenance

All data are public statistics or derived from them. The package contains only unit-level aggregates (si/gun,
si/gun-year, 500 m block, census block, neighbourhood) and published KOSIS tables. Sources, table identifiers,
editions and download dates are listed in `DATA_SOURCES.md` (in Korean) and in Supplementary Table S1 of paper 1.

| Source | Used for | Access and licence | Files in `data/` |
|---|---|---|---|
| Ministry of Environment, national land-cover maps (level 1, 30 m; 1999, 2009, 2019), https://aid.mcee.go.kr | Urban land, new urban land, old core | Free after registration; raw maps not redistributed | Aggregates in `outputs/partA/shrink_sprawl_grid.csv`, `zoning_route_grid.csv`, `newcity_share_grid.csv` and the paper 2 panels |
| Statistics Korea, SGIS 100 m grid statistics (population, households, dwellings, employees; 2000–2024), https://sgis.mods.go.kr | Population, households and housing supply by area | Free after registration; raw grids not redistributed | Aggregates in `outputs/partA/supply_demand_levels.csv`, `outputs/partB/*.csv` |
| Statistics Korea, SGIS census-block statistics (sex and age, dwellings by construction year and floor area; 2025 boundaries) | Old-core ageing, natural increase, dwelling age | Free after registration | Aggregates in `outputs/partB/old_core_housing_sigun.csv`, `same_dong_bound_vital_rates.csv`, `partB_did_oa.csv` (census-block panel of the old-core sample) |
| Statistics Korea, MDIS internal-migration microdata (public-use files, 2001–2025), https://mdis.mods.go.kr | Moves between old cores, new towns and new housing | Free after registration; microdata may not be redistributed | Annual counts by si/gun, origin and destination type in `outputs/flows/mdis_old_core_flows.csv`, `mdis_old_core_pop.csv`; summaries `mdis_old_core.txt`, `mdis_check.csv`; processing logs in `data_work/logs/` |
| KOSIS tables (Statistics Korea, Ministry of the Interior and Safety, MOLIT), https://kosis.kr | Registered population (DT_1B040A3), vacancies (DT_1JU0511, DT_1JU1012, DT_1JU1512, DT_1YL202005), unsold housing (DT_MLTM_2082, DT_MLTM_5328), master plans, zoning and permits (TX_315_2009_H1004, H1004A, H1440, H1100) | Public, free (KOSIS open API) | `data_work/housing/*.csv` (as downloaded, reshaped to long form) |
| Korea Industrial Complex Corporation, national industrial-complex statistics (30 June 2026), https://www.data.go.kr | Industrial-complex status | Public data portal, free use | `ugm/ugm_national/supply_raw/*.csv` |
| MOLIT V-World zoning polygons UQ111, UQ112 (October 2026), https://www.vworld.kr | Zoning route of new urban land | Free; polygons not redistributed (CC BY-NC-ND) | Aggregates in `outputs/partA/zoning_route_grid.csv` |
| Industrial-complex boundaries (KRIHS) and innovation/enterprise-city boundaries (V-World UB811) | Industrial complexes, new-town zones | Free | Aggregates in `outputs/partA/ic_complexes_grid.csv`, `newcity_zones.csv` |
| Housing Site Information System, development-district files (attributes and boundaries; as of 30 September 2026) | Housing-site districts (paper 1, Table S7; paper 2, Table 4, Panel D) | Free; boundaries not redistributed | District attributes with grid aggregates in `outputs/partA/hd_districts_grid.csv`; housing added inside and outside districts by si/gun and period in `outputs/partB/hd_supply_grid.csv` |
| Statistics Korea, SGIS census boundaries (*eup/myeon/dong*, 2020 4th quarter), dissolved to the study's 162 si/gun units (`code/02_grid/build_sigun_boundary.py`, unit table `code/02_grid/sgis2020_sgg_units.csv`) | Unit of analysis, maps | Free after registration | Vertex arrays for the maps in `outputs/partA/geometry_sigun.npz`, `geometry_region.npz` |

The variables of the regression data are described in `replication/data/CODEBOOK.md`.

## 3. Computational requirements

- **Python** 3.11 with numpy 1.24.3, pandas 2.0.2, statsmodels 0.14.0, scipy 1.9.3, matplotlib 3.6.3 (`requirements.txt`;
  the papers were produced with the ArcGIS Pro 3.3.1 environment `arcgispro-py3`, but `arcpy` is not needed here).
- **R** 4.4 with `fixest` and `data.table` (versions in `replication/R/renv.lock`). Optional: without `Rscript` on
  the path, `run_all.py` skips the R step.
- Figures use the Arial font; on systems without it matplotlib substitutes another font, which changes only the
  appearance of the figures.
- Run time on a Windows 11 workstation: about 16 minutes in total, of which about 14 minutes are the 500 m block
  and census-block event studies of paper 2 (`partB_did`, run inside `export_model_frames.py paper2`); the R step
  takes under a minute. Disk: about 90 MB for `results/`.
- Tested from a fresh copy of this package with `arcpy` made unavailable: (1) this version, with the Python environment listed
  above and R 4.4.1 — every step succeeded, every reported number (181 + 151) and every R estimate agreed, and the
  tables and figures were byte-identical to those in the papers; (2) the previous build, with Python 3.12, numpy 1.26, pandas 2.2,
  statsmodels 0.14.2, matplotlib 3.8 — all numbers and tables identical; figures differ only in rendering.
  (Paper 2's check has 152 items in the authors' copy; item 131 compares the manuscript's table section with the
  generated tables and needs the manuscript, which is not part of the package.)

## 4. Instructions

```
pip install -r requirements.txt          # or use an existing environment with these packages
python run_all.py                        # all steps; add --no-r to skip R
```

`run_all.py` copies `data/` to a new folder `results/` (the input files are never changed), sets the environment
variable `USUS_DATA` to it, and runs:

| Step | Script (in `code/`, mode) | Output in `results/outputs/` |
|---|---|---|
| Paper 1 | `03_partA/regpop.py` | `partA/regpop_sigun.csv` |
| | `replication/export_model_frames.py paper1`: runs `supply_demand`, `shrink_sprawl`, `ic_unmet`, `hd_unmet`, `vacancy`, `plan_pop`, `plan_event`, `zoning_route`, `robust_review` (models) and records each regression | `partA/*.txt`, `*_models.csv`; `replication/data/paper1/` |
| | `03_partA/newcity_share.py` (models) | `partA/newcity_share.csv` |
| | `03_partA/paper1_supplement_tables.py`, `paper1_tables.py` | `paper1/supplement_tables.md`, `paper1/tables.md` |
| | `03_partA/paper1_figures.py` (models) | `paper1/fig1_groups.png` … `fig5_routes.png` |
| | `03_partA/check_paper1_numbers.py` | `paper1/numbers_check.md` |
| Paper 2 | `04_partB/supply_panel.py` (models) | `partB/supply_panel.txt` |
| | `replication/export_model_frames.py paper2`: runs `flows_supply_panel`, `same_dong_bound_vital`, `hd_supply_panel`, `zone_event_study`, `emp_supply`, `flows_age`, `partB_did` (models) | `partB/*.txt`, `*.csv`; `replication/data/paper2/` |
| | `04_partB/old_core_housing.py`, `same_dong_bound.py`, `supply_decomp.py` (models) | `partB/*.txt`, `*.csv` |
| | `04_partB/paper2_tables.py`, `paper2_figures.py`, `paper2_fig5.py` (models) | `paper2/tables.md`, `paper2/fig1_destinations.png` … `fig5_case_cities.png` |
| | `04_partB/paper2_numbers_check.py` | `paper2/numbers_check_pass2.csv` |
| R | `replication/R/01_replicate_paper1.R`, `02_replicate_paper2.R` | `replication/output/paper{1,2}_r_vs_python.md` |

Each step's printout is saved in `results/logs/`. The run ends with "all steps succeeded" only if every script ran,
every reported number was reproduced, and every R estimate agrees with the Python estimate (coefficients and
standard errors within 1e-6 relative, identical N; permutation p identical).

## 5. Where each result comes from

| Paper | Result | Program | Output file |
|---|---|---|---|
| 1 | Table 1 (propositions and evidence), Tables 2–5 | `paper1_tables.py` from the outputs of the model scripts | `paper1/tables.md` |
| 1 | Supplementary Tables S2–S13 | `paper1_supplement_tables.py` | `paper1/supplement_tables.md` |
| 1 | Figures 1–5 | `paper1_figures.py` | `paper1/fig1_groups.png`, `fig2_map.png`, `fig3_plan_trend.png`, `fig4_event.png`, `fig5_routes.png` |
| 1 | Numbers in the text | `check_paper1_numbers.py` lists each number, its source file and the value re-read from it | `paper1/numbers_check.md` |
| 2 | Tables 1–5 | `paper2_tables.py` | `paper2/tables.md` |
| 2 | Figures 1–4 | `paper2_figures.py` | `paper2/fig1_destinations.png`, `fig2_age_paths.png`, `fig3_zone_event.png`, `fig4_bound.png` |
| 2 | Figure 5 | `paper2_fig5.py` | `paper2/fig5_case_cities.png` |
| 2 | Numbers in the text | `paper2_numbers_check.py` | `paper2/numbers_check_pass2.csv` |
| 1, 2 | Every regression re-estimated in R | `replication/R/` | `replication/output/` |

## 6. Re-running from the raw data

With the raw data in place (folder layout in `code/paths.py` and `DATA_SOURCES.md`) and ArcGIS Pro 3.3, the
scripts run without the `models` argument rebuild the aggregates in `data/`. Order: `code/00_data`,
`01_landcover`, `02_grid`, `05_flows`, then the analysis scripts above. Each script states its inputs, outputs and
command in its header.

## 7. Licences and terms of use

| Files | Terms |
|---|---|
| `code/`, `replication/`, `run_all.py` | MIT (`LICENSE`) |
| `data_work/housing/*.csv` (KOSIS tables) | KOSIS terms of use: free use, reuse and redistribution, commercial or not, with the source stated (producer, survey, table, reference date, URL); the figures may not be altered. Source: https://kosis.kr/serviceInfo/useGuide.do |
| `outputs/partA/zoning_route_grid.csv`, `newcity_zones.csv`, `newcity_share_grid.csv` (derived from V-World polygons) | Aggregates only; the source polygons are licensed CC BY-NC-ND 4.0 by MOLIT (V-World). Reuse for non-commercial purposes with attribution to MOLIT/V-World |
| `ugm/ugm_national/supply_raw/*.csv` (KICOX) | Public data portal (data.go.kr) open data; attribution to the Korea Industrial Complex Corporation |
| All other files in `data/` (aggregates of SGIS grid and census-block statistics, MDIS migration counts, land-cover shares, boundary vertices) | Statistics derived by the authors from the sources in Section 2; CC BY 4.0 for the authors' contribution. Cite the original producers (Statistics Korea: SGIS, MDIS; Ministry of Environment: land-cover maps) when reusing them. No record refers to an individual person or household |

The raw data are not redistributed: the MDIS microdata are licensed for the registered user only, and the raw grids,
census-block files, land-cover maps and V-World polygons can be obtained free of charge from their producers.

## 8. Archiving

For review, this package is available through an anonymised link. On acceptance it will be deposited in Zenodo
(https://zenodo.org) under a DOI with the licences above, and the DOI will be cited in the data availability statement
of both papers.
