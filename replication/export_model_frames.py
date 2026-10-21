"""Export the estimation data and specification of every regression in paper 1 for the R replication.

The analysis scripts of code/03_partA are run unchanged in their "models" mode (no grid rebuild). While they run,
statsmodels.formula.api.ols is wrapped so that each fitted model records
  - the formula, the covariance type (HC1 or clustered) and the cluster variable,
  - the estimation data: the columns named in the formula (plus the cluster variable), rows as passed,
  - the Python estimates (coefficient, standard error, N) of every term that is not a fixed-effect dummy.
The scripts write their usual outputs again (same numbers; check with code/03_partA/check_paper1_numbers.py).

Outputs (replication/data/):
  frames/{script}_{nnn}.csv   estimation data of each model
  models.csv                  one row per model: id, script, formula, cov_type, cluster, nobs
  python_estimates.csv        one row per model and term
Run with ArcGIS Pro Python:  propy.bat replication\\export_model_frames.py
"""
import importlib
import os
import re
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(os.path.dirname(HERE), "code")
sys.path.insert(0, CODE)
sys.path.insert(0, os.path.join(CODE, "03_partA"))
sys.stdout.reconfigure(encoding="utf-8")

OUT = os.path.join(HERE, "data")
FR = os.path.join(OUT, "frames")
os.makedirs(FR, exist_ok=True)
SCRIPTS = ["shrink_sprawl", "supply_demand", "ic_unmet", "vacancy", "plan_pop", "plan_event", "zoning_route"]
FE_TERM = re.compile(r"^C\((SG_ID|sigun|rp|ry|region)\)\[")       # dummies absorbed as fixed effects in R

_ols = smf.ols
models, ests, state = [], [], {"script": None, "k": 0}


def names_in(formula, cols):
    toks = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula))
    return [c for c in cols if c in toks]


class Recorder:
    def __init__(self, formula, data, **kw):
        self.formula, self.data, self.kw = formula, data, kw
        self.inner = _ols(formula, data=data, **kw)

    def __getattr__(self, a):
        return getattr(self.inner, a)

    def fit(self, *a, **kw):
        res = self.inner.fit(*a, **kw)
        state["k"] += 1
        mid = f"{state['script']}_{state['k']:03d}"
        cov = kw.get("cov_type", "nonrobust")
        cols = names_in(self.formula, self.data.columns)
        fr = self.data[cols].copy()
        cl = ""
        if cov == "cluster":
            g = np.asarray(kw["cov_kwds"]["groups"])
            fr["cluster_id"] = g
            cl = "cluster_id"
        fr.to_csv(os.path.join(FR, f"{mid}.csv"), index=False, encoding="utf-8")
        models.append({"id": mid, "script": state["script"], "formula": self.formula, "cov_type": cov,
                       "cluster": cl, "nobs": int(res.nobs)})
        for t in res.params.index:
            if FE_TERM.match(t):
                continue
            ests.append({"id": mid, "term": t, "coef": res.params[t], "se": res.bse[t], "nobs": int(res.nobs)})
        return res


def main():
    smf.ols = Recorder
    for s in SCRIPTS:
        state["script"], state["k"] = s, 0
        mod = importlib.import_module(s)
        mod.smf.ols = Recorder
        argv = sys.argv
        sys.argv = [s + ".py", "models"]
        try:
            mod.main()
        finally:
            sys.argv = argv
        print(f"-- {s}: {state['k']} models")
    pd.DataFrame(models).to_csv(os.path.join(OUT, "models.csv"), index=False, encoding="utf-8")
    pd.DataFrame(ests).to_csv(os.path.join(OUT, "python_estimates.csv"), index=False, encoding="utf-8")
    print(f"models {len(models)}, terms {len(ests)}")


if __name__ == "__main__":
    main()
