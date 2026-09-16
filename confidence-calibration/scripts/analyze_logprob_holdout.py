#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2", "scipy>=1.14"]
# ///
"""Evaluate frozen logprob/stated-confidence rules on the untouched BANKING77 holdout."""
from __future__ import annotations
import csv, json, math
from pathlib import Path
import numpy as np
from scipy.stats import rankdata
from common import DATA, BUILD, ensure_build

PLAN = DATA / "logprob-holdout-plan.json"
RESULTS = DATA / "logprob-holdout-results.csv"
plan = json.loads(PLAN.read_text())
rows = list(csv.DictReader(RESULTS.open()))
if len(rows) != plan["holdout_n"]:
    raise SystemExit(f"Expected {plan['holdout_n']} holdout rows, found {len(rows)}")
rows.sort(key=lambda r: r["id"])
y = np.array([int(r["correct"]) for r in rows], float)
p_log = np.clip(np.array([float(r["token_probability"]) for r in rows], float),0,1)
p_stated = np.array([float(r["stated_confidence"])/100 for r in rows], float)

EPS=1e-6
def logit(p):
    p=np.clip(p,EPS,1-EPS); return np.log(p/(1-p))
def sigmoid(z): return 1/(1+np.exp(-np.clip(z,-40,40)))
def apply_cal(p,ab): return sigmoid(ab[0]*logit(p)+ab[1])
def brier(p): return float(np.mean((p-y)**2))
def ece(p):
    bins=[0,.5,.6,.7,.8,.9,.95,.98,.99,1.0000001]; out=0.0
    for lo,hi in zip(bins,bins[1:]):
        m=(p>=lo)&(p<hi)
        if m.any(): out += m.mean()*abs(y[m].mean()-p[m].mean())
    return float(out)
def auc(p):
    pos=p[y==1]; neg=p[y==0]; ranks=rankdata(np.r_[pos,neg], method="average")
    n1=len(pos); n0=len(neg)
    return float((ranks[:n1].sum()-n1*(n1+1)/2)/(n1*n0))
def wilson(errors,n):
    z=1.95996398454; p=errors/n; d=1+z*z/n; c=(p+z*z/(2*n))/d
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-h), min(1,c+h)]
def frozen_rules(family,p):
    out={}
    for target in ("2","5","10"):
        rule=plan["routing_rules"][family][target]; m=p>=rule["threshold"]
        n=int(m.sum()); errors=int((1-y[m]).sum())
        out[target]={"threshold":rule["threshold"],"training_coverage":rule["coverage"],"training_risk":rule["risk"],"coverage":n/len(y),"n":n,"errors":errors,"risk":errors/n if n else None,"risk_ci95":wilson(errors,n) if n else None}
    return out

q_log=apply_cal(p_log,plan["platt"]["logprob"])
q_stated=apply_cal(p_stated,plan["platt"]["stated"])
exact_one=p_log==1.0
exact_one_n=int(exact_one.sum()); exact_one_errors=int((1-y[exact_one]).sum())
summary={
    "n":len(rows), "accuracy":float(y.mean()),
    "diagnostic_exact_one":{"n":exact_one_n,"coverage":float(exact_one_n/len(y)),"errors":exact_one_errors,"risk":float(exact_one_errors/exact_one_n) if exact_one_n else None},
    "raw":{
        "logprob":{"mean":float(p_log.mean()),"brier":brier(p_log),"ece":ece(p_log),"auroc":auc(p_log)},
        "stated":{"mean":float(p_stated.mean()),"brier":brier(p_stated),"ece":ece(p_stated),"auroc":auc(p_stated)},
    },
    "frozen_calibrated":{
        "logprob":{"mean":float(q_log.mean()),"brier":brier(q_log),"ece":ece(q_log),"auroc":auc(q_log)},
        "stated":{"mean":float(q_stated.mean()),"brier":brier(q_stated),"ece":ece(q_stated),"auroc":auc(q_stated)},
    },
    "frozen_routing":{"logprob":frozen_rules("logprob",p_log),"stated":frozen_rules("stated",p_stated)},
}
# Paired bootstrap, frozen transforms only. Negative Brier delta favors logprob.
rng=np.random.default_rng(20260916)
d=(q_log-y)**2-(q_stated-y)**2
vals=[]
for _ in range(10):
    ix=rng.integers(0,len(y),size=(1000,len(y)))
    vals.extend(d[ix].mean(axis=1))
vals=np.asarray(vals); lo,hi=np.quantile(vals,[.025,.975])
summary["paired_calibrated_brier_delta_logprob_minus_stated"]={"delta":float(d.mean()),"ci95_low":float(lo),"ci95_high":float(hi),"prob_logprob_better":float(np.mean(vals<0))}
ensure_build()
(BUILD/"logprob-holdout-summary.json").write_text(json.dumps(summary,indent=2))
with (BUILD/"logprob-holdout-summary.csv").open("w",newline="") as f:
    fields=["signal","holdout_n","accuracy","calibrated_brier","calibrated_ece","auroc","training_coverage_at_5pct","holdout_coverage_at_5pct","holdout_error_at_5pct","holdout_errors","holdout_auto_passed"]
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
    for family in ("logprob","stated"):
        m=summary["frozen_calibrated"][family]; r=summary["frozen_routing"][family]["5"]
        w.writerow({"signal":family,"holdout_n":len(rows),"accuracy":summary["accuracy"],"calibrated_brier":m["brier"],"calibrated_ece":m["ece"],"auroc":m["auroc"],"training_coverage_at_5pct":r["training_coverage"],"holdout_coverage_at_5pct":r["coverage"],"holdout_error_at_5pct":r["risk"],"holdout_errors":r["errors"],"holdout_auto_passed":r["n"]})
print(f"holdout n={len(rows)} accuracy={summary['accuracy']:.3f}")
for family in ("logprob","stated"):
    m=summary['frozen_calibrated'][family]; r=summary['frozen_routing'][family]['5']
    print(f"{family}: Brier={m['brier']:.4f} AUROC={m['auroc']:.3f} frozen-5% coverage={r['coverage']:.3f} risk={r['risk']:.3f} ({r['errors']}/{r['n']})")
b=summary['paired_calibrated_brier_delta_logprob_minus_stated']
print(f"paired calibrated Brier Δ logprob-stated={b['delta']:+.4f} 95% CI [{b['ci95_low']:+.4f},{b['ci95_high']:+.4f}]")
