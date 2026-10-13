# How large can frontier LLMs multiply numbers?

**13 October 2026 · OpenRouter · ten shared random problems per main condition · no tools.**

## Results

**Takeaway:** GPT-6.1 Sol solved all 10/10 questions through **35-digit × 35-digit** operands. Claude Sonnet 5.5 solved **10/10 at 40 digits** with 12k output tokens, while Claude Opus 5.5 solved **7/10 at 40 digits** and **5/10 at 50 digits** at that budget. These are screening samples: 10/10 does **not** prove high real-world reliability.

| Model | 2 | 4 | 6 | 8 | 12 | 15 | 20 | 30 | 35 | 40 | 50 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| openai/gpt-6.1-sol | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 0/10† | 0/10† |
| anthropic/claude-opus-5.5 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 9/10† | – | 7/10 | 5/10† |
| anthropic/claude-sonnet-5.5 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 9/10 | 10/10 | – | 10/10 | 6/10† |
| google/gemini-3.8-flash | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 8/10 | 2/10 | 0/10 | – | – | – |
| openai/gpt-6-luna | 10/10 | 10/10 | 10/10 | 8/10 | 8/10 | 9/10 | – | – | – | – | – |
| google/gemini-3.1-pro-preview | 10/10 | 10/10 | 10/10 | 10/10 | 8/10 | 2/10 | – | – | – | – | – |
| qwen/qwen3.8-max-0902 | 10/10 | 10/10 | 10/10 | 10/10 | 1/10† | 0/10† | – | – | – | – | – |
| x-ai/grok-4.7 | 10/10 | 10/10 | 10/10 | 8/10† | 5/10† | 0/10† | – | – | – | – | – |
| deepseek/deepseek-v4-pro | 10/10 | 7/10 | 4/10 | 1/10 | 3/10 | 0/10 | – | – | – | – | – |

Cells = exact products / attempted problems. **†** marks at least one unanswered response (reasoning-cap exhaustion or API error); don't interpret all missing answers as mathematical mistakes. **–** = not tested. The table uses the largest tested output cap for each model/length (4,096, 12,000, or 20,000 tokens), except GPT-6.1 Sol where only the 4,096-token sweep completed sufficiently for comparison. See `summary.csv` for all budgets and for the count of genuinely wrong, empty, and errored responses.

### Most informative contrasts

- **Reasoning tokens beat first impressions.** Sonnet 5.5 was 2/10 at 30 digits with a 4,096-token cap (eight empty replies); the **same problems** were 10/10 with 12,000 tokens. At 40 digits it reached 10/10 with 12,000 tokens. At 50 digits its score rose from 2/10 at 12,000 tokens to 6/10 at 20,000 tokens (with one timeout).
- **GPT-6.1 Sol's measured success extends to 35 digits.** At 40–50 digits, the 4,096-token tests largely exhausted the budget or timed out. That is *not* a demonstrated hard arithmetic ceiling.
- **Arithmetic and missing responses differ.** Gemini 3.8 Flash dropped to 2/10 at 20 digits and 0/10 at 30 digits with actual numeric answers; by contrast, some other models produced no final number after using their available reasoning tokens.
- **Accuracy is not necessarily monotonic in ten samples.** Small samples and heterogeneous failures can make a model appear better on 15 digits than 12 digits. Replicate near any chosen cutoff.

### Cost and coverage

**About US$16.62 estimated identifiable inference charges** across 961 recorded API attempts (851 priced replies), including duplicate attempts from the earlier remote-timeout/replay. Computed from reported input/output tokens using frozen OpenRouter prices in `data/pricing.json`; **not an OpenRouter invoice or a lower bound on actual charges**. Timed-out requests might still have incurred charges that are invisible to this log. See `costs.csv` for per-model amounts and tokens.

The fixed plan covers **712 model × length × trial × budget combinations**; 712 have at least one recorded attempt, 0 remain unattempted. API errors (including HTTP 402 insufficient OpenRouter credits) are persisted as observed outcomes, not automatically retried by `just build`. This prevents unexpected spending and keeps rebuilds instant; `just retry-errors` is the explicit paid retry action after topping up credits.

