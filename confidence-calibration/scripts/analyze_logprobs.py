#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2", "scipy>=1.14"]
# ///
"""Compare first-token logprob confidence with stated confidence on BANKING77."""
from __future__ import annotations
import csv, json, math
from collections import defaultdict
import numpy as np
from scipy.optimize import minimize
from scipy.stats import spearmanr
from common import DATA, BUILD, ensure_build

MODEL='gpt-5.6-luna'
rows=[r for r in csv.DictReader((DATA/'logprob-results.csv').open()) if r['model']==MODEL]
if len(rows)!=770: raise SystemExit(f'Expected 770 {MODEL} rows, found {len(rows)}')
ensure_build()
# Preserve stable case order for page payload and paired bootstrap.
rows.sort(key=lambda r:int(r['id'].split('-')[-1]))
y=np.array([int(r['correct']) for r in rows],float)
lp=np.array([float(r['token_logprob']) for r in rows],float)
p_log=np.clip(np.exp(lp),0,1)  # logprob is theoretically <=0; clip tiny API/numerical overshoots
p_stated=np.array([float(r['stated_confidence'])/100 for r in rows],float)

# Deterministic 2-fold split within every gold intent: 5 train / 5 test each way.
by_gold=defaultdict(list)
for i,r in enumerate(rows): by_gold[r['gold']].append(i)
fold=np.zeros(len(rows),dtype=int)
for gold,idx in by_gold.items():
    idx.sort(key=lambda i:rows[i]['id'])
    if len(idx)!=10: raise SystemExit(f'{gold}: expected 10 rows, found {len(idx)}')
    for j,i in enumerate(idx): fold[i]=j%2

EPS=1e-6
def logit(p):
    p=np.clip(p,EPS,1-EPS); return np.log(p/(1-p))
def sigmoid(z):
    return 1/(1+np.exp(-np.clip(z,-40,40)))
def fit_platt(train_p,train_y):
    x=logit(train_p)
    def loss(ab):
        a,b=ab; q=sigmoid(a*x+b)
        return -np.mean(train_y*np.log(np.clip(q,1e-12,1))+(1-train_y)*np.log(np.clip(1-q,1e-12,1)))
    res=minimize(loss,[1.0,0.0],method='L-BFGS-B',bounds=[(0,None),(None,None)])
    if not res.success: raise RuntimeError(res.message)
    return float(res.x[0]),float(res.x[1])
def crossfit(p):
    out=np.empty_like(p); params=[]
    for test_fold in (0,1):
        train=fold!=test_fold; test=~train
        a,b=fit_platt(p[train],y[train]); out[test]=sigmoid(a*logit(p[test])+b); params.append({'test_fold':test_fold,'slope':a,'intercept':b})
    return out,params

p_log_cal,log_params=crossfit(p_log)
p_stated_cal,stated_params=crossfit(p_stated)

# Fixed bins are for descriptive ECE only. Brier and risk/coverage are primary.
bins=[0,.5,.6,.7,.8,.9,.95,.98,.99,1.0000001]
def ece(p):
    out=0
    for lo,hi in zip(bins,bins[1:]):
        m=(p>=lo)&(p<hi)
        if m.any(): out += m.mean()*abs(y[m].mean()-p[m].mean())
    return float(out)
def auc(p):
    # Mann-Whitney / rank AUC without sklearn; ties get half credit.
    pos=p[y==1]; neg=p[y==0]
    total=0.0
    for v in pos: total += np.sum(v>neg)+0.5*np.sum(v==neg)
    return float(total/(len(pos)*len(neg)))
def metrics(p):
    return {'n':len(p),'accuracy':float(y.mean()),'mean_score':float(p.mean()),'gap':float(p.mean()-y.mean()),'brier':float(np.mean((p-y)**2)),'ece':ece(p),'auroc_correct':auc(p)}
def risk_curve(p):
    # Deployment can only threshold on the score itself. Keep equal scores tied:
    # every point is an actually attainable cutoff, never an arbitrary split within a tie.
    out=[]
    for threshold in np.unique(p)[::-1]:
        m=p>=threshold; n=int(m.sum()); errors=int((1-y[m]).sum())
        out.append({'coverage':float(n/len(p)),'risk':float(errors/n),'threshold':float(threshold),'n':n,'errors':errors})
    return out
def coverage_at_risk(curve,target):
    ok=[q for q in curve if q['risk']<=target]
    return max(ok,key=lambda q:q['coverage']) if ok else {'coverage':0.0,'risk':None,'threshold':None}

def reliability(p):
    out=[]
    for lo,hi in zip(bins,bins[1:]):
        m=(p>=lo)&(p<hi)
        if m.any(): out.append({'lo':lo,'hi':min(hi,1),'n':int(m.sum()),'mean_score':float(p[m].mean()),'accuracy':float(y[m].mean())})
    return out

