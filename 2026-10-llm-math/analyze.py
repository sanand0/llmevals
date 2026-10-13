#!/usr/bin/env -S uv run --script
"""Deterministically rebuild README, summary.csv and costs.csv from saved replies."""
from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from run import MODELS, PROMPT, VERSION, final_integer, identity, latest, load, planned, strict_integer

ROOT = Path(__file__).resolve().parent
PRICING = json.loads((ROOT / "data/pricing.json").read_text())
CONFIG = json.loads((ROOT / "plan.json").read_text())
ALL = load()
EXISTING = latest(ALL)
EXPECTED = planned(CONFIG)
PLANNED_COUNTS = Counter((r["model"], r["digits"], r["max_tokens"]) for r in EXPECTED)


def cost(row: dict) -> float:
    """Estimate known spend from reported token usage and a fixed price snapshot."""
    if row["status"] != "ok":
        return 0.0  # Error/timeout billing is unknown, not necessarily zero.
    rate = PRICING["prices"][row["model"]]
    return ((row.get("input_tokens") or 0) * float(rate.get("prompt") or 0)
            + (row.get("output_tokens") or 0) * float(rate.get("completion") or 0))


def write_csv(filename: str, values: list[dict]) -> None:
    with (ROOT / filename).open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=values[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def show_cell(s: dict | None, trials: int) -> str:
    if not s:
        return "–"
    marker = "†" if s["no_answer"] or s["errors"] else ""
    return f"{s['correct']}/{trials}{marker}"


def main() -> None:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for spec in EXPECTED:
        found = EXISTING.get(identity(spec))
        if found:
            grouped[(spec["model"], spec["digits"], spec["max_tokens"])].append(found)
    sizes = sorted({r["digits"] for r in EXPECTED})
    summary = []
    for (model, digits, budget), rr in sorted(grouped.items()):
        valid = [r for r in rr if r["status"] == "ok"]
        filled = [r for r in valid if r.get("answer", "").strip()]
        total = PLANNED_COUNTS[(model, digits, budget)]
        summary.append({
            "model": model, "digits": digits, "max_tokens": budget,
            "planned": total, "recorded": len(rr), "responses": len(valid),
            "correct": sum(final_integer(r.get("answer", "")) == int(r["expected"]) for r in valid),
            "wrong_answer": sum(final_integer(r.get("answer", "")) != int(r["expected"]) for r in filled),
            "no_answer": len(valid) - len(filled),
            "reasoning_cap_hit": sum(not r.get("answer", "").strip() and (r.get("output_tokens") or 0) >= budget for r in valid),
            "errors": len(rr) - len(valid),
            "unattempted": total - len(rr),
            "format_ok": sum(strict_integer(r.get("answer", "")) for r in valid),
            "median_seconds": round(statistics.median(r["seconds"] for r in valid), 1) if valid else "",
            "input_tokens": sum(int(r.get("input_tokens") or 0) for r in valid),
            "output_tokens": sum(int(r.get("output_tokens") or 0) for r in valid),
            "estimated_usd": round(sum(cost(r) for r in valid), 5),
        })
    write_csv("summary.csv", summary)

    per_model: dict[str, dict] = {}
    for row in ALL:  # Duplicated paid replies count toward spend, not accuracy.
        x = per_model.setdefault(row["model"], {"model": row["model"], "attempts": 0,
                                                   "priced_replies": 0, "unpriced_errors": 0,
                                                   "input_tokens": 0, "output_tokens": 0,
                                                   "estimated_usd": 0.0})
        x["attempts"] += 1
        if row["status"] == "ok":
            x["priced_replies"] += 1
            x["input_tokens"] += row.get("input_tokens") or 0
            x["output_tokens"] += row.get("output_tokens") or 0
            x["estimated_usd"] += cost(row)
        else:
            x["unpriced_errors"] += 1
    prices = sorted(per_model.values(), key=lambda x: -x["estimated_usd"])
    for row in prices:
        row["estimated_usd"] = round(row["estimated_usd"], 5)
    write_csv("costs.csv", prices)
    total_cost = sum(cost(r) for r in ALL)
    incomplete = sum(s["unattempted"] for s in summary)
    conditions = {(s["model"], s["digits"], s["max_tokens"]): s for s in summary}
    main_models = ["sol", "opus", "sonnet", "gemini-flash", "luna", "gemini-pro", "qwen", "grok", "deepseek"]
    # Use the best-studied generous-budget condition at each size, not an average across budgets.
    def preferred(model: str, d: int) -> dict | None:
        budgets = [key[2] for key in conditions if key[0] == model and key[1] == d]
        if not budgets:
            return None
        return conditions[model, d, max(budgets)] if model != MODELS["sol"] else conditions[model, d, 4096]

    lines = [
        "# How large can frontier LLMs multiply numbers?",
        "",
        "**13 October 2026 · OpenRouter · ten shared random problems per main condition · no tools.**",
        "",
        "## Results",
        "",
        "**Takeaway:** GPT-6.1 Sol solved all 10/10 questions through **35-digit × 35-digit** operands. "
        "Claude Sonnet 5.5 solved **10/10 at 40 digits** with 12k output tokens, while Claude Opus 5.5 solved **7/10 at 40 digits** and **5/10 at 50 digits** at that budget. "
        "These are screening samples: 10/10 does **not** prove high real-world reliability.",
        "",
        "| Model | " + " | ".join(str(d) for d in sizes) + " |",
        "| :--- | " + " | ".join("---:" for _ in sizes) + " |",
    ]
    for name in main_models:
        model = MODELS[name]
        lines.append(f"| {model} | " + " | ".join(show_cell(preferred(model, d), CONFIG["trials"]) for d in sizes) + " |")
    lines += [
        "",
        "Cells = exact products / attempted problems. **†** marks at least one unanswered response (reasoning-cap exhaustion or API error); don't interpret all missing answers as mathematical mistakes. **–** = not tested. "
        "The table uses the largest tested output cap for each model/length (4,096, 12,000, or 20,000 tokens), except GPT-6.1 Sol where only the 4,096-token sweep completed sufficiently for comparison. "
        "See `summary.csv` for all budgets and for the count of genuinely wrong, empty, and errored responses.",
        "",
        "### Most informative contrasts",
        "",
        "- **Reasoning tokens beat first impressions.** Sonnet 5.5 was 2/10 at 30 digits with a 4,096-token cap (eight empty replies); the **same problems** were 10/10 with 12,000 tokens. "
        "At 40 digits it reached 10/10 with 12,000 tokens. At 50 digits its score rose from 2/10 at 12,000 tokens to 6/10 at 20,000 tokens (with one timeout).",
        "- **GPT-6.1 Sol's measured success extends to 35 digits.** At 40–50 digits, the 4,096-token tests largely exhausted the budget or timed out. That is *not* a demonstrated hard arithmetic ceiling.",
        "- **Arithmetic and missing responses differ.** Gemini 3.8 Flash dropped to 2/10 at 20 digits and 0/10 at 30 digits with actual numeric answers; by contrast, some other models produced no final number after using their available reasoning tokens.",
        "- **Accuracy is not necessarily monotonic in ten samples.** Small samples and heterogeneous failures can make a model appear better on 15 digits than 12 digits. Replicate near any chosen cutoff.",
        "",
        "### Cost and coverage",
        "",
        f"**About US${total_cost:.2f} estimated identifiable inference charges** across {len(ALL)} recorded API attempts ({sum(r['status'] == 'ok' for r in ALL)} priced replies), including duplicate attempts from the earlier remote-timeout/replay. "
        "Computed from reported input/output tokens using frozen OpenRouter prices in `data/pricing.json`; **not an OpenRouter invoice or a lower bound on actual charges**. "
        "Timed-out requests might still have incurred charges that are invisible to this log. See `costs.csv` for per-model amounts and tokens.",
        "",
        f"The fixed plan covers **{len(EXPECTED)} model × length × trial × budget combinations**; "
        f"{len(EXPECTED) - incomplete} have at least one recorded attempt, {incomplete} remain unattempted. "
        "API errors (including HTTP 402 insufficient OpenRouter credits) are persisted as observed outcomes, not automatically retried by `just build`. "
        "This prevents unexpected spending and keeps rebuilds instant; `just retry-errors` is the explicit paid retry action after topping up credits.",
        "",
        "## Process and reproduction",
        "",
        "Run from this directory:",
        "",
        "```bash",
        "just build          # reproduce README.md, summary.csv, costs.csv; skip saved API calls",
        "just check          # show missing attempts without calling an LLM",
        "just test           # offline reproducibility tests",
        "just retry-credits  # optional: retry only HTTP 402 cases after adding credits (PAID)",
        "just retry-errors   # optional: reattempt every failed/timeout request (PAID)",
        "```",
        "",
        "`just build` first checks each planned (model, digits, trial, reasoning, prompt hash, token budget). "
        "If `data/results.jsonl` has that attempt (including a recorded error), it makes **zero API calls**. "
        "If the results file is deleted, all planned tests are re-run. If interrupted, completed JSONL rows are retained and only missing attempts are scheduled on the next run. "
        "Deleting `summary.csv`, `costs.csv`, or `README.md` regenerates them locally without spending anything. "
        "New API responses are not guaranteed to be byte-identical because model inference and provider routing can vary. "
        "The plan includes two exploratory single-trial GPT-6.1 Sol 12,000-token attempts at 40 and 50 digits; these timed out and are shown in `summary.csv`, not in the main table.",
        "",
        "**Prerequisites if raw results are absent:** `uv`, `just`, and an OpenRouter key configured with `llm keys set openrouter`. "
        "The script loads the key through the `llm` plugin only when actually calling a model. "
        "To keep a different experiment separate, edit `plan.json`; new conditions add rows without erasing prior responses.",
        "",
        "**Problems and scoring.** Ten independent random positive `d`-digit operand pairs per digit length, deterministically generated with `random.Random(20261013 + d)`. "
        "All models receive the same operands, no leading zeroes. Python arbitrary-precision integers supply exact ground truth. "
        "The prompt is:",
        "",
        "```text",
        PROMPT,
        "```",
        "",
        "No tools are supplied; model-default reasoning is used. The cap applies to combined visible output and hidden reasoning. "
        "A numeric score checks the *last integer* in the response, permitting a correct answer embedded in prose; output-format compliance is separately measured. "
        "Empty responses and timeouts are tracked separately from incorrect products. "
        "`data/results.jsonl` stores all raw answers, operands, correct products, usage, duration and errors; local batch logs in `logs/` are excluded from Git.",
        "",
        "**Caveats.** A ten-item sample has large confidence intervals: even 10/10 is compatible with substantially lower true accuracy "
        "(a two-sided 95% Wilson lower bound is about 72%). Differences in provider, latency, timeouts, reasoning defaults and caps "
        "make a single universal digit ceiling misleading. Some models may use hidden internal arithmetic routines, but no external tools were offered in this test. "
        "OpenRouter model aliases and prices can change after this date; `data/pricing.json` freezes only a historical price snapshot.",
        "",
        "## Files",
        "",
        "- `plan.json`: fixed experiment coverage and budgets.",
        "- `run.py`: resumable OpenRouter calls and exact Python oracle.",
        "- `analyze.py`: regenerates this README and the two CSV summaries.",
        "- `data/results.jsonl`: append-only raw data; duplicates retained for cost provenance.",
        "- `data/pricing.json`: historical published prices per token.",
        "- `summary.csv`: all model/digit/budget conditions, including empty answers and errors.",
        "- `costs.csv`: per-model estimated identifiable charges for all recorded attempts.",
        "- `test_run.py`: tests the caching and resume contract without API calls.",
        "- `notes.md` and `logs/`: investigation trail.",
        "",
    ]
    cost_section = ["| Model | Logged API attempts | Priced replies | Estimated USD |",
                    "| :--- | ---: | ---: | ---: |"]
    cost_section += [f"| {r['model']} | {r['attempts']} | {r['priced_replies']} | ${r['estimated_usd']:.2f} |"
                     for r in prices]
    sol_50 = conditions.get((MODELS["sol"], 50, 4096))
    if sol_50:
        cost_section += [
            "",
            f"At 50 digits and a 4,096-token cap, GPT-6.1 Sol returned "
            f"**{sol_50['correct']}/{sol_50['planned']} exact products**: "
            f"{sol_50['no_answer']} empty replies "
            f"({sol_50['reasoning_cap_hit']} hit the token cap) and "
            f"{sol_50['errors']} API errors. "
            "The earlier HTTP 402/401 retry failures remain in the raw audit log, "
            "but the previously credit-blocked cases now have cached responses.",
            "",
        ]
    lines[lines.index("## Process and reproduction"):lines.index("## Process and reproduction")] = cost_section
    (ROOT / "README.md").write_text("\n".join(lines))
    print(f"{len(EXPECTED)} planned; {len(ALL)} logged; estimated identifiable charges US${total_cost:.2f}; {incomplete} missing attempts")


if __name__ == "__main__":
    main()
