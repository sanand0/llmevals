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
│   ├── analyze_prompt_variants.py
│   ├── analyze_input_length.py
│   └── build_site.py
├── data/
│   ├── banking77-test.csv             # source test split
│   ├── banking77-sample.csv           # deterministic 770-case sample
│   ├── results.csv                    # cached baseline API outputs
│   ├── prompt-screen-results.csv      # cached prompt screen outputs
│   ├── prompt-variant-results.csv     # cached full prompt outputs
│   └── input-length-results.csv       # cached length-stress outputs
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
5. fills only missing input-length rows for both models and all three conditions;
6. regenerates statistical summaries;
7. writes `index.html`, `data.json`, and downloadable CSVs directly into this directory for GitHub Pages.

All API outputs are cached under `data/`. Each runner writes a completed row immediately and keys completion by experimental condition plus case ID, so interrupted runs resume.

A cache-complete build **does not require an API key**. If missing rows need to be generated, the runners use `OPENAI_API_KEY` if set; otherwise they try `llm keys get openai`. There are no hard-coded paths to another checkout or `.env` file.

Useful commands:

```bash
just site                                      # analyses + Pages files; no API calls
just benchmark gpt-5.6-luna                   # fill missing baseline rows
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

Gold labels are independent of the evaluated model. Prompt and input-length comparisons use the same cases pairwise. Screening results are used only to select candidates; headline prompt conclusions use all 770 cases. Production thresholds should be learned on project-specific historical data and confirmed on a separate holdout.
