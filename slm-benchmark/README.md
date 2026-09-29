# PGIM FinQA small-model benchmark

A paired benchmark of local-capable open-weight models and GPT-6 Luna on 100 FinQA questions, designed for the PGIM AI-enabled GCC demo.

The question is not "are SLMs cheaper?" It is: **which model tier earns its place on an investment-management workflow under local-deployment constraints, and where can prompt/harness engineering plus confidence-based escalation close the remaining gap?**

The PGIM discussion made privacy, control, regulation, and local execution the credible reasons to use smaller open-weight models. Cost, latency, accuracy, and calibration should be measured rather than assumed.

## Dataset: FinQA only

Use exactly 100 frozen questions from the FinQA test split.

FinQA is a good first benchmark because it uses real financial reports and combines narrative context, tables, and numerical reasoning. It has objective gold answers, so the first benchmark requires no LLM-as-judge.

Sources:

- https://github.com/EnvCommons/FinQA
- https://github.com/czyssrs/FinQA

### Sampling

The benchmark is frozen from FinQA commit `0f16e2867befa6840783e58be38c9efb9229d742` with seed `20260929`.

Before sampling, discard public-test records whose published human answer disagrees with FinQA's executable result after ordinary numeric rounding and percentage-unit normalization. This removes 142 internally inconsistent/noisy records, leaving 1,005 eligible cases across every operation family.

From those eligible cases:

- allocate the 100 root-operation quotas proportional to the square root of each operation's frequency, so common operations remain common without letting `divide` dominate the benchmark;
- within each root operation, allocate proportionally by 1-step, 2-step, and 3+-step complexity, with at least one example from each non-empty bucket where possible;
- sample deterministically within each stratum;
- give each model only the question plus FinQA's gold evidence snippets, not the full report, gold program, or retrieval output. This isolates model reasoning from retrieval quality;
- preserve both the published human answer and `exe_ans` for auditing. The published answer is the user-facing scoring target; `exe_ans` is an internal consistency check.

The frozen sample contains 37 divide, 17 subtract, 13 add, 11 multiply, 6 greater-than, and 16 table-aggregation questions; 64 are one-step, 28 two-step, and 8 three-or-more-step.

The same 100 questions must go to every model with the same prompt and inference settings wherever the APIs permit.

## Models

Assume local deployment with approximately 4-bit quantization and modest context windows. "Fits" is a deployment hypothesis to validate later; KV cache, runtime overhead, quantization format, multimodal encoders, and context length all affect actual memory.

### Core OpenRouter benchmark

| Tier | Model | OpenRouter ID | Hosted provider pin | Hosted quantization | Why include |
|---|---|---|---|---|---|
| <=8 GB GPU | Qwen3.5-9B | qwen/qwen3.5-9b | Darkbloom | FP4 | Strong current compact general model and a realistic 8GB-class candidate when quantized |
| <=8 GB GPU fallback | Granite 4.2-8B | ibm-granite/granite-4.2-8b | CoreWeave | BF16 | OpenRouter-available second compact family for a controlled API comparison |
| ~64 GB MacBook Pro | Qwen3.8-27B | qwen/qwen3.8-27b | Darkbloom | FP4 | Strong current open-weight model in the Mac-local size range |
| ~64 GB MacBook Pro | Gemma 4 31B | google/gemma-4-31b-it | CoreWeave | FP4 | Different model family, strong document understanding, and realistic Mac-local size when quantized |
| Frontier anchor | GPT-6 Luna | openai/gpt-6-luna | OpenAI | provider-managed | Low-cost current frontier reference point |

### Preferred local-only replacement for Granite

**Gemma 4 E4B** (google/gemma-4-E4B-it) is the preferred second <=8GB model.

Google describes E4B as 4.5B effective parameters / 8B total including embeddings, aimed at local/edge deployment. It should therefore be a particularly relevant local model for the PGIM story.

As of 2026-09-29, however, Gemma 4 E4B is **not present in OpenRouter's live model catalog**. OpenRouter currently lists Gemma 4 26B A4B and Gemma 4 31B, but not E4B.

Therefore:

