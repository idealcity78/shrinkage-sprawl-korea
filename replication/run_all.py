"""Reproduce every table, figure and reported number of papers 1 and 2 from the analysis data in data/.

The script copies data/ to a fresh results/ folder, points the analysis code at it (USUS_DATA), runs the analysis
scripts in their "models" mode (no raw data, grids or ArcGIS needed), then
  1. compares every number reported in the papers with the new outputs (check_paper1_numbers.py,
     paper2_numbers_check.py; 179 + 152 values),
  2. re-estimates every regression in R (replication/R, if Rscript is found) and compares the R estimates with the
     Python estimates.
A log of each step goes to results/logs/. Exit status 1 if any step fails or any number differs.

Usage:  python run_all.py            (all steps)
        python run_all.py --no-r     (skip the R step)
"""
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(ROOT, "code")
DATA = os.path.join(ROOT, "data")
RES = os.path.join(ROOT, "results")
LOGS = os.path.join(RES, "logs")
EXPORT = os.path.join(ROOT, "replication", "export_model_frames.py")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PAPER1 = [("03_partA/regpop.py", []),
          (EXPORT, ["paper1"]),          # supply_demand, shrink_sprawl, ic_unmet, hd_unmet, vacancy, plan_pop, plan_event, zoning_route, robust_review
          ("03_partA/newcity_share.py", ["models"]),
          ("03_partA/zoning_route_robust.py", ["models"]),
          ("03_partA/paper1_supplement_tables.py", []),
          ("03_partA/paper1_tables.py", []),
          ("03_partA/paper1_figures.py", ["models"]),
          ("03_partA/check_paper1_numbers.py", [])]
PAPER2 = [("04_partB/supply_panel.py", ["models"]),
          (EXPORT, ["paper2"]),          # flows_supply_panel, same_dong_bound_vital, hd_supply_panel, zone_event_study, emp_supply, flows_age, partB_did
          ("04_partB/old_core_housing.py", ["models"]),
          ("04_partB/same_dong_bound.py", ["models"]),
          ("04_partB/supply_decomp.py", ["models"]),
          ("04_partB/paper2_tables.py", []),
          ("04_partB/paper2_figures.py", []),
          ("04_partB/paper2_fig5.py", ["models"]),
          ("04_partB/paper2_numbers_check.py", [])]
R_SCRIPTS = ["01_replicate_paper1.R", "02_replicate_paper2.R"]


def run(cmd, log, env):
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        r = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env, cwd=ROOT)
    tail = open(log, encoding="utf-8", errors="replace").read().strip().splitlines()[-1:] or [""]
    print(f"  {'ok ' if r.returncode == 0 else 'FAIL'} {os.path.basename(cmd[-1] if cmd[-1].endswith(('.py', '.R')) else cmd[1])}"
          f" {' '.join(a for a in cmd[2:] if not a.endswith(('.py', '.R')))}  ({time.time() - t0:.0f} s)  {tail[0][:90]}")
    return r.returncode == 0


def main():
    if os.path.exists(RES):
        shutil.rmtree(RES)
    shutil.copytree(DATA, RES)
    os.makedirs(LOGS, exist_ok=True)
    env = dict(os.environ, USUS_DATA=RES, UGM_DATA=os.path.join(RES, "ugm"), PYTHONIOENCODING="utf-8",
               MPLBACKEND="Agg")
    ok = True
    for paper, steps in (("paper 1", PAPER1), ("paper 2", PAPER2)):
        print(paper)
        for i, (script, args) in enumerate(steps, 1):
            path = script if os.path.isabs(script) else os.path.join(CODE, script)
            name = os.path.splitext(os.path.basename(path))[0]
            log = os.path.join(LOGS, f"{paper[-1]}_{i:02d}_{name}{'_' + args[0] if args and args[0] != 'models' else ''}.txt")
            ok &= run([sys.executable, path] + args, log, env)
    if "--no-r" not in sys.argv:
        rscript = shutil.which("Rscript")
        print("R")
        if rscript is None:
            print("  Rscript not found: R step skipped")
        for s in R_SCRIPTS if rscript else []:
            ok &= run([rscript, os.path.join(ROOT, "replication", "R", s)], os.path.join(LOGS, f"R_{s[:-2]}.txt"), env)
    print("all steps succeeded" if ok else "SOME STEPS FAILED: see results/logs/")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
