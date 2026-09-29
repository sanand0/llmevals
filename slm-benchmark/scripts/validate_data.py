#!/usr/bin/env python3
"""Validate the frozen FinQA benchmark without network access."""

from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

from freeze_finqa import display_answer_matches_execution

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data" / "cases.jsonl"
PROVENANCE = ROOT / "data" / "provenance.json"


def main() -> None:
    raw = CASES.read_bytes()
    cases = [json.loads(line) for line in raw.splitlines() if line.strip()]
    prov = json.loads(PROVENANCE.read_text())

    assert len(cases) == 100, len(cases)
    ids = [x["id"] for x in cases]
    assert len(set(ids)) == 100, "duplicate IDs"
    assert ids == sorted(ids), "cases must be in stable ID order"
    assert prov["sample_size"] == 100
    assert prov["split"] == "test"
    assert hashlib.sha256(raw).hexdigest() == prov["cases_sha256"]

    for case in cases:
        assert case["question"].strip()
        assert case["evidence"], case["id"]
        assert all(e["id"] and e["text"].strip() for e in case["evidence"])
        assert case["gold_answer"] not in (None, "")
        assert case["gold_exe_answer"] not in (None, "")
        assert display_answer_matches_execution(
            {"answer": case["gold_answer"], "exe_ans": case["gold_exe_answer"]}
        ), case["id"]
        assert case["root_op"]
        assert case["num_steps"] >= 1
        assert case["step_bucket"] in {"1", "2", "3+"}
        # Do not freeze the reasoning program or full report into model inputs.
        assert "program" not in case
        assert "pre_text" not in case
        assert "post_text" not in case
        assert "table" not in case

    roots = collections.Counter(x["root_op"] for x in cases)
    steps = collections.Counter(x["step_bucket"] for x in cases)
    assert dict(sorted(roots.items())) == prov["sample_stats"]["root_op_counts"]
    assert dict(sorted(steps.items())) == prov["sample_stats"]["step_bucket_counts"]
    assert dict(sorted(roots.items())) == dict(
        sorted(prov["sampling"]["root_quota"].items())
    )

    print("OK: 100 unique frozen FinQA test cases")
    print("root ops:", dict(sorted(roots.items())))
    print("step buckets:", dict(sorted(steps.items())))
    print("cases sha256:", prov["cases_sha256"])


if __name__ == "__main__":
    main()