1. Use Granite 4.2-8B only as the second compact model in the initial all-OpenRouter benchmark.
2. Add Gemma 4 E4B as a local inference run later, using the exact same 100 cases and prompt.
3. Once E4B appears on OpenRouter, replace Granite in the hosted comparison unless there is a reason to preserve both.

Sources:

- https://ai.google.dev/gemma/docs/core/model_card_4
- https://huggingface.co/google/gemma-4-E4B-it
- https://openrouter.ai/api/v1/models

## Response contract

Every request should return structured output equivalent to:

    {"answer": "...", "confidence": 87}

confidence means: **the model's estimated probability, from 0 to 100, that its final answer matches the FinQA gold answer.**

For numeric answers, the answer field should contain only the final answer required for evaluation, not prose or chain of thought. Do not request or store hidden reasoning.

Use JSON-schema structured output where the model/provider supports it. Where it does not, use the same textual contract and parse conservatively.

## First-pass inference settings

- Disable reasoning / thinking wherever the model permits it.
- Temperature 0 where supported.
- Keep output short; the benchmark needs only the final answer and confidence.
- Use the same prompt across models apart from unavoidable API syntax differences.
- Pin provider/model identity in results so reruns remain interpretable.
- Record malformed responses and retries explicitly rather than silently hiding them.

A later experiment may turn reasoning on for models where the first-pass result suggests that it changes the conclusion.

## What to log

For every (case, model) pair, retain:

- case ID and gold answer
- model ID and provider
- prompt version
- raw response
- parsed answer
- confidence
- correctness under the benchmark's normalized final-answer scorer; keep `exe_ans` as an audit check
- input tokens
- output tokens
- reasoning tokens if any
- OpenRouter usage.cost
- wall-clock latency
- request/retry metadata

For later local runs, also retain:

- hardware
- runtime
- quantization
- peak memory
- context configuration
- wall-clock latency
- energy usage if it can be captured cheaply

## Analysis

At minimum report:

- accuracy
- total and per-question cost
- median and p90 latency
- malformed/retry rate
- accuracy versus cost
- accuracy versus latency
- confidence calibration: Brier score, ECE, AUROC for correct-vs-wrong
- risk/coverage curve: accuracy retained as low-confidence cases are escalated

For the PGIM demo, the 100 cases are a model-selection demonstration. Do **not** both choose and validate a production confidence threshold on these same 100 observations. A later confidence-calibration exercise should use a larger, disjoint calibration and holdout sample.

## Rough hosted cost

Using the earlier planning assumption of roughly 120k input tokens + 6k output tokens across all 100 FinQA questions, hosted inference should remain tiny: generally around one to a few cents per model, depending on current provider pricing and retries.

Do not hard-code estimated prices into the benchmark results. Record OpenRouter's actual usage.cost for each completed request and compute totals from those observations.

The practical implication remains important: this benchmark is unlikely to show that local inference wins on token cost. Local models earn their place through control/privacy/offline execution if their measured quality is good enough.

## Execution plan

### Step 1 — Freeze the benchmark — completed

- Download/pin FinQA source data.
- Inspect the test-set schema and official evaluator.
- Select the 100-case stratified sample with a fixed seed.
- Save only the required frozen benchmark inputs plus provenance.
- Add a small validation script that proves there are exactly 100 unique cases and that gold answers/evaluator inputs are intact.
- Commit.

### Step 2 — Build the resumable runner — completed

Model it closely on ../jev/:

- models.json for the five initial OpenRouter models and inference settings
- prompt.md for the human-readable contract
- run.py for resumable (model, case) execution
- append-only JSONL result log
- structured-output parsing and explicit retry/error logging
- concurrency kept conservative enough to avoid rate-limit noise
- justfile commands for dry-run, smoke test, full run, and analysis
- never commit .env

Run only tiny smoke tests at this stage. Commit.

Implemented: all five hosted models use OpenRouter JSON-schema structured output; the runner is append-only and skips successful `(model, case)` pairs; it records raw output, parsed answer, confidence, correctness, actual OpenRouter cost, token counts, reasoning tokens, latency, provider, generation ID, attempts, and retry errors. Smoke outputs live under ignored `.build/`.

A one-case-per-model smoke test succeeded for all five models with zero reasoning tokens and zero retries. OpenRouter auto-routing selected different providers on repeated runs for Qwen3.8-27B and Gemma 4 31B, so provider pinning is intentionally deferred to Step 3 rather than silently allowing provider drift in the full measurement.

