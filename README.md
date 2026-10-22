# Shrinkage sprawl and supply-led development in Korea's non-capital regions

Code and replication material for two papers on why shrinking Korean cities and counties keep building, and what the
building does:

- **Paper 1.** *Planning for growth that never comes: Permissive developmentalism and shrinkage sprawl in South
  Korea's non-capital regions.* Supply, sprawl and growth-premised master plans (code in `code/03_partA`).
- **Paper 2.** Old-core migration paths: does new housing outside the historic core drain it? (code in
  `code/04_partB`, `code/05_flows`).

## Quick replication of the regressions

The folder `replication/` re-estimates every regression of both papers in R, without the raw data or ArcGIS:

- **Paper 1:** 129 models (Tables 2–4, Figures 2–3, Supplementary Tables S4–S10).
- **Paper 2:** 198 models (Tables 3–5 and the robustness checks of Sections 5.3–5.4), plus its two permutation tests.

```
replication/
├─ data/
│  ├─ paper1/, paper2/
│  │  ├─ frames/{model id}.csv  estimation data of each model (unit-level aggregates)
│  │  ├─ models.csv             formula, standard-error type, weights and N of each model
│  │  ├─ python_estimates.csv   estimates reported in the paper (Python, statsmodels)
│  │  └─ perm/                  paper 2: control panel, the 1,000 placebo draws, reported permutation p
│  └─ CODEBOOK.md               variable definitions
├─ R/01_replicate_paper1.R      independent re-estimation in R (fixest)
├─ R/02_replicate_paper2.R      the same for paper 2, and the permutation tests
├─ R/replicate_lib.R            shared functions; renv.lock gives package versions
├─ output/                      R estimates and the comparison with the Python estimates
└─ export_model_frames.py       writes data/ from the full pipeline (needs the raw data): paper1 | paper2
```

With R 4.4 and the packages in `replication/R/renv.lock` (`fixest`, `data.table`):

```
Rscript replication/R/01_replicate_paper1.R
Rscript replication/R/02_replicate_paper2.R
```

The scripts write `replication/output/paper1_r_vs_python.md` and `paper2_r_vs_python.md`. In the current version every
estimated term agrees with the published estimates (coefficients, standard errors and N):

- paper 1: 687 terms, largest difference 1.6e-11;
- paper 2: 877 terms, largest difference 2.8e-8.

The permutation p of all 13 outcomes of paper 2 is the same in R, using the placebo draws made in Python.

Reported standard errors are clustered by unit or heteroskedasticity-robust (HC1). They keep singleton observations and
count fixed-effect dummies as parameters. The comparison files also give fixest's default standard errors, which are
equal or smaller.

## Full pipeline

The full pipeline starts from the raw data (not redistributable; see *Data* below) and runs with the ArcGIS Pro 3.3
Python environment (Python 3.11; package versions in `requirements.txt`). `arcpy` with Spatial Analyst is needed only
for the rasterisation steps (`code/01_*`, `code/02_*`). Every script states its inputs, outputs and command in its
header.

```
"C:\Program Files\ArcGIS\Pro\bin\Python\scripts\propy.bat" code\03_partA\shrink_sprawl.py
```

Data locations are set in `code/paths.py`: the data folder is the parent of this repository unless the environment
variable `USUS_DATA` points elsewhere (`UGM_DATA` for the earlier national land-cover project that holds the
industrial-complex files). Raw data go to `data_raw/`, intermediate files to `data_work/`, results to `outputs/`.

| Step | Folder | Scripts (in order) |
|---|---|---|
| 0 | `code/00_data` | `fetch_kosis_housing.py` (KOSIS API), `organize_sgis_*.py`, `organize_vworld_*.py` |
| 1 | `code/01_landcover` | `unzip_l2.py`, `merge_l2.py`, `unzip_l3.py` |
| 2 | `code/02_grid` | `sigun.py`, `grid_lc_share.py`, `grid_sgis.py`, `check_sgis.py`, `supply_zones.py`, `grid_zoning.py`, `grid_industry.py` |
| 3 | `code/05_flows` | `build_mdis_db.py`, `check_mdis_db.py`, `dong_xwalk.py`, `dong_class.py`, `flows_old_core_mdis.py`, `zone_pop.py` |
| 4 | `code/04_partB` (shared panels) | `supply_panel.py`, `flows_supply_panel.py`, `zone_event_study.py`, `emp_supply.py` (its `emp_sigun_year.csv` is also used by paper 1) |
| 5 | `code/03_partA` (paper 1) | `regpop.py`, `sigun_panel.py`, `supply_demand.py`, `shrink_sprawl.py`, `ic_unmet.py`, `vacancy.py`, `plan_pop.py`, `plan_event.py`, `zoning_route.py` |
| 6 | `code/04_partB` (paper 2) | `old_core_housing.py`, `flows_age.py`, `same_dong_bound.py`, `same_dong_bound_vital.py`, `partB_did.py`, `supply_decomp.py` |
| 7 | outputs | paper 1: `paper1_tables.py`, `paper1_supplement_tables.py`, `paper1_figures.py`, `check_paper1_numbers.py`; paper 2: `paper2_tables.py`, `paper2_figures.py`, `paper2_numbers_check.py` |

Paper 1 model scripts accept the argument `models` to skip rebuilding grids from raw data. `check_paper1_numbers.py` and
`paper2_numbers_check.py` re-read every number of the manuscripts from the output files (the manuscripts themselves are not part of the public repository).

## Data

All sources are listed, with table identifiers, editions and download dates, in `DATA_SOURCES.md` (in Korean) and in
Supplementary Table S1 of paper 1. Main sources: national land-cover maps (Ministry of Environment); SGIS 100 m grid
statistics (Statistics Korea); KOSIS tables of registered population, vacancy, unsold housing and urban planning
(DT_1B040A3, DT_1JU0512, DT_1JU1012, DT_1JU1512, DT_MLTM_2082, TX_315_2009_H1004, H1004A, H1440, H1443, H1100);
MDIS internal-migration microdata (Statistics Korea); V-World zoning polygons (MOLIT); industrial-complex data
(KRIHS, KICOX).

Raw data are not included. Most can be obtained free of charge from the producers (KOSIS through its open API, SGIS
and MDIS after registration). The MDIS microdata may not be redistributed; the replication data contain only
unit-level aggregates. API keys are read from files outside the repository and are never stored here.

## License

Code: MIT (see `LICENSE`). Derived data remain subject to the terms of their sources.