def nines_reliability(p, family):
    """Reliability on a complementary-surprisal / 'number of nines' display scale.

    Logprobs need one-nine-wide bands because most mass is extremely close to 1.
    Stated confidence lives lower and is integer-valued, so use familiar probability
    bands there while plotting their points on the same transformed x-axis.
    """
    pc=np.clip(p,0,1)
    z=-np.log10(np.clip(1-pc,1e-6,1))
    out=[]
    if family=='logprob':
        # 90% -> 1, 99% -> 2, ..., with exact/saturated 1.0 values grouped at 6+.
        edges=[0,1,2,3,4,5,6,float('inf')]
        for lo,hi in zip(edges,edges[1:]):
            m=(z>=lo)&(z<hi)
            if m.any():
                out.append({'label':f'{lo:g}+ nines' if not np.isfinite(hi) else f'{lo:g}–{hi:g} nines','lo_nines':lo,'hi_nines':None if not np.isfinite(hi) else hi,'gap_before':False,'n':int(m.sum()),'mean_nines':float(z[m].mean()),'mean_score':float(pc[m].mean()),'accuracy':float(y[m].mean())})
    else:
        # Familiar confidence bands give useful resolution where stated scores live.
        # Exact 100% stays separate; do not draw a line across the empty 99.9... region.
        edges=[(0,.70,'<70%'),(.70,.90,'70–90%'),(.90,.95,'90–95%'),(.95,.98,'95–98%'),(.98,.99,'98–99%'),(.99,1,'99–<100%'),(1,1.0000001,'100%')]
        for lo,hi,label in edges:
            m=(pc>=lo)&(pc<hi)
            if m.any():
                out.append({'label':label,'lo_nines':float(-np.log10(max(1-lo,1e-6))),'hi_nines':float(-np.log10(max(1-min(hi,1),1e-6))),'gap_before':label=='100%','n':int(m.sum()),'mean_nines':float(z[m].mean()),'mean_score':float(pc[m].mean()),'accuracy':float(y[m].mean())})
    return out

scores={'logprob_raw':p_log,'logprob_calibrated':p_log_cal,'stated_raw':p_stated,'stated_calibrated':p_stated_cal}
# Risk-vs-coverage is a ranking metric. A monotonic Platt transform cannot improve
# the ordering, so calibrated and raw versions intentionally share the same curve.
rank_curves={'logprob':risk_curve(p_log),'stated':risk_curve(p_stated)}
curves={
    'logprob_raw':rank_curves['logprob'], 'logprob_calibrated':rank_curves['logprob'],
    'stated_raw':rank_curves['stated'], 'stated_calibrated':rank_curves['stated'],
}
summary={k:metrics(v) for k,v in scores.items()}
for k in scores:
    summary[k]['reliability']=reliability(scores[k])
    summary[k]['nines_reliability']=nines_reliability(scores[k], 'logprob' if k.startswith('logprob') else 'stated')
for k in scores:
    family='logprob' if k.startswith('logprob') else 'stated'
    summary[k]['coverage_at_risk']={str(int(t*100)):coverage_at_risk(rank_curves[family],t) for t in (.01,.02,.05,.10)}

# Paired bootstrap Brier differences: logprob minus stated; negative favors logprob.
rng=np.random.default_rng(20260916)
def boot_diff(a,b,n_boot=20000):
    d=(a-y)**2-(b-y)**2; vals=[]
    for _ in range(n_boot//1000):
        ix=rng.integers(0,len(y),size=(1000,len(y))); vals.extend(d[ix].mean(axis=1))
    vals=np.array(vals); lo,hi=np.quantile(vals,[.025,.975])
    return {'delta':float(d.mean()),'ci95_low':float(lo),'ci95_high':float(hi),'prob_logprob_better':float(np.mean(vals<0))}
bootstrap={'raw_brier_logprob_minus_stated':boot_diff(p_log,p_stated),'calibrated_brier_logprob_minus_stated':boot_diff(p_log_cal,p_stated_cal)}

corr=spearmanr(p_log,p_stated)
payload={
 'model':MODEL,'n':len(rows),'accuracy':float(y.mean()),
 'correlation':{'spearman':float(corr.statistic),'pvalue':float(corr.pvalue)},
 'saturation':{'near_one_threshold':0.999999,'near_one_n':int((p_log>=0.999999).sum()),'near_one_fraction':float((p_log>=0.999999).mean()),'near_one_errors':int(((p_log>=0.999999)&(y==0)).sum())},
 'platt':{'logprob':log_params,'stated':stated_params},
 'summary':summary,'bootstrap':bootstrap,'risk_curves':curves,
 'rows':[{'id':r['id'],'gold':r['gold'],'prediction':r['prediction'],'correct':bool(int(r['correct'])),'logprob_raw':float(p_log[i]),'logprob_calibrated':float(p_log_cal[i]),'stated_raw':float(p_stated[i]),'stated_calibrated':float(p_stated_cal[i])} for i,r in enumerate(rows)]
}
(BUILD/'logprob-summary.json').write_text(json.dumps(payload,indent=2))
fields=['score','mean_score','gap','brier','ece','auroc_correct','coverage_at_1pct_risk','coverage_at_2pct_risk','coverage_at_5pct_risk','coverage_at_10pct_risk']
with (BUILD/'logprob-summary.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for k,m in summary.items():
        w.writerow({'score':k,**{x:m[x] for x in ['mean_score','gap','brier','ece','auroc_correct']},**{f'coverage_at_{t}pct_risk':m['coverage_at_risk'][str(t)]['coverage'] for t in [1,2,5,10]}})
print('accuracy',f'{y.mean():.3f}','spearman(logprob, stated)',f'{corr.statistic:.3f}')
print('score\tmean\tgap\tBrier\tECE\tAUROC(correct)\tcov@2%\tcov@5%\tcov@10%')
for k,m in summary.items():
    c=m['coverage_at_risk'];print(f"{k}\t{m['mean_score']:.3f}\t{m['gap']:+.3f}\t{m['brier']:.4f}\t{m['ece']:.3f}\t{m['auroc_correct']:.3f}\t{c['2']['coverage']:.3f}\t{c['5']['coverage']:.3f}\t{c['10']['coverage']:.3f}")
print('bootstrap',json.dumps(bootstrap,indent=2))
print('platt',json.dumps(payload['platt'],indent=2))
