#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""Run the frozen 77-case BANKING77 pilot through OpenRouter.

Results append to data/results.jsonl. A (model_key, case_id) already present is skipped,
so interrupted runs can be resumed safely without re-running completed work.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import subprocess
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CASES = DATA / "cases.csv"
RESULTS = DATA / "results.jsonl"
MODELS = json.loads((ROOT / "models.json").read_text())
BASELINE = (
    "your probability that your chosen label exactly matches the gold routing label. "
    "Treat confidence as a probability of correctness, not a vague feeling."
)


def api_key() -> str:
    """Prefer the user's configured llm OpenRouter key; fall back to the environment."""
    try:
        p = subprocess.run(
            ["llm", "keys", "get", "openrouter"],
            capture_output=True,
            text=True,
            check=True,
        )
        if key := p.stdout.strip():
            return key
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    if key := os.environ.get("OPENROUTER_API_KEY", "").strip():
        return key
    raise RuntimeError("Configure OpenRouter with `llm keys set openrouter` or OPENROUTER_API_KEY")


def load_cases() -> list[dict[str, str]]:
    rows = list(csv.DictReader(CASES.open()))
    if len(rows) != 77 or len({r["category"] for r in rows}) != 77:
        raise RuntimeError("data/cases.csv must contain exactly one case for each of 77 labels")
    return rows


def load_completed() -> set[tuple[str, str]]:
    if not RESULTS.exists():
        return set()
    done: set[tuple[str, str]] = set()
    for line in RESULTS.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            done.add((row["model_key"], row["id"]))
    return done


def chat_prompt(row: dict[str, str], labels: list[str]) -> str:
    allowed = json.dumps(labels, separators=(",", ":"))
    return f'''Classify this customer request into exactly one of the allowed labels below.

Allowed labels:
{allowed}

Request:
{row["text"]}

Return ONLY JSON with label (exactly one allowed label) and confidence (integer 0-100): {BASELINE}'''


def parse_json(text: str) -> dict[str, object]:
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group())


async def call_jev(
    client: httpx.AsyncClient,
    key: str,
    row: dict[str, str],
    labels: list[str],
    spec: dict[str, object],
) -> dict[str, object]:
    payload = {
        "model": spec["model"],
        "state": {"request": row["text"]},
        "questions": {
            "intent": {
                "type": "choice",
                "instructions": (
                    "Classify the customer request into exactly one banking support intent. "
                    "The option names correspond to the routing labels."
                ),
                "criteria": {label: label.replace("_", " ").replace("?", "") for label in labels},
            }
        },
    }
    started = time.perf_counter()
    response = await client.post(
        "https://openrouter.ai/api/alpha/decisions",
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
    )
    latency = time.perf_counter() - started
    response.raise_for_status()
    data = response.json()
    answer = data["answers"]["intent"]
    prediction = answer["choice"]
    probabilities = answer["probabilities"]
    confidence = float(probabilities[prediction])
    usage = data.get("usage") or {}
    return {
        "model_returned": data.get("model"),
        "prediction": prediction,
        "confidence": confidence,
        "reported_confidence": answer.get("confidence"),
        "probabilities": probabilities,
        "raw": answer,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "reasoning_tokens": 0,
        "cost": usage.get("cost"),
        "latency_s": latency,
        "generation_id": data.get("id"),
        "provider": data.get("provider"),
    }


async def call_chat(
    client: httpx.AsyncClient,
    key: str,
    row: dict[str, str],
    labels: list[str],
    spec: dict[str, object],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": spec["model"],
        "messages": [{"role": "user", "content": chat_prompt(row, labels)}],
        "max_tokens": spec.get("max_tokens", 256),
        "reasoning": {"effort": spec.get("reasoning", "none"), "exclude": True},
    }
    if "temperature" in spec:
        payload["temperature"] = spec["temperature"]
    started = time.perf_counter()
    response = await client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
    )
    latency = time.perf_counter() - started
    response.raise_for_status()
    data = response.json()
    text = data["choices"][0]["message"].get("content") or ""
    obj = parse_json(text)
    prediction = str(obj["label"])
    confidence = float(obj["confidence"]) / 100
    usage = data.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    return {
        "model_returned": data.get("model"),
        "prediction": prediction,
        "confidence": confidence,
        "reported_confidence": confidence,
        "probabilities": None,
        "raw": text,
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": details.get("reasoning_tokens", 0) or 0,
        "cost": usage.get("cost"),
        "latency_s": latency,
        "generation_id": data.get("id"),
        "provider": usage.get("provider"),
    }


async def run(args: argparse.Namespace) -> None:
    cases = load_cases()
    labels = sorted(r["category"] for r in cases)
    selected = list(MODELS) if args.models == ["all"] else args.models
    unknown = set(selected) - set(MODELS)
    if unknown:
        raise SystemExit(f"Unknown model keys: {', '.join(sorted(unknown))}")
    completed = load_completed()
    plan = {
        model: [r for r in cases if (model, r["id"]) not in completed][: args.limit]
        if args.limit
        else [r for r in cases if (model, r["id"]) not in completed]
        for model in selected
    }
    for model, pending in plan.items():
        print(f"{model}: {len(pending)} pending / 77", flush=True)
    if args.dry_run or not any(plan.values()):
        return

    key = api_key()
    write_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(args.concurrency)
    timeout = httpx.Timeout(120, connect=20)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for model in selected:
            spec = MODELS[model]
            pending = plan[model]
            if not pending:
                continue

            async def one(row: dict[str, str]) -> None:
                async with semaphore:
                    error: Exception | None = None
                    for attempt in range(5):
                        try:
                            result = (
                                await call_jev(client, key, row, labels, spec)
                                if spec.get("kind") == "decision"
                                else await call_chat(client, key, row, labels, spec)
                            )
                            record = {
                                "model_key": model,
                                "model_requested": spec["model"],
                                "id": row["id"],
                                "gold": row["category"],
                                **result,
                            }
                            record["correct"] = int(record["prediction"] == record["gold"])
                            async with write_lock:
                                with RESULTS.open("a") as f:
                                    f.write(json.dumps(record, separators=(",", ":")) + "\n")
                            return
                        except Exception as exc:  # retry transient/provider/parse failures
                            error = exc
                            await asyncio.sleep(min(8, 0.5 * 2**attempt))
                    raise RuntimeError(f"{model}/{row['id']} failed after retries: {error}")

            done_now = 0
            for future in asyncio.as_completed([one(row) for row in pending]):
                await future
                done_now += 1
                if done_now % 10 == 0 or done_now == len(pending):
                    print(f"  {done_now}/{len(pending)} complete", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["all"], help="model keys from models.json or all")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--limit", type=int, help="at most N currently-missing cases per model")
    parser.add_argument("--dry-run", action="store_true", help="show pending work without API calls")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