### Step 3 — Validate the measurement — completed

Provider pins are explicit and fallbacks are disabled: Darkbloom FP4 for both Qwens, CoreWeave BF16 for Granite, CoreWeave FP4 for Gemma 31B, and OpenAI for Luna. The chosen open-weight endpoints all support the structured-output and inference parameters used by the harness.

Five deliberately diverse cases were frozen in `data/validation_ids.txt`: one simple divide/percentage, one two-step percentage change, one 3+-step percentage calculation, one table average, and one yes/no comparison.

The 25-call crossed pilot passed the measurement checks:

- every response matched the structured `{answer, confidence}` contract;
- every request used the requested provider;
- all token, cost, latency, confidence, and provider fields were populated;
- reasoning tokens were zero throughout;
- there were zero retries and zero error rows;
- the normalized FinQA scorer behaved correctly on percentage, rounded numeric, and yes/no outputs.

Pilot accuracy was 5/5 for GPT-6 Luna and Qwen3.8-27B, 4/5 for Gemma 4 31B, 3/5 for Qwen3.5-9B, and 1/5 for Granite 4.2-8B. This sample is diagnostic rather than inferential, but it already confirms that the benchmark has useful separation. Smaller-model errors were often assigned very high confidence, which makes the later calibration/escalation phase especially relevant.

The validated 25 rows are retained as the first completed slice of `data/results.jsonl`; Step 4 resumes the remaining 95 cases per model rather than paying to repeat them.

### Step 4 — Run the 100-question OpenRouter benchmark — completed

The full 500-pair baseline is complete: 100 frozen FinQA cases x five models, with zero terminal error rows and zero reasoning tokens.

Headline first-pass accuracy:

| Model | Accuracy | Hosted cost / 100 | Median successful-call latency |
|---|---:|---:|---:|
| GPT-6 Luna | 83% | $0.00372 | 1.04 s |
| Qwen3.8-27B FP4 | 76% | $0.00528 | 1.39 s |
| Gemma 4 31B FP4 | 70% | $0.00347 | 0.84 s |
| Qwen3.5-9B FP4 | 41% | $0.00334 | 1.19 s |
| Granite 4.2-8B BF16 | 25% | $0.00278 | 0.56 s |

These are baseline results only; Step 5 will analyze uncertainty, operation difficulty, failures, and risk/coverage before drawing workflow implications.

Twenty-one canonical rows required retrying: 20 Granite/CoreWeave rows and one Qwen3.8/Darkbloom row, for 29 extra attempts in total. Every retry was an upstream HTTP 429 rate-limit response; there were no schema/parsing/model-output retries. Report retry rate separately from successful-call latency.

During this run, the remote command session timed out while the paid process continued, and overlapping continuation produced 230 duplicate successful calls for later models. The benchmark therefore canonicalizes to the **first successful response per (model, case)**. The canonical 500-pair benchmark cost $0.01859; accidental duplicate calls added $0.00905, for actual API spend of $0.02765. `data/run_metadata.json` records the anomaly and canonical result hash.

An inter-process runner lock was added after this incident so concurrent paid runs fail closed instead of issuing duplicate calls. `scripts/validate_results.py` also rejects duplicate successful pairs.

Commit code and canonical results; keep secrets and the ignored raw duplicate log out of git.

### Step 5 — Analyze and build the PGIM-facing result — completed

`analyze.py` now regenerates `data/summary.json` and a standalone `index.html` executive report from the canonical result log.

Main findings:

- GPT-6 Luna leads at 83%; Qwen3.8-27B FP4 reaches 76%; Gemma 4 31B FP4 reaches 70%.
- The 8GB-class hosted baselines are substantially weaker: Qwen3.5-9B at 41%, Granite 4.2-8B at 25%.
- Raw stated confidence is **not yet useful enough for routing**. Confidence AUROC is 0.538 for Qwen3.8-27B and 0.510 for Gemma 31B; both are close to random ordering of correct vs incorrect answers. They also make 22 and 29 errors respectively at >=90% stated confidence.
- Consequently, a same-sample 50%-local confidence route reaches only 77% with Qwen3.8-27B and 75% with Gemma 31B, below Luna's 83%.
- There is meaningful routing headroom if uncertainty detection can be improved: an oracle that escalates exactly the local model's errors would reach 90% with either Qwen3.8-27B or Gemma 31B. This is an upper bound, not an achievable policy.
- Model diversity is useful: Luna misses 17 questions; at least one local-sized model answers 9 of those correctly. Only 8 questions are missed by all five models.
- Operation type and reasoning depth expose useful failure structure; the report includes those breakdowns plus representative high-confidence errors.

