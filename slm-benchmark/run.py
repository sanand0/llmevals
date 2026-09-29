#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""Run the frozen 100-case FinQA benchmark through OpenRouter, resumably."""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import re
import time
from pathlib import Path

import httpx
from score import score_answer

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CASES = DATA / "cases.jsonl"
DEFAULT_RESULTS = DATA / "results.jsonl"
MODELS = json.loads((ROOT / "models.json").read_text())
PROMPT_VERSION = hashlib.sha256((ROOT / "prompt.md").read_bytes()).hexdigest()[:12]

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "finqa_answer",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            "required": ["answer", "confidence"],
            "additionalProperties": False,
        },
    },
}


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and not os.environ.get(key):
            os.environ[key] = value


def api_key() -> str:
    load_dotenv(ROOT / ".env")
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing OPENROUTER_API_KEY in slm-benchmark/.env or environment")
    return key


def acquire_runner_lock():
    """Prevent concurrent paid runs from duplicating model/case calls."""
    build = ROOT / ".build"
    build.mkdir(exist_ok=True)
    handle = (build / "run.lock").open("w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise RuntimeError("Another slm-benchmark run is already active") from exc
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def load_cases() -> list[dict]:
    rows = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    if len(rows) != 100 or len({row["id"] for row in rows}) != 100:
        raise RuntimeError("data/cases.jsonl must contain exactly 100 unique cases")
    return rows


def resolve_results(value: str | None) -> Path:
    if not value:
        return DEFAULT_RESULTS
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load_completed(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("status") == "ok":
            done.add((row["model_key"], row["id"]))
    return done


def evidence_text(row: dict) -> str:
    return "\n".join(f"- {item['text']}" for item in row["evidence"])


def chat_prompt(row: dict) -> str:
    return f"""Answer the financial question using only the evidence below.

Evidence:
{evidence_text(row)}

Question:
{row["question"]}

Return only JSON matching the supplied schema:
{{"answer":"FINAL_ANSWER","confidence":0-100}}

Rules:
- answer: give only the final answer, with the natural unit implied by the question/evidence. Use % for percentages and yes/no for yes/no questions.
- Do not include an explanation or reasoning in answer.
- confidence: your probability, as an integer from 0 to 100, that answer matches the correct FinQA answer.
- Treat confidence as a probability of correctness, not a vague feeling.
- Use only the supplied evidence."""


def parse_json(text: str) -> dict:
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        obj = json.loads(match.group())
    if not isinstance(obj, dict):
        raise ValueError("response is not a JSON object")
    if set(obj) != {"answer", "confidence"}:
        raise ValueError(f"unexpected response keys: {sorted(obj)}")
    confidence = int(obj["confidence"])
    if not 0 <= confidence <= 100:
        raise ValueError("confidence out of range")
    answer = str(obj["answer"]).strip()
    if not answer:
        raise ValueError("empty answer")
    return {"answer": answer, "confidence": confidence}


def err(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        body = exc.response.text[:1000].replace("\n", " ")
        return f"HTTP {exc.response.status_code}: {body}"
    return f"{type(exc).__name__}: {exc}"[:1200]


async def call_chat(client: httpx.AsyncClient, key: str, row: dict, spec: dict) -> dict:
    payload: dict[str, object] = {
        "model": spec["model"],
        "messages": [{"role": "user", "content": chat_prompt(row)}],
        "max_tokens": spec.get("max_tokens", 96),
        "response_format": RESPONSE_FORMAT if spec.get("structured_output", True) else {"type": "json_object"},
    }
    if spec.get("send_reasoning", True):
        payload["reasoning"] = {"effort": spec.get("reasoning", "none"), "exclude": True}
    if "temperature" in spec:
        payload["temperature"] = spec["temperature"]
    if provider := spec.get("provider"):
        payload["provider"] = provider

    started = time.perf_counter()
    response = await client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
    )
    latency = time.perf_counter() - started
    response.raise_for_status()
    data = response.json()
    text = data["choices"][0]["message"].get("content") or ""
    obj = parse_json(text)
    usage = data.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    return {
        "model_returned": data.get("model"),
        "provider": data.get("provider") or usage.get("provider"),
        "generation_id": data.get("id"),
        "answer": obj["answer"],
        "confidence": obj["confidence"] / 100.0,
        "reported_confidence": obj["confidence"],
        "raw": text,
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": details.get("reasoning_tokens", 0) or 0,
        "cost": usage.get("cost"),
        "latency_s": latency,
    }


async def append_record(path: Path, record: dict, lock: asyncio.Lock) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with lock:
        with path.open("a") as f:
            f.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")


async def run(args: argparse.Namespace) -> None:
    cases = load_cases()
    selected = list(MODELS) if args.models == ["all"] else args.models
    unknown = set(selected) - set(MODELS)
    if unknown:
        raise SystemExit(f"Unknown model keys: {', '.join(sorted(unknown))}")

    if args.ids:
        wanted = set(args.ids)
        available = {row["id"] for row in cases}
        missing_ids = wanted - available
        if missing_ids:
            raise SystemExit(f"Unknown case IDs: {', '.join(sorted(missing_ids))}")
        cases = [row for row in cases if row["id"] in wanted]

    output = resolve_results(args.results)
    completed = load_completed(output)
    plan = {}
    for model in selected:
        missing = [row for row in cases if (model, row["id"]) not in completed]
        plan[model] = missing[:args.limit] if args.limit else missing

    for model, pending in plan.items():
        print(f"{model}: {len(pending)} pending / 100", flush=True)
    if args.dry_run or not any(plan.values()):
        return

    runner_lock = acquire_runner_lock()
    key = api_key()
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(args.concurrency)
    timeout = httpx.Timeout(180, connect=30)

    async with httpx.AsyncClient(timeout=timeout) as client:
        for model in selected:
            spec = MODELS[model]
            pending = plan[model]
            if not pending:
                continue

            rate_lock = asyncio.Lock()
            next_request_at = 0.0

            async def throttle() -> None:
                nonlocal next_request_at
                interval = float(spec.get("min_interval_s", 0))
                if interval <= 0:
                    return
                async with rate_lock:
                    now = time.monotonic()
                    if next_request_at > now:
                        await asyncio.sleep(next_request_at - now)
                    next_request_at = time.monotonic() + interval

            async def one(row: dict) -> None:
                async with sem:
                    errors = []
                    for attempt in range(1, args.retries + 1):
                        try:
                            await throttle()
                            result = await call_chat(client, key, row, spec)
                            record = {
                                "status": "ok",
                                "model_key": model,
                                "model_name": spec["name"],
                                "model_requested": spec["model"],
                                "tier": spec["tier"],
                                "provider_requested": spec.get("provider"),
                                "hosted_quantization": spec.get("hosted_quantization"),
                                "id": row["id"],
                                "filename": row["filename"],
                                "gold": row["gold_answer"],
                                "gold_exe_answer": row["gold_exe_answer"],
                                "root_op": row["root_op"],
                                "num_steps": row["num_steps"],
                                "prompt_version": PROMPT_VERSION,
                                "attempts": attempt,
                                "retry_errors": errors,
                                **result,
                            }
                            record["correct"] = int(score_answer(record["answer"], record["gold"]))
                            await append_record(output, record, lock)
                            return
                        except Exception as exc:
                            errors.append(err(exc))
                            if attempt < args.retries:
                                await asyncio.sleep(min(8, 0.5 * 2 ** (attempt - 1)))

                    record = {
                        "status": "error",
                        "model_key": model,
                        "model_name": spec["name"],
                        "model_requested": spec["model"],
                        "tier": spec["tier"],
                        "provider_requested": spec.get("provider"),
                        "hosted_quantization": spec.get("hosted_quantization"),
                        "id": row["id"],
                        "filename": row["filename"],
                        "gold": row["gold_answer"],
                        "gold_exe_answer": row["gold_exe_answer"],
                        "root_op": row["root_op"],
                        "num_steps": row["num_steps"],
                        "prompt_version": PROMPT_VERSION,
                        "attempts": args.retries,
                        "retry_errors": errors,
                    }
                    await append_record(output, record, lock)
                    raise RuntimeError(
                        f"{model}/{row['id']} failed after {args.retries} attempts: {errors[-1]}"
                    )

            n = 0
            for future in asyncio.as_completed([one(row) for row in pending]):
                await future
                n += 1
                if n % 10 == 0 or n == len(pending):
                    print(f"  {n}/{len(pending)} complete", flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--models", nargs="+", default=["all"], help="model keys from models.json or all")
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--limit", type=int, help="at most N currently-missing cases per model")
    p.add_argument("--ids", nargs="+", help="run only these frozen FinQA case IDs")
    p.add_argument("--results", help="alternate JSONL path, relative to project root unless absolute")
    p.add_argument("--retries", type=int, default=4)
    p.add_argument("--dry-run", action="store_true")
    asyncio.run(run(p.parse_args()))

if __name__ == "__main__":
    main()
