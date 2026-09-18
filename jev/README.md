# Jev vs frontier LLMs on BANKING77

<!-- https://chatgpt.com/c/6aabb0bc-2888-83ec-b5ed-374329c52bca -->

A small paired benchmark of Jev and eight general-purpose LLMs on 77 BANKING77 support-routing cases: one frozen case per intent.

## Reproduce

OpenRouter credentials are read from `llm keys get openrouter` first, then `OPENROUTER_API_KEY`.

```bash
just dry-run       # should be 0 pending with the checked-in results
just run           # runs only missing (model, case) pairs
just analyze       # rebuilds summary.json, results.csv, and index.html
```

Run selected models or a cheap preflight directly:

```bash
uv run run.py --models jev gemini deepseek --limit 1
uv run run.py --models astra gemini --concurrency 4
```

`data/results.jsonl` is append-only. The runner loads completed `(model_key, case_id)` pairs before making calls, so interrupted runs resume without repeating completed work. `analyze.py` also deduplicates by that key before computing metrics.

## Frozen inputs

- `data/cases.csv`: 77 cases, exactly one from each BANKING77 category. The sample was drawn from the existing `confidence-calibration` benchmark with seed `20260918` and is now frozen here.
- `models.json`: model IDs and inference settings.
- `prompt.md`: human-readable prompt contract. `run.py` contains the executable form.

## Outputs

- `data/results.jsonl`: full API results, including Jev's 77-way probability distributions.
- `data/results.csv`: flat analysis-friendly result table.
- `summary.json`: computed metrics by model.
- `index.html`: executive explanation of findings.

## Metric notes

Accuracy is exact match to the BANKING77 gold label; there is no LLM judge. Confidence calibration uses the model-reported probability of its chosen label. Brier/ECE evaluate probability quality; AUROC evaluates whether confidence ranks correct predictions above errors. The risk/coverage statistic is exploratory because its threshold is chosen and evaluated on the same 77 cases.

Costs come from OpenRouter's per-response `usage.cost` for successful calls. They exclude development-time malformed-response retries and are not a promise of future pricing.
