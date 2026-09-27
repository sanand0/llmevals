# Qwen 3.6 vs Gemma 4 E4B vs GPT-6 Luna

<!-- https://chatgpt.com/c/6a802a27-5cf4-83e8-b999-f483c97263db -->

I wanted to know how good local coding models really are for the kind of agentic work I do—not on a benchmark, but on real changes where I can look at the diff and immediately decide whether I would keep it.

I compared:

- **Gemma 4 E4B QAT** via Ollama + Pi.
- **Qwen 3.6 35B-A3B Q4_K_M** via llama.cpp + Pi, with 64K context, Q8 KV cache and MoE experts offloaded to CPU as needed to stay within my 8 GB VRAM budget.
- **GPT-6 Luna** via Codex, at medium reasoning.

This is deliberately an end-to-end agent benchmark, not a pure model-IQ benchmark. Each agent gets its normal tools. In particular, Codex could use its browser tooling on the image-loading task.

## What I found

Luna was clearly better on all three tasks.

| Task | Gemma 4 E4B | Qwen 3.6 | GPT-6 Luna |
| --- | --- | --- | --- |
| **Flare image loading** | Refactored JavaScript without really fixing loading | Elegant two-line preload, but not the optimization I wanted | **Best:** pure HTML `loading="lazy"` + `decoding="async"`; simple and directly useful |
| **WhatsApp integrity** | Did not complete the change | Understood the problem and built a substantial solution, but timed out unfinished | **Best:** small validation-only solution, which is exactly what I wanted |
| **MCP console logs** | Did not complete the change | Improved readability in the right direction, but timed out unfinished | **Best:** achieved roughly the same goal much more concisely by reusing `truncate_middle` |

The runtime difference was just as striking:

| Model | Flare | WhatsApp | MCP logs |
| --- | ---: | ---: | ---: |
| Gemma 4 E4B | 174s | 103s, no change | 89s, no change |
| Qwen 3.6 | 231s | **900s timeout** | **900s timeout** |
| GPT-6 Luna | **141s** | **183s** | **117s** |

My main takeaway is: **local models still lag behind even weaker online models for autonomous coding.** Qwen 3.6 was much more agentic than Gemma—it explored, edited, tested and iterated—but it often failed to converge before the 15-minute timeout. Luna consistently got to a small, tested, finished change.

That said, if I had to code locally—for example on a flight—**I would use Qwen 3.6 today**. It works OK, is capable enough to be useful, and this llama.cpp setup stays within my 8 GB GPU-memory budget by keeping most MoE experts in system RAM.

## How I tested

These are three tasks from my recent coding history, replayed from the exact commit immediately before my actual fix:

1. **`flare-loading`** — make a large image-heavy page load better on a poor network without reducing image quality.
2. **`whatsapp-integrity`** — detect corrupt/misattributed backup JSONL safely before touching WhatsApp/CDP.
3. **`mcpserver-console`** — make rapidly scrolling MCP tool logs easier to understand without weakening persistent logs.

`benchmark.sh` creates a clean, history-free Git workspace for every model/task pair, so the agent cannot find the later fix in Git history. Every model gets the same task prompt. Each task has a 15-minute limit and an automated verifier; the historical fix is kept separately for comparison.

The verifier is useful but not the score. For example, Gemma's WhatsApp run passed the old tests despite making no change. The real evaluation is the resulting diff: did it diagnose the right problem, make the smallest robust change, test it, and leave something I would merge?

Token counts are recorded for completeness in [`results/details.tsv`](results/details.tsv), but the clients/providers account for cached and reasoning tokens differently, so I would not compare those numbers directly across models.

## Results and files

The repository keeps the small artifacts worth reviewing:

- [`tasks/`](tasks/) — the exact prompts.
- [`originals/`](originals/) — only the baseline versions of files that at least one model edited.
- [`results/summary.tsv`](results/summary.tsv) — time, exit status and diff size.
- [`results/details.tsv`](results/details.tsv) — model/runtime, token counters, time, verifier status and diff size.
- [`results/environment.tsv`](results/environment.tsv) — GPU and CLI/runtime versions plus the Qwen context/offload settings.
- `results/{gemma,qwen,codex}/{task}/` — `agent.txt`, the unified `diff.patch`, verifier output, and non-empty stderr where relevant.
- [`results/reference/`](results/reference/) — the historical patches I actually made after the same baseline.

The bulky generated workspaces and raw session event streams live under `runs/` and are ignored by Git.

## Reproduce

Run this on the Ubuntu host, not inside `dev.sh`, because the benchmark stops/starts the host llama.cpp server so only one local model owns the GPU at a time.

```bash
./benchmark.sh
```

It is resumable: completed model/task pairs are skipped. To force a completely fresh run:

```bash
rm -rf runs
./benchmark.sh
```

To regenerate only the commit-friendly artifacts from an existing run:

```bash
./benchmark.sh export
```

The script pins the baseline/reference commits and checks that they exist. It expects this `llmevals` repo plus `~/code/scripts`, Pi/Ollama with Gemma, llama.cpp for Qwen, and an authenticated Codex CLI. You can also run one model at a time with `./benchmark.sh gemma`, `./benchmark.sh qwen`, or `./benchmark.sh codex`. Use `BENCH_TIMEOUT=30m` to change the per-task timeout.
