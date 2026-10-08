# Decision models vs frontier LLMs on BANKING77

<!-- https://chatgpt.com/c/6aabb0bc-2888-83ec-b5ed-374329c52bca -->

A paired benchmark of 17 decision-model and general-purpose LLM systems on 77 BANKING77 support-routing cases: one frozen case per intent.

## Reproduce

Credentials depend on the provider: OpenRouter uses `llm keys get openrouter` (or `OPENROUTER_API_KEY`), OpenAI Decisions uses `llm keys get openai` (or `OPENAI_API_KEY`), and Clef/Clef-flash use the existing authenticated Cloudflare CLI account (`cf auth whoami`).

```bash
just dry-run       # should be 0 pending with the checked-in results
just run           # runs only missing (model, case) pairs
just analyze       # rebuilds summary.json, results.csv, and index.html
```

Run selected models or a cheap preflight directly:

```bash
uv run run.py --models decider_v1_1 liquid_d1 kev4b mercury_decide --limit 1
uv run run.py --models clef_flash mercury_decide liquid_d1 --concurrency 4
```

`data/results.jsonl` is append-only. The runner loads completed `(model_key, case_id)` pairs before making calls, so interrupted runs resume without repeating completed work. `analyze.py` also deduplicates by that key before computing metrics.

## 8 Oct 2026 additions

The OpenRouter Decisions leaderboard was used as the starting point, then filtered for public visibility and compatibility with a single 77-way `choice`. Added:

- **Perplexity Decider v1.1 27B** — newly released successor to Decider V1; explicitly requested for this benchmark.
- **Liquid d1** — among the most-used new decision models on OpenRouter and newly open-weight.
- **Kev 4B** — compact open-weight Qwen3.5-based decision model with rapidly rising OpenRouter usage.
- **Mercury Decide** — free Jev-compatible decision model from Inception with substantial OpenRouter usage.

Popular candidates deliberately **not** added because they cannot express this benchmark natively:

- **Span-01 Lite** — specialized Noul/behavior scoring, not a 77-way Choice classifier; the preflight returned HTTP 400.
- **Solar Decide** — Choice supports at most 26 options; the 77-way preflight returned HTTP 422.
- **Tev1 4B Experimental** — Choice is limited to at most 20 options.

The four completed additions cost **$0.00569 total including preflights**, comfortably below the $1 incremental budget.

OpenRouter Decisions ranking: https://openrouter.ai/rankings/decisions

## Frozen inputs

- `data/cases.csv`: 77 cases, exactly one from each BANKING77 category. The sample was drawn from the existing `confidence-calibration` benchmark with seed `20260918` and is now frozen here.
- `models.json`: model IDs and inference settings.
- `prompt.md`: human-readable prompt contract. `run.py` contains the executable form.

## Outputs

- `data/results.jsonl`: full API results, including full 77-way probability distributions from the decision-model systems.
- `data/results.csv`: flat analysis-friendly result table.
- `summary.json`: computed metrics by model.
- `index.html`: executive explanation of findings.

## Metric notes

Accuracy is exact match to the BANKING77 gold label; there is no LLM judge. Confidence calibration uses the model-reported probability of its chosen label. Brier/ECE evaluate probability quality; AUROC evaluates whether confidence ranks correct predictions above errors. The risk/coverage statistic is exploratory because its threshold is chosen and evaluated on the same 77 cases.

Cost uses measured token usage. OpenRouter-backed systems use per-response `usage.cost`; OpenAI Decisions is computed from current GPT-6 Luna direct API token prices; Clef/Clef-flash use Cloudflare's listed $0.24/M and $0.09/M input-token prices. Cloudflare's daily free Workers AI allocation can make actual billed cost lower. Development retries are excluded, and all pricing is point-in-time rather than a promise of future pricing.

Latency is observed end-to-end from this machine and is not a pure model-execution benchmark because provider/network paths differ.

Current API/pricing references:

- OpenAI Decisions: https://developers.openai.com/api/reference/resources/decisions/methods/create
- OpenAI pricing: https://developers.openai.com/api/docs/pricing
- Clef: https://developers.cloudflare.com/ai/models/%40cf/cloudflare/clef/
- Clef-flash: https://developers.cloudflare.com/ai/models/%40cf/cloudflare/clef-flash/
- Workers AI pricing/free allocation: https://developers.cloudflare.com/workers-ai/platform/pricing/
- Perplexity Decider v1.1: https://openrouter.ai/perplexity/pplx-decider-v1.1-27b
- Liquid d1: https://openrouter.ai/liquid/d1
- Kev 4B: https://openrouter.ai/jaredpalmer/kev-4b
- Mercury Decide: https://openrouter.ai/inception/mercury-decide%3Afree
