#!/usr/bin/env -S uv run --script
"""Build GitHub Pages assets directly into confidence-calibration/."""
from __future__ import annotations

import csv
import json
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
    }

    shutil.copy2(SRC/"index.html", ROOT/"index.html")
    (ROOT/"data.json").write_text(json.dumps(payload,separators=(",", ":")))

    with (ROOT/"results.csv").open("w",newline="") as f:
        fields=["task","model","id","gold","prediction","confidence","correct"]
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows({k:r[k] for k in fields} for r in results)
    for name in ["banking77-sample.csv","prompt-variant-results.csv","prompt-screen-results.csv","input-length-results.csv"]:
        shutil.copy2(DATA/name,ROOT/name)
    shutil.copy2(BUILD/"prompt-calibration-summary.csv",ROOT/"prompt-calibration-summary.csv")
    shutil.copy2(BUILD/"input-length-summary.csv",ROOT/"input-length-summary.csv")

    counts=Counter(r["model"] for r in results); prompt_counts=Counter(r["variant"] for r in prompt_rows)
    print(f"Built Pages assets in {ROOT} with {len(cases)} BANKING77 cases and {len(results)} base results")
    for model in models: print(f"  {model}: {counts[model]} results")
    print("Prompt variants:")
    for variant in variants: print(f"  {variant}: {prompt_counts[variant]} results")
    print(f"Prompt screen: {len(screen_ids)} cases × {len(SCREEN_META)} new variants")
    print(f"Input length: {length_summary['case_count']} cases × {len(length_summary['models'])} models × {len(length_summary['conditions'])} conditions")

if __name__=="__main__": main()
