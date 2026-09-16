#!/usr/bin/env -S uv run --script
"""Build GitHub Pages assets directly into confidence-calibration/."""
from __future__ import annotations

import csv
import json
import math
import shutil
from collections import Counter

from common import ROOT, DATA, BUILD, SRC
from prompt_fragments import BASELINE, FULL_VARIANTS, SCREEN_VARIANTS

PROMPT_META = {
    "uncertainty_ok": {"label": "Okay to be uncertain", "short": "Explicitly permit uncertainty instead of defaulting high.", "fragment": FULL_VARIANTS["uncertainty_ok"]},
    "frequency_calibrated": {"label": "Long-run frequency", "short": "Define X% as X correct out of 100 similar cases.", "fragment": FULL_VARIANTS["frequency_calibrated"]},
    "strongest_alternative": {"label": "Strongest alternative", "short": "Consider the closest competing label before scoring.", "fragment": FULL_VARIANTS["strongest_alternative"]},
    "top_two_mass": {"label": "Top-two probability", "short": "Allocate probability across plausible labels, then report the winner's share.", "fragment": FULL_VARIANTS["top_two_mass"]},
}
SCREEN_META = {
    "anchored_scale": {"label": "Anchored scale", "short": "Give concrete meanings to 50%, 70%, 85%, 95%, and 99%.", "fragment": SCREEN_VARIANTS["anchored_scale"]},
    "top_two_mass": {"label": "Top-two probability", "short": "Allocate probability across the most plausible labels first.", "fragment": SCREEN_VARIANTS["top_two_mass"]},
    "independent_recheck": {"label": "Independent recheck", "short": "Choose a label, then score it as a fresh second judgment.", "fragment": SCREEN_VARIANTS["independent_recheck"]},
    "evidence_balance": {"label": "Evidence balance", "short": "Weigh discriminating evidence against remaining ambiguity.", "fragment": SCREEN_VARIANTS["evidence_balance"]},
    "proper_score": {"label": "Proper scoring rule", "short": "Say the probability will be judged with a proper scoring rule.", "fragment": SCREEN_VARIANTS["proper_score"]},
}


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="") as f:
        return list(csv.DictReader(f))


def metrics(rows: list[dict[str, str]]) -> dict[str, float | int | None]:
    if not rows: return {"n": 0}
    correct=[int(r["correct"]) for r in rows]; probs=[float(r["confidence"])/100 for r in rows]
    passed=[(y,p) for y,p in zip(correct,probs) if p>=.95]
    return {"n":len(rows),"accuracy":sum(correct)/len(rows),"mean_confidence":sum(probs)/len(rows),"brier":sum((p-y)**2 for y,p in zip(correct,probs))/len(rows),"coverage_95":len(passed)/len(rows),"error_95":sum(1-y for y,_ in passed)/len(passed) if passed else None}


