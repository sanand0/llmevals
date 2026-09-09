#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2"]
# ///
"""Analyze full prompt variants with paired bootstrap Brier comparisons."""
from __future__ import annotations
import csv, json
import numpy as np
from common import DATA, BUILD, ensure_build

N_BOOT=20000
rng=np.random.default_rng(42)
BANDS=[(0,59),(60,69),(70,79),(80,89),(90,94),(95,97),(98,99),(100,100)]

base=[r for r in csv.DictReader((DATA/'results.csv').open()) if r['model']=='gpt-5.6-luna']
variants=list(csv.DictReader((DATA/'prompt-variant-results.csv').open()))
by_id={r['id']:r for r in base}; conds={'baseline':by_id}
for v in sorted({r['variant'] for r in variants}):
    conds[v]={r['id']:r for r in variants if r['variant']==v}
ids=sorted(by_id)
assert len(ids)==770 and all(set(d)==set(ids) for d in conds.values())

def arrays(d):
    y=np.array([int(d[i]['correct']) for i in ids],float); p=np.array([float(d[i]['confidence'])/100 for i in ids]); return y,p

def ece(y,p):
    out=0.0
    for lo,hi in BANDS:
        m=(p*100>=lo)&(p*100<=hi)
        if m.any(): out+=m.mean()*abs(y[m].mean()-p[m].mean())
    return float(out)

def metrics(d):
    y,p=arrays(d); out={'n':len(y),'accuracy':float(y.mean()),'mean_confidence':float(p.mean()),'signed_gap':float(p.mean()-y.mean()),'ece':ece(y,p),'brier':float(np.mean((p-y)**2))}
    for t in (.95,.98,.99):
        m=p>=t; k=int(t*100); out[f'coverage_{k}']=float(m.mean()); out[f'error_{k}']=float(1-y[m].mean()) if m.any() else None; out[f'n_{k}']=int(m.sum())
    return out

summary={name:metrics(d) for name,d in conds.items()}
y0,p0=arrays(conds['baseline']); base_loss=(p0-y0)**2; boot={}
for name,d in conds.items():
    if name=='baseline': continue
    y,p=arrays(d); diffs=(p-y)**2-base_loss; vals=[]
    for _ in range(N_BOOT//1000):
        ix=rng.integers(0,len(ids),size=(1000,len(ids))); vals.extend(diffs[ix].mean(axis=1))
    lo,hi=np.quantile(vals,[.025,.975]); boot[name]={'delta_brier_vs_baseline':float(diffs.mean()),'ci95_low':float(lo),'ci95_high':float(hi),'prob_better':float(np.mean(np.array(vals)<0))}

bands=[]
for name,d in conds.items():
    y,p=arrays(d)
    for lo,hi in BANDS:
        m=(p*100>=lo)&(p*100<=hi)
        if m.any(): bands.append({'variant':name,'band':f'{lo}-{hi}','lo':lo,'hi':hi,'n':int(m.sum()),'mean_stated':float(p[m].mean()),'actual_accuracy':float(y[m].mean())})

ensure_build()
(BUILD/'prompt-calibration-summary.json').write_text(json.dumps({'summary':summary,'bootstrap':boot,'bands':bands},indent=2))
fields=['variant','n','accuracy','mean_confidence','signed_gap','ece','brier','coverage_95','error_95','coverage_98','error_98','coverage_99','error_99']
with (BUILD/'prompt-calibration-summary.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
    for name,m in summary.items(): w.writerow({k:(name if k=='variant' else m.get(k)) for k in fields})
print('variant\taccuracy\tmean_conf\tgap\tECE\tBrier\tcov>=95\terr>=95\tcov>=99\terr>=99')
for name in ['baseline','uncertainty_ok','frequency_calibrated','strongest_alternative','top_two_mass']:
    m=summary[name]; print(f"{name}\t{m['accuracy']:.3f}\t{m['mean_confidence']:.3f}\t{m['signed_gap']:+.3f}\t{m['ece']:.3f}\t{m['brier']:.4f}\t{m['coverage_95']:.3f}\t{m['error_95']:.3f}\t{m['coverage_99']:.3f}\t{m['error_99']:.3f}")
print('\npaired bootstrap Brier delta vs baseline (negative=better):')
for name,b in boot.items(): print(name,b)
