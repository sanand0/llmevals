#!/usr/bin/env python3
"""Freeze a reproducible 100-case FinQA reasoning benchmark."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import random
import re
import urllib.request
from pathlib import Path

SOURCE_REPO = "https://github.com/czyssrs/FinQA"
SOURCE_SHA = "0f16e2867befa6840783e58be38c9efb9229d742"
SOURCE_URL = f"https://raw.githubusercontent.com/czyssrs/FinQA/{SOURCE_SHA}/dataset/test.json"
SEED = 20260929
N_CASES = 100
OP_RE = re.compile(r"([a-z_]+)\(")
NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def largest_remainder(weights: dict[str, float], total: int) -> dict[str, int]:
    raw = {k: total * w / sum(weights.values()) for k, w in weights.items()}
    out = {k: int(math.floor(v)) for k, v in raw.items()}
    left = total - sum(out.values())
    order = sorted(raw, key=lambda k: (-(raw[k] - out[k]), k))
    for k in order[:left]:
        out[k] += 1
    return out


def allocate_with_minimum(
    counts: dict[str, int], total: int, minimum_one: bool = True
) -> dict[str, int]:
    nonempty = {k: v for k, v in counts.items() if v > 0}
    if not nonempty:
        return {}
    base = {k: 0 for k in nonempty}
    remaining = total
    if minimum_one and total >= len(nonempty):
        for k in base:
            base[k] = 1
        remaining -= len(nonempty)
    if remaining:
        extra = largest_remainder({k: float(v) for k, v in nonempty.items()}, remaining)
        for k, v in extra.items():
            base[k] += v
    return base


def step_bucket(n: int) -> str:
    return "3+" if n >= 3 else str(n)


def load_source(path: str | None) -> tuple[list[dict], bytes]:
    if path:
        raw = Path(path).read_bytes()
    else:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
            raw = response.read()
    return json.loads(raw), raw


def case_metadata(item: dict) -> tuple[str, int, str]:
    ops = OP_RE.findall(item["qa"]["program"])
    if not ops:
        raise ValueError(f"No operations in {item['id']}")
    return ops[-1], len(ops), step_bucket(len(ops))


def display_answer_matches_execution(qa: dict) -> bool:
    """Reject records whose published answer and executable result disagree."""
    display = str(qa.get("answer", "")).strip().lower()
    exe = qa.get("exe_ans")
    if not display:
        return False
    if display in {"yes", "no"}:
        return str(exe).strip().lower() == display
    if not isinstance(exe, (int, float)):
        return False

    match = NUM_RE.search(display.replace("$", ""))
    if not match:
        return False
    token = match.group(0).replace(",", "")
    value = float(token)
    decimals = len(token.split(".", 1)[1]) if "." in token else 0
    tolerance = 0.5 * (10 ** (-decimals)) + 1e-9

    executable_candidates = [float(exe)]
    if "%" in display:
        executable_candidates.append(float(exe) * 100.0)
    return any(abs(value - candidate) <= tolerance for candidate in executable_candidates)


def select_cases(items: list[dict]) -> tuple[list[dict], dict]:
    root_groups: dict[str, list[dict]] = collections.defaultdict(list)
    metadata = {}
    excluded = []
    full_root_counts = collections.Counter()
    for item in items:
        root_op, n_steps, bucket = case_metadata(item)
        full_root_counts[root_op] += 1
        metadata[item["id"]] = (root_op, n_steps, bucket)
        if not display_answer_matches_execution(item["qa"]):
            excluded.append(item["id"])
            continue
        root_groups[root_op].append(item)

    root_counts = {k: len(v) for k, v in root_groups.items()}
    # Sqrt-frequency sampling keeps common operations common while making rare
    # operations visible in a 100-case benchmark.
    root_quota = largest_remainder(
        {k: math.sqrt(v) for k, v in root_counts.items()}, N_CASES
    )

    selected = []
    step_quota_by_root = {}
    for root in sorted(root_groups):
        groups: dict[str, list[dict]] = collections.defaultdict(list)
        for item in root_groups[root]:
            groups[metadata[item["id"]][2]].append(item)
        counts = {k: len(v) for k, v in groups.items()}
        quota = allocate_with_minimum(counts, root_quota[root], minimum_one=True)
        step_quota_by_root[root] = quota

        for bucket in sorted(groups):
            candidates = sorted(groups[bucket], key=lambda x: x["id"])
            rng = random.Random(f"{SEED}:{root}:{bucket}")
            chosen = rng.sample(candidates, quota[bucket])
            selected.extend(chosen)

    if len(selected) != N_CASES:
        raise AssertionError(f"Expected {N_CASES} cases, got {len(selected)}")
    if len({x["id"] for x in selected}) != N_CASES:
        raise AssertionError("Duplicate selected IDs")

    # Stable output ordering makes diffs and reruns simple.
    selected.sort(key=lambda x: x["id"])
    return selected, {
        "full_test_size": len(items),
        "eligible_size": len(items) - len(excluded),
        "excluded_inconsistent_gold_count": len(excluded),
        "root_counts_full_test": dict(sorted(full_root_counts.items())),
        "root_counts_eligible": root_counts,
        "root_quota": root_quota,
        "step_quota_by_root": step_quota_by_root,
    }


def frozen_case(item: dict) -> dict:
    root_op, n_steps, bucket = case_metadata(item)
    qa = item["qa"]
    evidence = [{"id": k, "text": v} for k, v in qa["gold_inds"].items()]
    if not evidence:
        raise ValueError(f"No gold evidence for {item['id']}")
    return {
        "id": item["id"],
        "filename": item["filename"],
        "question": qa["question"],
        "evidence": evidence,
        "gold_answer": qa["answer"],
        "gold_exe_answer": qa["exe_ans"],
        "root_op": root_op,
        "num_steps": n_steps,
        "step_bucket": bucket,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="Optional local copy of pinned FinQA test.json")
    parser.add_argument("--output", default="data/cases.jsonl")
    parser.add_argument("--provenance", default="data/provenance.json")
    args = parser.parse_args()

    items, raw = load_source(args.source)
    selected, sampling = select_cases(items)
    frozen = [frozen_case(x) for x in selected]

    output = Path(args.output)
    provenance = Path(args.provenance)
    output.parent.mkdir(parents=True, exist_ok=True)
    provenance.parent.mkdir(parents=True, exist_ok=True)

    encoded_lines = [
        json.dumps(x, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        for x in frozen
    ]
    output_bytes = ("\n".join(encoded_lines) + "\n").encode()
    output.write_bytes(output_bytes)

    root_counts_sample = collections.Counter(x["root_op"] for x in frozen)
    step_counts_sample = collections.Counter(x["step_bucket"] for x in frozen)
    evidence_counts = collections.Counter(len(x["evidence"]) for x in frozen)

    prov = {
        "dataset": "FinQA",
        "split": "test",
        "source_repo": SOURCE_REPO,
        "source_commit": SOURCE_SHA,
        "source_url": SOURCE_URL,
        "source_test_sha256": sha256_bytes(raw),
        "license": "MIT",
        "sample_size": N_CASES,
        "seed": SEED,
        "eligibility_filter": "published human answer agrees with exe_ans after numeric rounding and percent-unit normalization",
        "sampling": {
            "method": "after gold-consistency filtering: sqrt-frequency root operation quotas; proportional step-count quotas with minimum one per nonempty step bucket",
            **sampling,
        },
        "sample_stats": {
            "root_op_counts": dict(sorted(root_counts_sample.items())),
            "step_bucket_counts": dict(sorted(step_counts_sample.items())),
            "evidence_count_distribution": {
                str(k): v for k, v in sorted(evidence_counts.items())
            },
        },
        "cases_sha256": sha256_bytes(output_bytes),
        "model_input": "question + gold evidence snippets only; programs and full report context are excluded",
    }
    provenance.write_text(json.dumps(prov, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(frozen)} cases to {output}")
    print(json.dumps(prov["sample_stats"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
