# Dealing with Hallucinations

_How can we rely on unreliable LLMs?_

Large language models can feel magical—until they start confidently making things up. In a recent evaluation of 11 state-of-the-art LLMs on a real-world customer-support intent task, we discovered a simple way to tame those “hallucinations” with only a modest hit to automation.

## When one model isn’t enough

We tested 11 LLMs on Kaggle’s [Customer Support Intent Dataset](https://www.kaggle.com/datasets/scodepy/customer-support-intent-dataset), asking them to classify thousands of user messages (billing, refunds, order changes, etc.). The headline findings:

- **Median accuracy \~90%.** Over half the models got at least 90% of the examples right—so even a random pick would nail most queries.
- **Error rate \~10–15%.** But in scale-sensitive settings (customer support, compliance, etc.) a 1 in 10 mistake rate can be disastrous.

![Graph of classification accuracy. Only 20% of the customer intents are classified with under 80% accuracy](model-accuracy.webp)

Different LLMs tend to trip over different edge cases. One might misinterpret “cancel my order”; another might choke on a subtle refund clause. That diversity of mistakes is actually our superpower.

## Cross‐checking with two models

Imagine running each query through two independent LLMs and flagging any time they disagree. The correlation between LLM models is fairly low, as shown below:

![Correlation between LLMs. Numbers are typically between 10-30%](correlation.webp)

- **Disagreement ≈ 20%.** In our experiments, two-model ensembles disagreed on about one-fifth of the inputs, so you’d still automate **80%** end-to-end.
- **Error rate ↓ from \~15% to \~0.25%.** If both models agree, they’re almost always right: accuracy jumps to \~99.75%.

| Metric         | Single Model | 2-Model Majority |
| -------------- | -----------: | ---------------: |
| Automation (%) |         100% |              80% |
| Error Rate (%) |        \~15% |          \~0.25% |

You pay a **20% review load** for a **60× reduction** in mistakes.

## Three-way majority: quality over quantity

Take it further with **three** LLMs and use majority voting:

- **Disagreement ≈ 24%**, so about **76%** fully automated.
- **Error rate \~0.005%**, i.e. **99.995%** accuracy on agreed-upon items.

| Metric         | Single Model | 3-Model Majority |
| -------------- | -----------: | ---------------: |
| Automation (%) |         100% |              76% |
| Error Rate (%) |        \~15% |         \~0.005% |

A **25% hit** to throughput nets you **99.99% precision**—dramatic improvements with minimal extra cost.

## Why this works

1. **Independent mistakes.** LLMs trained on different data and architectures tend to err in uncorrelated ways.
2. **Majority voting.** If two out of three models agree, the odds are overwhelmingly in your favor that they’re right.
3. **Human-in-the-loop only when needed.** Reviewers only see the \~20–25% cases where models disagree, saving time and catching nearly every error.

## Takeaway

If you’re battling hallucinations in your LLM pipeline, you don’t need a perfect single model—just **double-check**:

> **For a 20-25% review load, you can boost accuracy from \~85% to \~99.99%.**

In short, **rely on multiple unreliable LLMs** rather than a single imperfect one. By turning your model fleet into a built-in safety net, you can automate at speed **and** quality—finally making hallucination a thing of the past.

## Setup

Run this code to execute and serve the results:

```bash
git clone git@github.com:sanand0/llmevals.git
cd llmevals/double-checking/
export OPENROUTER_API_KEY=...
export OPENAI_API_KEY=...
npx promptfoo eval
npx promptfoo export latest -o evals.json
npx http-server
```

[Analysis and code by ChatGPT](https://chatgpt.com/share/681ca225-d970-800c-9a43-f7f1da1c8cc7)
