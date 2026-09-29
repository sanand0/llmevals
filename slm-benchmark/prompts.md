# Prompts

## Refinements, 30 Sep 2026

<!--
cd ~/code/llmevals/slm-benchmark/
dev.sh -- codex --yolo --model gpt-6-luna --config model_reasoning_effort=high
-->

A few changes:

- In the scatter-splot, change the color coding based on (estimated) number of model parameters: Large, Medium, Small.
- In the "Exact benchmark results" table,
  - Add a column for "Parameters" and use values like 8.3B, etc.
  - Allow sorting by any column.
- Convert costs to cents everywhere, making it easier to read.
- Change the title to "SLM vs Fronter Models"

---

When sorting, treat "Undisclosed" as the largest value in parameters.
Clicking on the legend "Large", "Medium", etc. should highlight only the corresponding points in the scatter plot (as well as mark itself active on the legend, visibly), and dim the others. Clicking again should restore the original view.
Drop GLM 5.3 Flash from the scatterplot and table since it requires reasoning. Let it be in the data. Update the frontier line and axes scales accordingly.

---

Vertically align the "Frontier" legend with the rest of the legends.
Make all tables sortable by columns.
In the "Where models differ" table, swap rows and columns. Columns can just be add, subtract, multiple, divide. Color code the table on a RdYlGn scale ensuring text/background color contrast in light AND dark modes.
Replace "Gold: ..." with "Actual: ...".

--- <!-- steering -->

Change the title to "SLM vs LLM on FinQA".

---

Drop the ECE column

<!-- codex resume 01a0ef21-20e1-7663-817e-b594e7db8b04 --yolo -->

## Initial draft, 29 Sep 2026

<!-- SLM FinQA Benchmark for PGIM: https://chatgpt.com/c/6abb69ef-08e8-83ec-a0c4-80438d2d2239 (2026-09-30T05:36:43+08:00) -->

On [LocalMCP2](/plugins/plugin_asdk_app_6ab0b6c561508191882e58b23665db3e) take a look at ~/Dropbox/notes/transcripts/2026-09-28 Manish Abhishek PGIM demo for Ankor Prep.md

In this, I propose a set of demos for Ankor to show PGIM.

One workflow is where we take a business workflow relevant to PGIM and benchmark it against multiple models - small local models as well as small frontier models. I want to do this similar to the BANKING77 benchmark at ~/code/llmevals/jev/ (and you should check the past conversation we had about it.)

What would be good datasets - with about 100 data points - that we should benchmark? In the light of the conversation, what models should we pick assuming we want to pick from OpenRouter and want the latest models? I'm thinking we should have 2 of the best latest models that'll fit under 8GB GPU RAM, 2 of the best latest models that'll fit in a MacBook Pro, and GPT 6 Luna for comparison. Research and suggest which models to pick (you may suggest more than this number - just prioritize, so I can pick) for these. Estimate the cost of running for each model for ~100 data points for each of the datasets you suggest. I'm looking for a rough number, not a perfect calculation.

(Afterwards, I might do a prompt optimization exercise and a confidence calibration exercise - sort of like ~/code/llmevals/confidence-calibration/ - just FYI)

Use ~/code/llmevals/slm-benchmark/ as your root directory.

Use relevant skills, including reframe-question.

---

Let's go with 100 questions from FinQA. For the 8GB, I prefer Gemma 4 E4B instead of Granite - if we can run this on OpenRouter? The rest of your model choices are fine.

Agreed with {answer,confidence} and your other choices. Update README.md.

Copy the OPENROUTER_API_KEY from confidence-calibration/.env into slm-benchmark/.env and .gitignore it.

Plan how best to do this. Break it into steps. I will say "Continue" and you can proceed to execute the next step. Keep committing on a separate branch as you progress. If you need to change plans midway based on what you find, you're welcome to do so.

---

Continue

---

Continue

---

Continue

---

Continue

---

Continue. Also, tell me, if you had to extend the benchmark to 5 more models of similar types at similar costs and available on OpenRouter, what would they be?

---

I'd prefer a bit more diversity in models. GLM 5.3 Flash, Ministral 3 8B are fine, but let's not add another Qwen or Gemma model. Suggest 5 more (preferably popular modern inexpensive open) models on OpenRouter.

---

Benchmark the 5 you suggested plus Ling 3.0 Flash Fin in addition to the existing. Remove the last table from index.html that suggests these new models. Begin with a cost (log scale?) vs quality benchmark using popups to show details. Use relevant skills from ~/code/skills/agents/ to craft good data visualizations.

---

* [Remote Desktop Commander](/plugins/plugin_asdk_app_6a057d268ebc81919918d37eec718425)
 can access graphene, which is the same machine and has the same files as* [LocalMCP2](/plugins/plugin_asdk_app_6ab0b6c561508191882e58b23665db3e)
 - so you can use Remote Desktop Commander instead and implement this change.

---

Is this done? If not, complete it.
