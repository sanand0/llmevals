# Confidence calibration experiments — updated 2026-09-16

## Bottom line

Four findings survive the expanded 770-case BANKING77 benchmark:

1. **Raw LLM confidence is materially overconfident.** Nano is 61.0% accurate while averaging 87.1% confidence; Luna is 84.0% accurate while averaging 95.7% confidence.
2. **Prompting can make confidence much more useful without making the classifier materially more accurate.** On Luna, “okay to be uncertain” and “top-two probability” reduce Brier score from 0.1231 to 0.0968; ≥95% error drops from 10.3% to about 4%.
3. **Confidence robustness is model-dependent.** Adding 2,000 words of irrelevant neutral metadata raises Nano confidence by about 6.1 points without improving accuracy and significantly worsens Brier score. Luna is essentially stable under the same manipulation.
4. **Raw logprobs are worse probabilities but useful risk-ranking signals.** On a paired Luna run, first-token logprob has worse raw Brier than Top-two stated confidence (0.148 vs 0.119), but better correctness ranking (AUROC 0.830 vs 0.783). Using only actually deployable score cutoffs and never splitting equal-score ties, the development-set 5% rule covers 65.2% of cases versus 43.1% for stated confidence.
5. **That routing advantage survived a prospective holdout at the 5% target.** A rule frozen on 770 cases auto-passed 65.2% of 2,310 untouched requests at 4.38% observed error, versus 41.2% coverage at 2.63% error for the frozen stated-confidence rule. But the frozen 10% logprob rule missed its target at 12.0%, so risk control must be validated at the actual operating cutoff.

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

## Logprobs vs stated confidence: same Luna call, same 770 cases

The new protocol maps each of the 77 intents to a random one-character code per case. Luna emits the code first, then its Top-two stated confidence. The first-token logprob and stated score therefore describe the same prediction.

| Signal | Raw mean | Raw Brier ↓ | Calibrated Brier ↓ | AUROC correctness ↑ | Coverage at ≤5% error ↑ |
|---|---:|---:|---:|---:|---:|
| First-token logprob | 98.4% | 0.148 | **0.102** | **0.830** | **65.2%** |
| Stated confidence | 88.2% | **0.119** | 0.116 | 0.783 | 43.1% |

Luna is 83.6% accurate in this protocol. Yet 435/770 first-token probabilities are effectively 100%; 18 of those predictions are wrong. Raw token probability is therefore emphatically **not** a trustworthy literal probability.

The useful information is primarily in the ranking, not the literal probability. The development set made calibrated logprob look better on Brier, but the prospective holdout did not confirm a clear calibration advantage. For routing, curves now use only attainable score thresholds and never split equal-score ties; at the 5% development target, logprob covers 65.2% versus 43.1% for stated confidence. Raw-score Spearman correlation is 0.57.

The logprob runner uses Chat Completions because that surface returned token logprobs in direct probes. The earlier benchmark used Responses, so old and new absolute accuracies should not be treated as an endpoint-controlled comparison.

## Prospective logprob holdout: 2,310 untouched requests

The original 770 cases were used to fit one final Platt calibrator per signal and freeze score cutoffs for 2%, 5%, and 10% observed training error. The remaining BANKING77 test cases were then run once without retuning.

| Frozen signal | Holdout coverage at 5% rule | Holdout error | Errors / auto-passed | Calibrated Brier |
|---|---:|---:|---:|---:|
| Token logprob | **65.2%** | 4.38% | 66 / 1,506 | 0.1105 |
| Stated confidence | 41.2% | **2.63%** | 25 / 951 | 0.1130 |

The calibrated-Brier difference is small and its paired 95% bootstrap interval crosses zero, so the holdout does **not** establish that calibrated logprobs are universally better probabilities. It does support the narrower operational result: at the predeclared 5% cutoff, the frozen logprob rule removed substantially more review while remaining inside the observed error budget. The separately frozen 10% logprob rule produced 12.0% error, showing that this result should not be extrapolated across thresholds.

## Operational use

For a production project with historical review outcomes:

1. replay gold cases through the production prompt/model;
2. experiment with confidence elicitation and richer risk signals such as logprobs;
3. stress-test the score against nuisance factors such as input length;
4. plot risk versus auto-pass coverage;
5. choose the threshold that meets the error SLA;
6. confirm it on a separate holdout before removing review.

See `README.md` for exact files, rebuild commands, and validity notes. `just build` is fully resumable and reconstructs the GitHub Pages assets directly in this directory.