def main() -> None:
    cases=read_csv("banking77-sample.csv"); case_by_id={r["id"]:r for r in cases}
    if len(case_by_id)!=len(cases): raise SystemExit("Duplicate IDs in banking77-sample.csv")

    results=read_csv("results.csv"); seen=set()
    for row in results:
        key=(row["model"],row["id"])
        if key in seen: raise SystemExit(f"Duplicate result: {key}")
        seen.add(key); case=case_by_id.get(row["id"])
        if not case: raise SystemExit(f"Result ID missing from sample: {row['id']}")
        if row["gold"]!=case["category"]: raise SystemExit(f"Gold mismatch for {row['id']}")

    prompt_rows=read_csv("prompt-variant-results.csv"); prompt_seen=set()
    for row in prompt_rows:
        key=(row["variant"],row["id"])
        if key in prompt_seen: raise SystemExit(f"Duplicate prompt result: {key}")
        prompt_seen.add(key)
        if row["id"] not in case_by_id: raise SystemExit(f"Prompt result ID missing from sample: {row['id']}")

    screen_rows=read_csv("prompt-screen-results.csv"); screen_ids={r["id"] for r in screen_rows}
    luna_screen=[r for r in results if r["model"]=="gpt-5.6-luna" and r["id"] in screen_ids]
    screen_summary={"baseline":{"label":"Baseline","short":"Original confidence request.","fragment":BASELINE,**metrics(luna_screen)}}
    for variant in sorted(SCREEN_META):
        screen_summary[variant]={**SCREEN_META[variant],**metrics([r for r in screen_rows if r["variant"]==variant])}

    length_summary=json.loads((BUILD/"input-length-summary.json").read_text())
    logprob_full=json.loads((BUILD/"logprob-summary.json").read_text())
    logprob_holdout=json.loads((BUILD/"logprob-holdout-summary.json").read_text())

    # Descriptive accuracy-vs-score chart: pool development + prospective holdout only
    # after the frozen holdout evaluation. This pooled view never feeds threshold selection.
    combined_logprob_rows=read_csv("logprob-results.csv") + read_csv("logprob-holdout-results.csv")
    if len(combined_logprob_rows) != 3080:
        raise SystemExit(f"Expected 3080 combined logprob rows, found {len(combined_logprob_rows)}")
    def nines(p: float) -> float:
        p=min(1.0,max(0.0,p))
        return -math.log10(max(1-p,1e-6))
    def chart_reliability(family: str):
        if family == "logprob":
            vals=[(min(1.0,max(0.0,math.exp(float(r["token_logprob"])))),int(r["correct"])) for r in combined_logprob_rows]
            bands=[("<90%",0,.9,False),("90–99%",.9,.99,False),("99–99.9%",.99,.999,False),("99.9–99.99%",.999,.9999,False),("99.99–99.999%",.9999,.99999,False),("99.999–99.9999%",.99999,.999999,False),("≥99.9999%",.999999,1.0000001,False)]
        else:
            vals=[(float(r["stated_confidence"])/100,int(r["correct"])) for r in combined_logprob_rows]
            bands=[("<70%",0,.70,False),("70–90%",.70,.90,False),("90–95%",.90,.95,False),("95–98%",.95,.98,False),("98–99%",.98,.99,False),("99–<100%",.99,1.0,False),("100%",1.0,1.0000001,True)]
        out=[]
        for label,lo,hi,gap_before in bands:
            bucket=[(score,correct) for score,correct in vals if lo <= score < hi]
            if not bucket: continue
            scores=[q[0] for q in bucket]; correct=[q[1] for q in bucket]; accuracy=sum(correct)/len(correct)
            out.append({"label":label,"n":len(bucket),"mean_score":sum(scores)/len(scores),"mean_nines":sum(nines(q) for q in scores)/len(scores),"accuracy":accuracy,"accuracy_nines":nines(accuracy),"gap_before":gap_before})
        return out
    combined_reliability={"n":len(combined_logprob_rows),"logprob":chart_reliability("logprob"),"stated":chart_reliability("stated")}
    # Page needs derived metrics and attainable-threshold curves, not all 770 per-row records.
    # There are only ~200 unique logprob thresholds, so keep every point; thinning could hide a cutoff.
    logprob_summary={
        "model":logprob_full["model"], "n":logprob_full["n"], "accuracy":logprob_full["accuracy"],
        "correlation":logprob_full["correlation"], "saturation":logprob_full["saturation"],
        "summary":logprob_full["summary"], "bootstrap":logprob_full["bootstrap"], "holdout":logprob_holdout,
        "combined_reliability":combined_reliability,
        "risk_curves":{
            "logprob":logprob_full["risk_curves"]["logprob_raw"],
            "stated":logprob_full["risk_curves"]["stated_raw"],
        },
    }
    models=sorted({r["model"] for r in results}); label_counts=Counter(r["category"] for r in cases); variants=sorted({r["variant"] for r in prompt_rows})
    payload={
        "source":{"name":"BANKING77","case_count":len(cases),"label_count":len(label_counts),"min_per_label":min(label_counts.values()),"max_per_label":max(label_counts.values())},
        "models":models,
        "cases":[{"id":r["id"],"text":r["text"],"gold":r["category"]} for r in cases],
        "results":[{"model":r["model"],"id":r["id"],"prediction":r["prediction"],"confidence":int(r["confidence"]),"correct":bool(int(r["correct"]))} for r in results],
        "prompt_experiment":{
            "model":"gpt-5.6-luna",
            "baseline":{"label":"Baseline","short":"Original request for a probability of exact correctness.","fragment":BASELINE},
            "variants":{v:PROMPT_META.get(v,{"label":v.replace("_"," ").title(),"short":""}) for v in variants},
            "results":[{"variant":r["variant"],"id":r["id"],"prediction":r["prediction"],"confidence":int(r["confidence"]),"correct":bool(int(r["correct"]))} for r in prompt_rows],
            "screen":{"case_count":len(screen_ids),"variants":screen_summary},
        },
        "input_length_experiment":length_summary,
        "logprob_experiment":logprob_summary,
    }

    shutil.copy2(SRC/"index.html", ROOT/"index.html")
    (ROOT/"data.json").write_text(json.dumps(payload,separators=(",", ":")))

    with (ROOT/"results.csv").open("w",newline="") as f:
        fields=["task","model","id","gold","prediction","confidence","correct"]
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows({k:r[k] for k in fields} for r in results)
    for name in ["banking77-sample.csv","prompt-variant-results.csv","prompt-screen-results.csv","input-length-results.csv","logprob-results.csv","logprob-holdout-results.csv"]:
        shutil.copy2(DATA/name,ROOT/name)
    shutil.copy2(BUILD/"prompt-calibration-summary.csv",ROOT/"prompt-calibration-summary.csv")
    shutil.copy2(BUILD/"input-length-summary.csv",ROOT/"input-length-summary.csv")
    shutil.copy2(BUILD/"logprob-summary.csv",ROOT/"logprob-summary.csv")
    shutil.copy2(BUILD/"logprob-holdout-summary.csv",ROOT/"logprob-holdout-summary.csv")

    counts=Counter(r["model"] for r in results); prompt_counts=Counter(r["variant"] for r in prompt_rows)
    print(f"Built Pages assets in {ROOT} with {len(cases)} BANKING77 cases and {len(results)} base results")
    for model in models: print(f"  {model}: {counts[model]} results")
    print("Prompt variants:")
    for variant in variants: print(f"  {variant}: {prompt_counts[variant]} results")
    print(f"Prompt screen: {len(screen_ids)} cases × {len(SCREEN_META)} new variants")
    print(f"Input length: {length_summary['case_count']} cases × {len(length_summary['models'])} models × {len(length_summary['conditions'])} conditions")
    print(f"Logprobs: {logprob_summary['n']} paired {logprob_summary['model']} cases + {logprob_holdout['n']} prospective holdout cases")

if __name__=="__main__": main()