| Model | Logged API attempts | Priced replies | Estimated USD |
| :--- | ---: | ---: | ---: |
| anthropic/claude-opus-5.5 | 120 | 117 | $5.71 |
| anthropic/claude-sonnet-5.5 | 120 | 119 | $4.72 |
| google/gemini-3.1-pro-preview | 67 | 67 | $2.26 |
| google/gemini-3.8-flash | 112 | 112 | $1.20 |
| openai/gpt-6.1-sol | 152 | 99 | $1.09 |
| x-ai/grok-4.7 | 118 | 79 | $0.94 |
| qwen/qwen3.8-max-0902 | 95 | 87 | $0.55 |
| deepseek/deepseek-v4-pro | 117 | 111 | $0.14 |
| openai/gpt-6-luna | 60 | 60 | $0.01 |

At 50 digits and a 4,096-token cap, GPT-6.1 Sol returned **0/10 exact products**: 8 empty replies (8 hit the token cap) and 2 API errors. The earlier HTTP 402/401 retry failures remain in the raw audit log, but the previously credit-blocked cases now have cached responses.

## Process and reproduction

Run from this directory:

```bash
just build          # reproduce README.md, summary.csv, costs.csv; skip saved API calls
just check          # show missing attempts without calling an LLM
just test           # offline reproducibility tests
just retry-credits  # optional: retry only HTTP 402 cases after adding credits (PAID)
just retry-errors   # optional: reattempt every failed/timeout request (PAID)
```

`just build` first checks each planned (model, digits, trial, reasoning, prompt hash, token budget). If `data/results.jsonl` has that attempt (including a recorded error), it makes **zero API calls**. If the results file is deleted, all planned tests are re-run. If interrupted, completed JSONL rows are retained and only missing attempts are scheduled on the next run. Deleting `summary.csv`, `costs.csv`, or `README.md` regenerates them locally without spending anything. New API responses are not guaranteed to be byte-identical because model inference and provider routing can vary. The plan includes two exploratory single-trial GPT-6.1 Sol 12,000-token attempts at 40 and 50 digits; these timed out and are shown in `summary.csv`, not in the main table.

**Prerequisites if raw results are absent:** `uv`, `just`, and an OpenRouter key configured with `llm keys set openrouter`. The script loads the key through the `llm` plugin only when actually calling a model. To keep a different experiment separate, edit `plan.json`; new conditions add rows without erasing prior responses.

**Problems and scoring.** Ten independent random positive `d`-digit operand pairs per digit length, deterministically generated with `random.Random(20261013 + d)`. All models receive the same operands, no leading zeroes. Python arbitrary-precision integers supply exact ground truth. The prompt is:

```text
Multiply these two integers exactly:
{a} * {b}
Return ONLY the decimal integer, without commas or explanation.
```

No tools are supplied; model-default reasoning is used. The cap applies to combined visible output and hidden reasoning. A numeric score checks the *last integer* in the response, permitting a correct answer embedded in prose; output-format compliance is separately measured. Empty responses and timeouts are tracked separately from incorrect products. `data/results.jsonl` stores all raw answers, operands, correct products, usage, duration and errors; local batch logs in `logs/` are excluded from Git.

**Caveats.** A ten-item sample has large confidence intervals: even 10/10 is compatible with substantially lower true accuracy (a two-sided 95% Wilson lower bound is about 72%). Differences in provider, latency, timeouts, reasoning defaults and caps make a single universal digit ceiling misleading. Some models may use hidden internal arithmetic routines, but no external tools were offered in this test. OpenRouter model aliases and prices can change after this date; `data/pricing.json` freezes only a historical price snapshot.

## Files

- `plan.json`: fixed experiment coverage and budgets.
- `run.py`: resumable OpenRouter calls and exact Python oracle.
- `analyze.py`: regenerates this README and the two CSV summaries.
- `data/results.jsonl`: append-only raw data; duplicates retained for cost provenance.
- `data/pricing.json`: historical published prices per token.
- `summary.csv`: all model/digit/budget conditions, including empty answers and errors.
- `costs.csv`: per-model estimated identifiable charges for all recorded attempts.
- `test_run.py`: tests the caching and resume contract without API calls.
- `notes.md` and `logs/`: investigation trail.
