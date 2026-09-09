# Confidence calibration experiment — 2026-09-09

## Bottom line

Three findings survive the expanded 770-case BANKING77 benchmark:

1. **Raw LLM confidence is materially overconfident.** Nano is 61.0% accurate while averaging 87.1% confidence; Luna is 84.0% accurate while averaging 95.7% confidence.
2. **Prompting can make confidence much more useful without making the classifier materially more accurate.** On Luna, “okay to be uncertain” and “top-two probability” reduce Brier score from 0.1231 to 0.0968; ≥95% error drops from 10.3% to about 4%.
3. **Confidence robustness is model-dependent.** Adding 2,000 words of irrelevant neutral metadata raises Nano confidence by about 6.1 points without improving accuracy and significantly worsens Brier score. Luna is essentially stable under the same manipulation.

The practical lesson is not “trust confidence after prompt engineering.” It is: **design the score, stress-test it, then empirically learn the review threshold from historical gold data.**

## Baseline: 770 support requests

| Model | Accuracy | Mean confidence | Gap | Error among ≥95% |
|---|---:|---:|---:|---:|
| GPT-4.1 Nano | 61.0% | 87.1% | +26.1 pt | 21.8% |
| GPT-5.6 Luna (`reasoning=none`) | 84.0% | 95.7% | +11.6 pt | 10.3% |

For Luna, a ≥99% rule auto-passes 55.8% of cases with 3.0% observed error. That is much safer than ≥95%, but still not evidence that “99” literally means 99% correct.

## Prompt calibration: same Luna, same 770 cases

| Prompt | Accuracy | Mean confidence | ECE ↓ | Brier ↓ | ≥95% error |
|---|---:|---:|---:|---:|---:|
| Baseline | 84.0% | 95.7% | 0.116 | 0.1231 | 10.3% |
| Okay to be uncertain | 84.5% | 90.7% | 0.061 | **0.0968** | 4.3% |
| Strongest alternative | 84.9% | 92.4% | 0.074 | 0.1029 | **3.7%** |
| Top-two probability | 84.8% | 90.0% | **0.053** | **0.0968** | 3.9% |

A five-way 154-case screen identified top-two probability as the strongest new candidate; it was then promoted to all 770 cases. Its full-run Brier improvement versus baseline is statistically clear under a paired bootstrap.

## Input length: 0 vs 500 vs 2,000 irrelevant words

The same 770 tickets were replayed with neutral metadata that the prompt explicitly marks as incidental.

| Model | Padding | Accuracy | Confidence | Gap | Brier |
|---|---:|---:|---:|---:|---:|
| Nano | 0 | 61.2% | 84.2% | +23.0 pt | 0.2688 |
| Nano | 500 | 61.4% | 89.5% | +28.1 pt | 0.2909 |
| Nano | 2,000 | 60.1% | 90.3% | +30.1 pt | 0.3069 |
| Luna | 0 | 85.7% | 96.1% | +10.4 pt | 0.1121 |
| Luna | 500 | 85.2% | 96.1% | +10.9 pt | 0.1158 |
| Luna | 2,000 | 85.3% | 96.2% | +10.8 pt | 0.1179 |

Paired bootstrap change in Brier versus unpadded:

- Nano +500 words: **+0.0221**, 95% CI about **+0.0037 to +0.0402**.
- Nano +2,000 words: **+0.0381**, 95% CI about **+0.0177 to +0.0584**.
- Luna +500 words: +0.0037, CI crosses zero.
- Luna +2,000 words: +0.0058, CI crosses zero.

Therefore the clean claim is: **irrelevant context makes Nano more overconfident in this task; the same effect is not established for Luna.** Do not generalize this to information-rich long documents.

## Operational use

For a production project with historical review outcomes:

1. replay gold cases through the production prompt/model;
2. experiment with confidence elicitation or richer risk signals;
3. stress-test the score against nuisance factors such as input length;
4. plot risk versus auto-pass coverage;
5. choose the threshold that meets the error SLA;
6. confirm it on a separate holdout before removing review.

See `README.md` for exact files, rebuild commands, and validity notes. `just build` is fully resumable and reconstructs the GitHub Pages assets directly in this directory.
