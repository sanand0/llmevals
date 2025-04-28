# LLM evals

A work-in-progress evaluation of multiple LLMs.

For now, it just checks if LLMs can respond to `Gr brx vshdn Fdhvdu flskhu?` ("Do you speak Caesar cipher?") and a few tests from [Nick Carlini](https://github.com/carlini/yet-another-applied-llm-benchmark).

## Setup

```bash
git clone git@github.com:sanand0/llmevals.git
cd llmevals
export OPENROUTER_API_KEY=...
export OPENAI_API_KEY=...
npx promptfoo eval
npx promptfoo export latest -o evals.json
```
