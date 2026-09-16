# Confidence calibration

<!--

Sources:

- [Confidence Calibration benchmark v1](https://chatgpt.com/c/6aa10fc4-8d30-83ec-a388-55339c129818)
- [Confidence Calibration benchmark v2](https://chatgpt.com/c/6aa12238-b530-83ec-a4b8-fa7e56760d97)

-->

A reproducible BANKING77 experiment asking a practical question:

> When an LLM says it is 95% confident, is it actually correct about 95% of the time—and what score is safe enough to skip human review?

Published page: <https://sanand0.github.io/llmevals/confidence-calibration/>

The benchmark uses **770 real BANKING77 support requests**: 10 examples from each of 77 fine-grained intents. Every prediction is checked by exact match against the benchmark gold label; there is no LLM judge.

## Findings

### Raw confidence is overconfident

| Model | Accuracy | Mean stated confidence | Gap | Error among ≥95% |
|---|---:|---:|---:|---:|
| GPT-4.1 Nano | 61.0% | 87.1% | +26.1 pt | 21.8% |
| GPT-5.6 Luna (`reasoning=none`) | 84.0% | 95.7% | +11.6 pt | 10.3% |

The useful business view is **risk vs coverage**: at each threshold, measure the fraction of cases that would bypass review and the actual error rate among those auto-passed cases.

### Prompt wording improves calibration

The same GPT-5.6 Luna model is rerun on the same 770 cases while changing only the confidence instruction.

| Confidence instruction | Accuracy | Mean confidence | ECE ↓ | Brier ↓ | Error among ≥95% |
|---|---:|---:|---:|---:|---:|
| Baseline | 84.0% | 95.7% | 0.116 | 0.1231 | 10.3% |
| Okay to be uncertain | 84.5% | 90.7% | 0.061 | **0.0968** | 4.3% |
| Strongest alternative | 84.9% | 92.4% | 0.074 | 0.1029 | **3.7%** |
| Top-two probability | 84.8% | 90.0% | **0.053** | **0.0968** | 3.9% |

The exact prompt fragments are defined once in `scripts/prompt_fragments.py` and displayed verbatim on the page. A five-variant 154-case screen is used to test new elicitation mechanisms cheaply before promoting the best candidate to all 770 cases.

### Frozen logprob routing generalizes at the 5% target

A prospective test fit the calibration and routing cutoffs on the original 770 cases, froze them, then ran the remaining **2,310 untouched BANKING77 test requests** with no retuning.

| Frozen signal | Training coverage at ≤5% error | Holdout coverage | Holdout observed error | Auto-passed |
|---|---:|---:|---:|---:|
| Token logprob | 65.2% | **65.2%** | 4.38% | **1,506 / 2,310** |
| Stated confidence | 43.1% | 41.2% | **2.63%** | 951 / 2,310 |

The logprob rule removed substantially more review while staying below the predeclared 5% observed-error target. But the conclusion is target-specific: the separately frozen 10% logprob cutoff produced **12.0%** holdout error, so one validated cutoff does not imply the entire risk curve transfers.

Frozen calibration itself was nearly tied on the holdout: logprob Brier **0.1105** versus stated-confidence **0.1130**; the paired 95% bootstrap interval for the difference crosses zero. The strongest supported claim is therefore **better routing coverage at the validated 5% cutoff**, not universally better calibrated probabilities.

### Irrelevant context can distort confidence

The exact same 770 requests are replayed with 0, 500, or 2,000 words of neutral, explicitly incidental metadata.

| Model | Added context | Accuracy | Mean confidence | Gap | Brier |
|---|---:|---:|---:|---:|---:|
| Nano | 0 | 61.2% | 84.2% | +23.0 pt | 0.2688 |
| Nano | 500 | 61.4% | 89.5% | +28.1 pt | 0.2909 |
| Nano | 2,000 | 60.1% | 90.3% | +30.1 pt | 0.3069 |
| Luna | 0 | 85.7% | 96.1% | +10.4 pt | 0.1121 |
| Luna | 500 | 85.2% | 96.1% | +10.9 pt | 0.1158 |
| Luna | 2,000 | 85.3% | 96.2% | +10.8 pt | 0.1179 |

For Nano, adding 2,000 irrelevant words raises confidence by about 6.1 points without improving accuracy; paired Brier deterioration is about +0.038 with a 95% bootstrap interval entirely above zero. Luna is comparatively stable under the same manipulation.

This tests robustness to irrelevant context volume, not behavior on genuinely information-rich long documents.

### Logprobs rank risk better—but raw probabilities are worse

A fourth paired experiment asks whether the model's internal first-token probability is a better confidence signal than its stated confidence. GPT-5.6 Luna sees the same 770 BANKING77 requests. Each request gets a deterministic random mapping from the 77 intents to 77 single-character codes; the model emits the chosen code first and then its **Top-two** stated confidence. The first output token therefore identifies the same class whose stated confidence follows in the same call.

| Signal | Raw mean score | Raw Brier ↓ | Cross-fitted calibrated Brier ↓ | AUROC for correctness ↑ | Coverage at ≤5% error ↑ |
|---|---:|---:|---:|---:|---:|
| First-token logprob | 98.4% | 0.148 | **0.102** | **0.830** | **65.2%** |
| Stated Top-two confidence | 88.2% | **0.119** | 0.116 | 0.783 | 43.1% |

The distinction matters: **raw logprobs are not better calibrated probabilities**. Luna is 83.6% correct, yet the raw first-token probability averages 98.4%; 435/770 probabilities are effectively 100%, including 18 wrong predictions. But logprobs rank correct vs. incorrect cases more effectively. Cross-fitted Platt calibration looked better on the 770 development cases, but the 2,310-case prospective holdout did not establish a clear probability-calibration advantage, so calibration is not the main result.

Risk–coverage depends only on ordering. The curve now uses only thresholds that could actually be deployed and never splits cases with identical scores. At a 5% observed-error budget, the attainable logprob cutoff auto-passes 65.2% of development cases versus 43.1% for stated confidence. Spearman correlation between the raw signals is 0.57: related, but far from interchangeable. Naïve equal-count deciles are avoided because they can split large score ties; a log scale on raw probability also does little to separate values concentrated near 1.

This experiment uses OpenAI Chat Completions because direct capability probes returned token logprobs there for both evaluated models. The original experiments used Responses, so comparisons to the earlier sections are historical context; the **logprob-vs-stated comparison itself is paired within the same new Chat Completions call**. A Nano preflight was not promoted because the arbitrary one-token code protocol materially reduced its classification accuracy, making it a poor apples-to-apples replication.

## Layout

```text
confidence-calibration/
├── index.html                         # generated GitHub Pages entry point
├── data.json                          # generated page payload
├── *.csv                              # generated/downloadable Pages data
├── src/
│   └── index.html                     # editable page template
├── scripts/
│   ├── common.py                      # portable project paths + lazy API key lookup
│   ├── prepare.py                     # deterministic BANKING77 sampling
│   ├── run_benchmark.py               # resumable baseline runner
│   ├── screen_prompt_variants.py      # resumable 154-case prompt screen
│   ├── prompt_calibration_experiment.py
│   ├── input_length_experiment.py
│   ├── logprob_experiment.py           # paired one-token logprob + stated-confidence runner
│   ├── analyze_prompt_variants.py
│   ├── analyze_input_length.py
│   ├── analyze_logprobs.py             # cross-fitted calibration + risk/coverage analysis
│   └── build_site.py
├── data/
│   ├── banking77-test.csv             # source test split
│   ├── banking77-sample.csv           # deterministic 770-case sample
│   ├── results.csv                    # cached baseline API outputs
│   ├── prompt-screen-results.csv      # cached prompt screen outputs
│   ├── prompt-variant-results.csv     # cached full prompt outputs
│   ├── input-length-results.csv       # cached length-stress outputs
│   └── logprob-results.csv            # cached paired logprob/stated-confidence outputs
├── .build/                            # ignored, reproducible derived summaries
├── archive/                           # ignored, older exploratory extraction work
├── justfile
├── README.md
└── REPORT.md
```

The generated root files deliberately duplicate selected data from `data/`: GitHub Pages needs them at `.../confidence-calibration/<file>`, while the canonical cached experiment data lives under `data/`.

## Rebuild

From this directory:

```bash
just build
```

`just build`:

1. ensures the deterministic 770-case sample exists;
2. fills only missing baseline rows for Nano and Luna;
3. fills only missing prompt-screen rows;
4. fills only missing full prompt-variant rows;
5. fills only missing paired Luna logprob/stated-confidence rows;
6. fills only missing input-length rows for both models and all three conditions;
7. regenerates statistical summaries, including cross-fitted logprob calibration;
8. writes `index.html`, `data.json`, and downloadable CSVs directly into this directory for GitHub Pages.

All API outputs are cached under `data/`. Each runner writes a completed row immediately and keys completion by experimental condition plus case ID, so interrupted runs resume.

A cache-complete build **does not require an API key**. If missing rows need to be generated, the runners use `OPENAI_API_KEY` if set; otherwise they try `llm keys get openai`. There are no hard-coded paths to another checkout or `.env` file.

Useful commands:

```bash
just site                                      # analyses + Pages files; no API calls
just benchmark gpt-5.6-luna                   # fill missing baseline rows
just logprobs                                  # fill missing Luna logprob-pair rows
just holdout 16                                  # fill missing prospective holdout rows
just length gpt-5.6-luna long                 # fill one input-length condition
just prepare 10                               # ensure 10 cases per intent
just serve                                    # http://127.0.0.1:8000/
```

There is intentionally no deploy step. Committing the generated root files in the `llmevals` repository is sufficient for the existing GitHub Pages site.

## Metrics and validity

- **Calibration gap** = mean stated confidence − empirical accuracy.
- **Reliability curve** = actual correctness within confidence bands versus stated confidence.
- **Brier score** = mean squared error of the probability assigned to “my chosen answer is correct”; lower is better.
- **ECE** = weighted calibration error across fixed confidence bands; lower is better.
- **Coverage** = fraction auto-passed at a threshold.
- **Risk** = error rate among auto-passed cases.
- **AUROC for correctness** = how well a score ranks correct cases above incorrect ones; it measures discrimination, not literal probability calibration.
- **Cross-fitted Platt calibration** = the same monotonic two-parameter calibration applied to each signal using only other cases; this makes Brier comparisons out-of-sample.

Gold labels are independent of the evaluated model. Prompt and input-length comparisons use the same cases pairwise. Screening results are used only to select candidates; headline prompt conclusions use all 770 cases. Production thresholds should be learned on project-specific historical data and confirmed on a separate holdout.
