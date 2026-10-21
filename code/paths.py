r"""Shared paths. Every script lives one folder below code/ and imports this module.

DATA      project folder that holds the data (outside the git repo):
          \\DS1522\data\research_data\urban_shrinkage_urban_sprawl
          Override with the USUS_DATA environment variable.
RAW       downloaded source data, kept as received (data_raw)
WORK      intermediate files: master grid, aggregated tables (data_work)
OUTPUTS   figures, tables, model results (outputs)
LOGS      script printouts (data_work\logs, not in git)
L1        previous national urban growth model project; industrial complex
          and new-city supply data are read from there, not copied
"""
import os

CODE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(CODE)
DATA = os.environ.get("USUS_DATA", os.path.dirname(REPO))
RAW = os.path.join(DATA, "data_raw")
WORK = os.path.join(DATA, "data_work")
OUTPUTS = os.path.join(DATA, "outputs")
LOGS = os.path.join(WORK, "logs")

LANDCOVER = os.path.join(RAW, "landcover_mcee")
SGIS = os.path.join(RAW, "sgis")
SUPPLY = os.path.join(RAW, "supply")

L1 = os.environ.get("UGM_DATA", r"\\DS1522\data\research_data\landcover_L1_30m_korea")
L1_SUPPLY = os.path.join(L1, "ugm_national", "supply_raw")

for _d in (WORK, OUTPUTS, LOGS):
    os.makedirs(_d, exist_ok=True)
