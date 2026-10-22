"""Export the estimation data and specification of every regression in paper 1 or paper 2 for the R replication.

The analysis scripts are run unchanged (paper 1 scripts in their "models" mode, which skips the grid rebuild).
While they run, statsmodels.formula.api.ols and .wls are wrapped so that each fitted model records
  - the formula, the covariance type (HC1, clustered or classical) and the cluster variable,
  - the estimation data: the columns named in the formula (plus the cluster variable and WLS weights), rows as passed,
  - the Python estimates (coefficient, standard error, N) of every term that is not a fixed-effect dummy.
Paper 2 also has two permutation tests (zone_event_study.py, emp_supply.py): the random placebo assignments and the
control-unit panel they are applied to are recorded as well, so that R can redo the test with the same draws.
The scripts write their usual outputs again (same numbers; check with check_paper1_numbers.py and
paper2_numbers_check.py).

Outputs (replication/data/{paper}/):
  frames/{script}_{nnn}.csv   estimation data of each model
  models.csv                  one row per model: id, script, formula, cov_type, cluster, weights, nobs
  python_estimates.csv        one row per model and term
  perm/{script}_controls.csv  paper 2: control units' panel used by the permutation test
  perm/{script}_draws.csv     paper 2: draw, SG_ID, placebo onset year
  perm/python_perm.csv        paper 2: outcome, actual coefficient and permutation p reported by the script
Run with ArcGIS Pro Python:  propy.bat replication\\export_model_frames.py paper1   (or paper2)
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
for d in ("", "03_partA", "04_partB", "05_flows"):
    sys.path.insert(0, os.path.join(CODE, d))
sys.stdout.reconfigure(encoding="utf-8")
import paths

PAPERS = {
    "paper1": {"scripts": ["shrink_sprawl", "supply_demand", "ic_unmet", "vacancy", "plan_pop", "plan_event",
                           "zoning_route"],
               "argv": ["models"], "fe": ["SG_ID", "sigun", "rp", "ry", "region"]},
    # order matters: zone_event_study writes zone_event_panel.csv, read by emp_supply and flows_age
    "paper2": {"scripts": ["flows_supply_panel", "same_dong_bound_vital", "zone_event_study", "emp_supply",
                           "flows_age", "partB_did"],
               "argv": [], "fe": ["SG_ID", "rp", "ry", "block", "oa", "year"]},
}
# permutation tests of paper 2: outcomes tested, and where the script reports the result
PERM = {"zone_event_study": ["out_zone", "out_new", "out_rest", "out_outside", "out_capital", "in_outside", "net_old",
                             "sg_in", "sg_out", "sg_net"],
        "emp_supply": ["l_emp_old", "l_comm_old", "l_comm_rel"]}

_ols, _wls, _rng = smf.ols, smf.wls, np.random.default_rng
models, ests, state = [], [], {"script": None, "k": 0, "draws": [], "controls": None}


def names_in(formula, cols):
    toks = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula))
    return [c for c in cols if c in toks]


class Recorder:
    def __init__(self, formula, data, weights=None, **kw):
        self.formula, self.data, self.weights = formula, data, weights
        self.inner = _ols(formula, data=data, **kw) if weights is None else _wls(formula, data=data, weights=weights, **kw)

    def __getattr__(self, a):
        return getattr(self.inner, a)

    def fit(self, *a, **kw):
        res = self.inner.fit(*a, **kw)
        state["k"] += 1
        mid = f"{state['script']}_{state['k']:03d}"
        cov = kw.get("cov_type", "nonrobust")
        fr = self.data[names_in(self.formula, self.data.columns)].copy()
        cl = w = ""
        if cov == "cluster":
            fr["cluster_id"] = np.asarray(kw["cov_kwds"]["groups"])
            cl = "cluster_id"
        if self.weights is not None:
            fr["w_"] = np.asarray(self.weights)
            w = "w_"
        fr.to_csv(os.path.join(state["out"], "frames", f"{mid}.csv"), index=False, encoding="utf-8")
        models.append({"id": mid, "script": state["script"], "formula": self.formula, "cov_type": cov,
                       "cluster": cl, "weights": w, "nobs": int(res.nobs)})
        for t in res.params.index:
            if state["fe_term"].match(t):
                continue
            ests.append({"id": mid, "term": t, "coef": res.params[t], "se": res.bse[t], "nobs": int(res.nobs)})
        return res


def wls(formula, data, weights, **kw):
    return Recorder(formula, data, weights=weights, **kw)


class RngRecorder:
    """Generator that logs the placebo draws (choice of control units, then the permutation of onset years)."""

    def __init__(self, *a, **kw):
        self.g = _rng(*a, **kw)
        self.pick = None

    def choice(self, *a, **kw):
        self.pick = self.g.choice(*a, **kw)
        return self.pick

    def permutation(self, *a, **kw):
        r = self.g.permutation(*a, **kw)
        state["draws"].append((self.pick, r))
        return r

    def __getattr__(self, a):
        return getattr(self.g, a)


def projector_recorder(f):
    def wrapped(df):
        state["controls"] = df.copy()
        return f(df)
    return wrapped


def python_perm(script):
    """Actual coefficient and permutation p as written by the script."""
    o = os.path.join(paths.OUTPUTS, "partB")
    if script == "zone_event_study":
        z = pd.read_csv(os.path.join(o, "zone_event_pooled.csv"))
        return pd.DataFrame({"y": z.y, "coef": z.coef, "p_perm": z.p_perm})
    txt = open(os.path.join(o, "emp_supply.txt"), encoding="utf-8").read()
    rows = re.findall(r"^\s+(l_\w+)\s+([+-][\d.]+) \(군집 SE.*?순열 p=([\d.]+)", txt, re.M)
    return pd.DataFrame(rows, columns=["y", "coef", "p_perm"]).astype({"coef": float, "p_perm": float})


def main():
    paper = sys.argv[1] if len(sys.argv) > 1 else "paper1"
    cfg = PAPERS[paper]
    out = state["out"] = os.path.join(HERE, "data", paper)
    os.makedirs(os.path.join(out, "frames"), exist_ok=True)
    state["fe_term"] = re.compile(r"^C\((" + "|".join(cfg["fe"]) + r")\)\[")
    smf.ols, smf.wls = Recorder, wls
    perm_rows = []
    for s in cfg["scripts"]:
        state.update(script=s, k=0, draws=[], controls=None)
        mod = importlib.import_module(s)
        mod.smf.ols, mod.smf.wls = Recorder, wls
        if s in PERM:
            mod.fe_projector = projector_recorder(mod.fe_projector)
            np.random.default_rng = RngRecorder
        argv = sys.argv
        sys.argv = [s + ".py"] + cfg["argv"]
        try:
            mod.main()
        finally:
            sys.argv = argv
            np.random.default_rng = _rng
        print(f"-- {s}: {state['k']} models")
        if s in PERM:
            pd_ = os.path.join(out, "perm")
            os.makedirs(pd_, exist_ok=True)
            c = state["controls"]
            c[["SG_ID", "year", "ry"] + PERM[s]].to_csv(os.path.join(pd_, f"{s}_controls.csv"), index=False,
                                                         encoding="utf-8")
            dr = pd.concat([pd.DataFrame({"draw": i + 1, "SG_ID": p, "onset": o})
                            for i, (p, o) in enumerate(state["draws"])])
            dr.to_csv(os.path.join(pd_, f"{s}_draws.csv"), index=False, encoding="utf-8")
            pp = python_perm(s)
            pp.insert(0, "script", s)
            perm_rows.append(pp)
            print(f"   permutation: {len(state['draws'])} draws, {len(c)} control rows, {len(pp)} outcomes")
    pd.DataFrame(models).to_csv(os.path.join(out, "models.csv"), index=False, encoding="utf-8")
    pd.DataFrame(ests).to_csv(os.path.join(out, "python_estimates.csv"), index=False, encoding="utf-8")
    if perm_rows:
        pd.concat(perm_rows).to_csv(os.path.join(out, "perm", "python_perm.csv"), index=False, encoding="utf-8")
    print(f"{paper}: models {len(models)}, terms {len(ests)}")


if __name__ == "__main__":
    main()
