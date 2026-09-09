#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2"]
# ///
"""Analyze the paired 0/500/2,000-word input-length stress test."""
from __future__ import annotations
import csv, json
import numpy as np
from common import DATA, BUILD, ensure_build

CONDITIONS=['short','medium','long']; PADDING={'short':0,'medium':500,'long':2000}; BANDS=[(0,59),(60,69),(70,79),(80,89),(90,94),(95,97),(98,99),(100,100)]
rng=np.random.default_rng(20260909); N_BOOT=10000
rows=list(csv.DictReader((DATA/'input-length-results.csv').open())); models=sorted({r['model'] for r in rows})
grouped={(m,c):[r for r in rows if r['model']==m and r['condition']==c] for m in models for c in CONDITIONS}
ids=None
for key,rr in grouped.items():
    got={r['id'] for r in rr}
    if len(got)!=len(rr): raise SystemExit(f'Duplicate IDs in {key}')
    ids=got if ids is None else ids
    if got!=ids: raise SystemExit(f'Conditions do not cover identical IDs: {key}')
if len(ids or [])!=770: raise SystemExit(f'Expected 770 paired cases, found {len(ids or [])}')

def metrics(rr):
    y=np.array([int(r['correct']) for r in rr],float); p=np.array([float(r['confidence'])/100 for r in rr]); ece=0.0
    for lo,hi in BANDS:
        m=(p*100>=lo)&(p*100<=hi)
        if m.any(): ece+=m.mean()*abs(y[m].mean()-p[m].mean())
    out={'n':len(rr),'accuracy':float(y.mean()),'mean_confidence':float(p.mean()),'gap':float(p.mean()-y.mean()),'ece':float(ece),'brier':float(np.mean((p-y)**2))}
    for t in (95,98,99):
        m=p>=t/100; out[f'coverage_{t}']=float(m.mean()); out[f'error_{t}']=float(1-y[m].mean()) if m.any() else None; out[f'n_{t}']=int(m.sum())
    return out
summary={m:{c:metrics(grouped[m,c]) for c in CONDITIONS} for m in models}
paired={}; ordered_ids=sorted(ids)
for model in models:
    by={c:{r['id']:r for r in grouped[model,c]} for c in CONDITIONS}; paired[model]={}
    for c in ('medium','long'):
        arrays={}
        for metric in ('confidence','accuracy','brier'):
            vals=[]
            for i in ordered_ids:
                a,b=by['short'][i],by[c][i]; ya,yb=int(a['correct']),int(b['correct']); pa,pb=float(a['confidence'])/100,float(b['confidence'])/100
                vals.append({'confidence':pb-pa,'accuracy':yb-ya,'brier':(pb-yb)**2-(pa-ya)**2}[metric])
            arr=np.array(vals); ix=rng.integers(0,len(arr),size=(N_BOOT,len(arr))); means=arr[ix].mean(axis=1); lo,hi=np.quantile(means,[.025,.975]); arrays[metric]={'delta':float(arr.mean()),'ci95_low':float(lo),'ci95_high':float(hi)}
        paired[model][c]=arrays
natural={}
for model in models:
    rr=grouped[model,'short']; words=np.array([int(r['request_words']) for r in rr]); conf=np.array([float(r['confidence'])/100 for r in rr]); corr=np.array([int(r['correct']) for r in rr])
    cuts=[0,7,9,12,10**9]; quart=[]
    for j in range(4):
        m=(words>=cuts[j])&(words<cuts[j+1]); quart.append({'label':['3–6 words','7–8 words','9–11 words','12+ words'][j],'n':int(m.sum()),'accuracy':float(corr[m].mean()),'mean_confidence':float(conf[m].mean())})
    natural[model]={'quartiles':quart}
payload={'case_count':len(ids),'conditions':[{'key':c,'padding_words':PADDING[c]} for c in CONDITIONS],'models':models,'summary':summary,'paired_vs_short':paired,'natural_request_length':natural}
ensure_build(); (BUILD/'input-length-summary.json').write_text(json.dumps(payload,indent=2))
fields=['model','condition','padding_words','n','accuracy','mean_confidence','gap','ece','brier','coverage_95','error_95','coverage_99','error_99']
with (BUILD/'input-length-summary.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
    for m in models:
        for c in CONDITIONS:
            z=summary[m][c]; w.writerow({'model':m,'condition':c,'padding_words':PADDING[c],**{k:z[k] for k in fields if k not in ('model','condition','padding_words')}})
print('model condition accuracy mean_conf gap Brier ΔBrier-vs-short [95% CI]')
for m in models:
    for c in CONDITIONS:
        z=summary[m][c]; extra=''
        if c!='short':
            d=paired[m][c]['brier']; extra=f" {d['delta']:+.4f} [{d['ci95_low']:+.4f},{d['ci95_high']:+.4f}]"
        print(f"{m} {c:6} {z['accuracy']:.3f} {z['mean_confidence']:.3f} {z['gap']:+.3f} {z['brier']:.4f}{extra}")
