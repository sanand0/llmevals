#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["llm>=0.27", "llm-openrouter>=0.7"]
# ///
"""Resumable OpenRouter multiplication benchmark; see `just build` and plan.json.

A recorded API error or timeout counts as a *completed attempt*, not a correct
answer. `--retry-errors` explicitly retries these and may incur additional costs.
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import random
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "data/results.jsonl"
MODELS = {
    "sol": "openai/gpt-6.1-sol",
    "luna": "openai/gpt-6-luna",
    "opus": "anthropic/claude-opus-5.5",
    "sonnet": "anthropic/claude-sonnet-5.5",
    "gemini-pro": "google/gemini-3.1-pro-preview",
    "gemini-flash": "google/gemini-3.8-flash",
    "grok": "x-ai/grok-4.7",
    "deepseek": "deepseek/deepseek-v4-pro",
    "qwen": "qwen/qwen3.8-max-0902",
}
PROMPT = "Multiply these two integers exactly:\n{a} * {b}\nReturn ONLY the decimal integer, without commas or explanation."
VERSION = hashlib.sha256(PROMPT.encode()).hexdigest()[:12]


def operands(digits: int, trials: int, seed: int) -> list[tuple[int, int]]:
    """Sample uniformly from positive fixed-length integers without leading zeros."""
    rng = random.Random(seed + digits)
    low, high = 10 ** (digits - 1), 10 ** digits - 1
    return [(rng.randint(low, high), rng.randint(low, high)) for _ in range(trials)]


def identity(row: dict) -> tuple:
    """Output cap is part of condition; old rows implicitly used 4096."""
    return (row["model"], row["digits"], row["trial"], row["reasoning"],
            row["version"], row.get("max_tokens", 4096))


def load(path: Path = RESULTS) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def latest(rows: list[dict]) -> dict[tuple, dict]:
    """Retain the first successful reply; otherwise track the newest error.

    A later 401 must supersede an older 402 so `retry-credits` cannot
    repeatedly retry an authentication failure as a credit failure.
    """
    dedup: dict[tuple, dict] = {}
    for r in rows:
        k = identity(r)
        if k not in dedup or dedup[k]["status"] != "ok":
            dedup[k] = r
    return dedup


def planned(config: dict) -> list[dict]:
    unique: dict[tuple, dict] = {}
    for batch in config["runs"]:
        for name in batch["models"]:
            model = MODELS.get(name, name)
            for digits in batch["digits"]:
                for trial, (a, b) in enumerate(operands(digits, batch.get("trials", config["trials"]), config["seed"])):
                    row = {"model": model, "digits": digits, "trial": trial, "a": a,
                           "b": b, "reasoning": batch.get("reasoning", "default"),
                           "version": VERSION, "max_tokens": batch["max_tokens"],
                           "timeout": batch["timeout"]}
                    unique[identity(row)] = row
    return list(unique.values())


def missing(expected: list[dict], existing: list[dict], retry_errors: bool = False, retry_credit_errors: bool = False) -> list[dict]:
    completed = latest(existing)
    pending = []
    for row in expected:
        old = completed.get(identity(row))
        if old:
            if (old["a"], old["b"], old["expected"]) != (row["a"], row["b"], str(row["a"] * row["b"])):
                raise ValueError(f"Mismatched recorded problem for {identity(row)}")
            if old["status"] == "ok" or not (retry_errors or (retry_credit_errors and "code: 402" in old.get("error", ""))):
                continue
        pending.append(row)
    return pending


def final_integer(answer: str) -> int | None:
    """Score the final integer, allowing a model to include explanatory prose."""
    hits = re.findall(r"(?<![\d,])[+-]?\d[\d,]*(?![\d,])", answer.replace("\u2009", "").replace("\u202f", ""))
    return int(hits[-1].replace(",", "")) if hits else None


def strict_integer(answer: str) -> bool:
    return re.fullmatch(r"[+-]?\d+", answer.strip().replace(",", "")) is not None


async def evaluate(item: dict, semaphore: asyncio.Semaphore, write_lock: asyncio.Lock) -> None:
    async with semaphore:
        import llm  # Avoid loading OpenRouter plugin when all outputs are cached.

        row = {**item, "expected": str(item["a"] * item["b"])}
        start = time.monotonic()
        try:
            opts = {"max_tokens": row["max_tokens"]}
            if row["reasoning"] != "default":
                opts["reasoning_effort"] = row["reasoning"]
            response = await asyncio.wait_for(
                llm.get_async_model("openrouter/" + row["model"]).prompt(
                    PROMPT.format(**row), options=opts, stream=False, hide_reasoning=True
                ), timeout=row["timeout"]
            )
            answer, usage = await response.text(), await response.usage()
            row.update(status="ok", answer=answer,
                       correct=final_integer(answer) == row["a"] * row["b"],
                       format_ok=strict_integer(answer),
                       input_tokens=usage.input, output_tokens=usage.output,
                       usage_details=usage.details)
        except Exception as error:
            row.update(status="error", answer="", correct=False,
                       error=f"{type(error).__name__}: {str(error)[:300]}")
        row["seconds"] = round(time.monotonic() - start, 3)
        async with write_lock:
            with RESULTS.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{row['model']} {row['digits']}d trial {row['trial']}: "
                  f"{row['status']} correct={row['correct']} {row['seconds']}s", flush=True)


async def main(args: argparse.Namespace) -> None:
    with (ROOT / ".run.lock").open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = json.loads((ROOT / "plan.json").read_text())
        expected = planned(config)
        observed = load()
        pending = missing(expected, observed, args.retry_errors, args.retry_credit_errors)
        errors = sum(r["status"] != "ok" for r in latest(observed).values())
        print(f"{len(pending)} pending / {len(expected)} planned; {len(observed)} logged attempts "
              f"({errors} unique error statuses); prompt={VERSION}", flush=True)
        if args.dry_run or not pending:
            return
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        semaphore, write_lock = asyncio.Semaphore(args.concurrency), asyncio.Lock()
        await asyncio.gather(*(evaluate(row, semaphore, write_lock) for row in pending))
        print(f"Completed {len(pending)} new attempts; see `just analyze`.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--retry-credit-errors", action="store_true", help="Retry only recorded OpenRouter HTTP 402 errors")
    asyncio.run(main(parser.parse_args()))
