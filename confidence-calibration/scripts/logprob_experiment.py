#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=1.0", "tiktoken>=0.9"]
# ///
"""Paired BANKING77 confidence experiment: first-token logprob vs stated confidence.

Each case gets a deterministic per-case permutation from the 77 intent labels to 77
single-character codes. The response must begin with the chosen code, followed by the
model's stated confidence. This makes the first output token a one-token class decision.
Rows are appended immediately and keyed by (model, id), so runs are resumable.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import random
import re
from pathlib import Path

from openai import AsyncOpenAI
import tiktoken

from common import DATA, openai_api_key
from prompt_fragments import FULL_VARIANTS

INPUT = DATA / "banking77-sample.csv"
FIELDS = [
    "model", "id", "gold", "prediction", "code", "correct",
    "stated_confidence", "token_logprob", "token_probability",
    "top_logprobs_json", "raw",
]
# 62 alphanumerics + 15 punctuation characters. Every code is one token under
# cl100k_base and o200k_base; this is also checked in the preflight recipe.
CODES = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$%&*+-/:<=>?@"
assert len(CODES) == 77 and len(set(CODES)) == 77
for _enc_name in ("cl100k_base", "o200k_base"):
    _enc=tiktoken.get_encoding(_enc_name)
    bad=[c for c in CODES if len(_enc.encode(c))!=1 or _enc.decode(_enc.encode(c))!=c]
    if bad: raise RuntimeError(f"Codes are not one token under {_enc_name}: {bad}")
TOP_TWO = FULL_VARIANTS["top_two_mass"]


def code_map(case_id: str, labels: list[str], mapping_version: str = "v1") -> tuple[dict[str, str], dict[str, str]]:
    """Return deterministic per-case code→label and label→code maps."""
    seed = int.from_bytes(hashlib.sha256(f"logprob-{mapping_version}:{case_id}".encode()).digest()[:8], "big")
    codes = list(CODES)
    random.Random(seed).shuffle(codes)
    code_to_label = dict(zip(codes, labels))
    return code_to_label, {label: code for code, label in code_to_label.items()}


def output_path(mapping_version: str) -> Path:
    return DATA / ("logprob-results.csv" if mapping_version == "v1" else f"logprob-remap-{mapping_version}.csv")


def done(path: Path, model: str) -> set[str]:
    if not path.exists():
        return set()
    return {r["id"] for r in csv.DictReader(path.open()) if r["model"] == model}


def append(path: Path, row: dict[str, object]) -> None:
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def parse_output(text: str, valid_codes: set[str]) -> tuple[str, int]:
    text = text.strip()
    if not text:
        raise ValueError("empty output")
    code = text[0]
    if code not in valid_codes:
        raise ValueError(f"invalid first-character code {code!r}")
    m = re.match(r"^.\s+(\d{1,3})(?:\s|$)", text, flags=re.S)
    if not m:
        raise ValueError(f"expected '<CODE> <CONFIDENCE>', got {text!r}")
    confidence = int(m.group(1))
    if not 0 <= confidence <= 100:
        raise ValueError("confidence out of range")
    return code, confidence


async def run(model: str, concurrency: int, limit: int | None, mapping_version: str, input_path: Path = INPUT, out_path: Path | None = None) -> None:
    rows = list(csv.DictReader(input_path.open()))
    labels = sorted({r["category"] for r in rows})
    if len(labels) != 77:
        raise SystemExit(f"Expected 77 labels, found {len(labels)}")
    out = out_path or output_path(mapping_version)
    completed = done(out, model)
    pending = [r for r in rows if r["id"] not in completed]
    pending.sort(key=lambda r: hashlib.sha256(f"preflight:{r['id']}".encode()).hexdigest())
    if limit is not None:
        pending = pending[:limit]
    print(f"{model}: {len(pending)} pending in this run / {len(rows)} total; {len(completed)} cached", flush=True)
    if not pending:
        return

    client = AsyncOpenAI(api_key=openai_api_key())
    sem = asyncio.Semaphore(concurrency)

    async def one(r: dict[str, str]) -> dict[str, object]:
        c2l, _ = code_map(r["id"], labels, mapping_version)
        mapping = "\n".join(f"{code}\t{label}" for code, label in c2l.items())
        prompt = f"""Classify the customer request into exactly one intent from the mapping below.
The first column is a one-character output code; the second is the intent label.

CODE\tINTENT
{mapping}

REQUEST
{r['text']}

Confidence instruction:
{TOP_TWO}

Return exactly: <CODE><space><CONFIDENCE>
- CODE is exactly one character from the first column above.
- CONFIDENCE is an integer 0-100 for the probability that the intent represented by CODE exactly matches the gold intent.
- The very first character of your response MUST be CODE. No JSON, markdown, explanation, or leading whitespace."""
        async with sem:
            last: Exception | None = None
            for attempt in range(5):
                try:
                    kwargs: dict[str, object] = {
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_completion_tokens": 24,
                        "temperature": 0,
                        "logprobs": True,
                        "top_logprobs": 5,
                    }
                    if model == "gpt-5.6-luna":
                        kwargs["reasoning_effort"] = "none"
                    resp = await client.chat.completions.create(**kwargs)
                    choice = resp.choices[0]
                    raw = (choice.message.content or "").strip()
                    code, stated = parse_output(raw, set(c2l))
                    token_rows = choice.logprobs.content if choice.logprobs else None
                    if not token_rows:
                        raise ValueError("API returned no token logprobs")
                    first = token_rows[0]
                    # The response is required to begin with the one-character code; verify the API token agrees.
                    if first.token != code:
                        raise ValueError(f"first token {first.token!r} != parsed code {code!r}")
                    lp = float(first.logprob)
                    p = math.exp(lp)
                    tops = [{"token": t.token, "logprob": float(t.logprob)} for t in first.top_logprobs]
                    pred = c2l[code]
                    return {
                        "model": model, "id": r["id"], "gold": r["category"], "prediction": pred,
                        "code": code, "correct": int(pred == r["category"]),
                        "stated_confidence": stated, "token_logprob": repr(lp),
                        "token_probability": repr(p), "top_logprobs_json": json.dumps(tops, separators=(",", ":")),
                        "raw": raw.replace("\n", " "),
                    }
                except Exception as e:
                    last = e
                    await asyncio.sleep(min(8, 0.5 * 2**attempt))
            raise RuntimeError(f"{r['id']} failed after retries: {last}")

    completed_now = 0
    for fut in asyncio.as_completed([one(r) for r in pending]):
        append(out, await fut)
        completed_now += 1
        if completed_now % 25 == 0 or completed_now == len(pending):
            print(f"  completed {completed_now}/{len(pending)}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="gpt-5.6-luna")
    p.add_argument("--concurrency", type=int, default=12)
    p.add_argument("--limit", type=int, help="run only this many currently-missing cases (preflight)")
    p.add_argument("--mapping-version", default="v1", help="deterministic remapping seed version; v1 uses the canonical cache")
    p.add_argument("--input", type=Path, default=INPUT, help="input CSV with id,text,category")
    p.add_argument("--output", type=Path, help="output cache CSV; defaults from mapping version")
    a = p.parse_args()
    asyncio.run(run(a.model, a.concurrency, a.limit, a.mapping_version, a.input, a.output))


if __name__ == "__main__":
    main()
