#!/usr/bin/env python3
"""Validate result-log completeness and first-pass measurement invariants."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = json.loads((ROOT / "models.json").read_text())


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True)
    p.add_argument("--ids-file")
    args = p.parse_args()

    results = Path(args.results)
    if not results.is_absolute():
        results = ROOT / results
    rows = read_jsonl(results)

    if args.ids_file:
        ids_path = Path(args.ids_file)
        if not ids_path.is_absolute():
            ids_path = ROOT / ids_path
        ids = [line.strip() for line in ids_path.read_text().splitlines() if line.strip()]
    else:
        ids = [row["id"] for row in read_jsonl(ROOT / "data" / "cases.jsonl")]

    expected = {(model, case_id) for model in MODELS for case_id in ids}
    id_filter = set(ids) if args.ids_file else None
    successful: dict[tuple[str, str], dict] = {}
    duplicate_success = []
    errors = []

    for row in rows:
        if id_filter is not None and row["id"] not in id_filter:
            continue
        key = (row["model_key"], row["id"])
        if row.get("status") == "ok":
            if key in successful:
                duplicate_success.append(key)
            successful[key] = row
        else:
            errors.append(row)

    missing = expected - set(successful)
    unexpected = set(successful) - expected
    assert not missing, f"missing successful pairs: {sorted(missing)[:10]}"
    assert not unexpected, f"unexpected successful pairs: {sorted(unexpected)[:10]}"
    assert not duplicate_success, f"duplicate successful pairs: {duplicate_success[:10]}"

    prompt_versions = {row["prompt_version"] for row in successful.values()}
    assert len(prompt_versions) == 1, prompt_versions

    retries = 0
    provider_counts = Counter()
    for (model, _), row in successful.items():
        spec = MODELS[model]
        allowed = (spec.get("provider") or {}).get("only") or []
        if allowed:
            assert row.get("provider") in allowed, (model, row.get("provider"), allowed)
        assert row.get("hosted_quantization") == spec.get("hosted_quantization")
        assert isinstance(row.get("input_tokens"), int) and row["input_tokens"] > 0
        assert isinstance(row.get("output_tokens"), int) and row["output_tokens"] > 0
        assert isinstance(row.get("cost"), (int, float)) and row["cost"] >= 0
        assert isinstance(row.get("latency_s"), (int, float)) and row["latency_s"] > 0
        if spec.get("reasoning_required"):
            assert isinstance(row.get("reasoning_tokens"), int) and row["reasoning_tokens"] >= 0
        else:
            assert row.get("reasoning_tokens") == 0
        assert isinstance(row.get("reported_confidence"), int)
        assert 0 <= row["reported_confidence"] <= 100
        assert row.get("attempts", 0) >= 1
        retries += row["attempts"] - 1
        provider_counts[(model, row.get("provider"))] += 1

    print(f"OK: {len(successful)} successful pairs; {len(errors)} error rows; {retries} retries")
    print("prompt_version:", next(iter(prompt_versions)))
    for model in MODELS:
        model_rows = [row for (m, _), row in successful.items() if m == model]
        accuracy = sum(row["correct"] for row in model_rows) / len(model_rows)
        cost = sum(row["cost"] for row in model_rows)
        providers = sorted({row["provider"] for row in model_rows})
        print(f"{model}: n={len(model_rows)} accuracy={accuracy:.3f} cost={cost:.6f} providers={providers}")


if __name__ == "__main__":
    main()