Do not choose a production threshold from these same 100 cases. The next calibration/routing experiment should use separate calibration and holdout data.

### Expanded diverse-model benchmark — completed

The benchmark now contains **11 models x 100 FinQA questions = 1,100 canonical successful pairs**. Six additional model families were added:

- GLM 5.3 Flash
- Ministral 3 8B
- DeepSeek V4.1 Flash
- MiMo-V2.6-Flash
- Nemotron 3 Super 120B-A12B
- Ling 3.0 Flash Fin

Expanded results:

| Model | Accuracy | Cost / 100 | Notes |
|---|---:|---:|---|
| GPT-6 Luna | 83% | $0.00372 | Frontier anchor |
| MiMo-V2.6-Flash | 80% | $0.00354 | Best non-Luna |
| GLM 5.3 Flash | 79% | $0.00101 | Cheapest Pareto-frontier model; endpoint requires low-effort reasoning |
| Ling 3.0 Flash Fin | 77% | $0.00213 | Finance-specialized |
| Qwen3.8-27B | 76% | $0.00528 | Dense local-sized baseline |
| Nemotron 3 Super 120B-A12B | 74% | $0.00318* | Free NVIDIA endpoint used; cost is paid-equivalent DeepInfra token pricing |
| DeepSeek V4.1 Flash | 72% | $0.00383 | FP8 sparse model |
| Gemma 4 31B | 70% | $0.00347 | Dense local-sized baseline |
| Ministral 3 8B | 55% | $0.00432 | Best compact / 8B-class model |
| Qwen3.5-9B | 41% | $0.00334 | Compact baseline |
| Granite 4.2-8B | 25% | $0.00278 | Compact baseline |

The generated `index.html` now opens with an interactive **log-scale cost-vs-quality scatter plot**. The Pareto frontier is drawn explicitly; hover/tap reveals quick values, and clicking a point opens a bookmarkable detail popup with provider, quantization, latency, confidence calibration, operation strengths/weaknesses, and representative high-confidence errors. The previous “models to add next” recommendation table has been removed.

Two comparability caveats are shown directly in the report rather than hidden:

1. GLM 5.3 Flash's pinned endpoint requires reasoning, so it ran at low reasoning effort with reasoning text excluded; the other ten models ran with reasoning disabled.
2. Both paid Nemotron endpoints were persistently rate-limited during the benchmark. The canonical run therefore uses OpenRouter's NVIDIA free endpoint on this public dataset; its chart X-position uses current DeepInfra paid-equivalent input/output token rates.

The page is responsive, has light/dark mode, keyboard-accessible chart points and horizontally scrollable tables, and popup state is captured in the URL hash. Browser testing reports zero WCAG A/AA violations; SVG color-contrast remains flagged only for manual review by the automated checker.

Commit.

### Step 6 — Add Gemma 4 E4B local parity run

Once the hosted benchmark is stable:

- choose a reproducible E4B quantization/runtime
- run the exact same 100 questions locally
- measure local latency and memory
- compare its answer quality directly with Qwen3.5-9B, Granite, the Mac-class models, and Luna

If OpenRouter adds E4B before this step, prefer an OpenRouter parity run first and optionally add the true-local measurement separately.

Commit.

### Later — Prompt optimization and calibrated escalation

After the baseline is frozen:

1. use a strong model to optimize the prompt for one or more useful small models without changing the test set
2. evaluate prompt changes on a separate development/calibration subset
3. calibrate confidence
4. construct a route such as "local model first; GPT-6 Luna only below the calibrated threshold"
5. compare final workflow quality, escalation rate, latency, and cost against using Luna for everything

This should be a separate experimental phase so the baseline remains auditable.
