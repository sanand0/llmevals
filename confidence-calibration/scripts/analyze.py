#!/usr/bin/env -S uv run --script
"""Analyze confidence calibration from CSV columns: confidence, correct."""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

Z = 1.959963984540054


def wilson(successes: int, n: int) -> tuple[float, float]:
    if not n:
        return (float("nan"), float("nan"))
    p = successes / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def pct(x: float) -> str:
    return f"{100*x:5.1f}%"


def main(path: str) -> None:
    rows = list(csv.DictReader(Path(path).open()))
    data = [(float(r["confidence"]) / 100, int(r["correct"])) for r in rows]
    n = len(data); acc = sum(y for _, y in data) / n; mean_c = sum(c for c, _ in data) / n
    brier = sum((c-y)**2 for c,y in data) / n
    print(f"n={n}  accuracy={pct(acc)}  mean confidence={pct(mean_c)}  gap={pct(mean_c-acc)}  Brier={brier:.3f}")

    print("\nFixed confidence bands")
    print("band       n   mean_conf  accuracy    95% CI accuracy   gap")
    ece = 0.0
    edges = [0,.5,.6,.7,.8,.9,1.0000001]
    for lo, hi in zip(edges, edges[1:]):
        b = [(c,y) for c,y in data if lo <= c < hi]
        if not b: continue
        bn=len(b); bc=sum(c for c,_ in b)/bn; ba=sum(y for _,y in b)/bn; ci=wilson(sum(y for _,y in b),bn)
        ece += bn/n * abs(bc-ba)
        print(f"{lo:3.0%}-{min(hi,1):3.0%} {bn:4d}   {pct(bc)}    {pct(ba)}   [{pct(ci[0])}, {pct(ci[1])}]  {pct(bc-ba)}")
    print(f"ECE (fixed bands): {ece:.3f}")

    print("\nAuto-pass threshold / risk-coverage")
    print("score>=   pass_n coverage  errors  observed_error  95% CI error")
    for t in [.50,.60,.70,.80,.85,.90,.95]:
        b=[(c,y) for c,y in data if c>=t]
        if not b: continue
        bn=len(b); errors=sum(1-y for _,y in b); ci=wilson(errors,bn)
        print(f"{t:6.0%} {bn:7d} {pct(bn/n)} {errors:7d}      {pct(errors/bn)}   [{pct(ci[0])}, {pct(ci[1])}]")

    print("\nEqual-count bands (useful if reported scores cluster)")
    ordered=sorted(data, key=lambda x:x[0])
    target=max(25, math.ceil(n/6))
    for start in range(0,n,target):
        b=ordered[start:min(n,start+target)]
        if len(b)<15 and start: continue
        bn=len(b); bc=sum(c for c,_ in b)/bn; wins=sum(y for _,y in b); ba=wins/bn; ci=wilson(wins,bn)
        print(f"{pct(b[0][0])}-{pct(b[-1][0])} n={bn:3d}: mean={pct(bc)}, actual={pct(ba)}, CI=[{pct(ci[0])},{pct(ci[1])}]")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: uv run analyze.py results.csv")
    main(sys.argv[1])
