#!/usr/bin/env -S uv run --script
"""Prepare or extend the deterministic balanced BANKING77 sample."""
from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict

from common import DATA

SEED = 20260909


def stable_rank(row: dict[str, str]) -> str:
    key = f"{SEED}\0{row['category']}\0{row['text']}".encode()
    return hashlib.sha256(key).hexdigest()


def prepare_banking77(per_label: int = 10) -> None:
    source = list(csv.DictReader((DATA / "banking77-test.csv").open()))
    by_label: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source:
        by_label[row["category"]].append(row)
    maximum = min(map(len, by_label.values()))
    if not 1 <= per_label <= maximum:
        raise SystemExit(f"--per-label must be 1..{maximum}")

    path = DATA / "banking77-sample.csv"
    existing = list(csv.DictReader(path.open())) if path.exists() else []
    current = Counter(r["category"] for r in existing)
    if existing and any(n > per_label for n in current.values()):
        print(f"banking77-sample.csv already has up to {max(current.values())} per label; not shrinking")
        return

    selected = {(r["category"], r["text"]) for r in existing}
    next_id = 1 + max((int(r["id"].split("-")[-1]) for r in existing), default=0)
    added = []
    for label in sorted(by_label):
        need = per_label - current[label]
        candidates = [r for r in by_label[label] if (label, r["text"]) not in selected]
        candidates.sort(key=stable_rank)
        for row in candidates[:need]:
            added.append({"id": f"banking-{next_id:03d}", **row})
            next_id += 1

    sample = [*existing, *added]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "text", "category"])
        writer.writeheader(); writer.writerows(sample)
    counts = Counter(r["category"] for r in sample)
    print(f"banking77-sample.csv: {len(sample)} rows, {len(counts)} labels, {min(counts.values())}-{max(counts.values())} per label; added {len(added)}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--per-label", type=int, default=10, help="cases per intent; only grows an existing sample")
    args = p.parse_args()
    prepare_banking77(args.per_label)


if __name__ == "__main__":
    main()
