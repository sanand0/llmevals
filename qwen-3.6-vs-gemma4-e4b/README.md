# Qwen 3.6 vs Gemma 4 E4B vs Codex

Compare coding-agent quality on three real tasks from recent work.

Run on the Ubuntu host, not inside `dev.sh`, because the benchmark temporarily stops/restarts the host llama.cpp server so only one model owns the 8 GB GPU at a time.

```bash
./benchmark.sh
```

It creates clean, history-free workspaces in `runs/`, runs Gemma 4 E4B through Ollama, Qwen 3.6 35B-A3B through llama.cpp, and Codex with `gpt-6-luna` at medium reasoning. A task with `meta.tsv` is already complete and is skipped on later runs; an interrupted task without metadata is reset to its clean baseline and retried.

Each `runs/{gemma,qwen,codex}/{task}/` contains `agent.txt`, `stderr.txt`, `diff.patch`, `status.txt`, `verify.txt`, timing/exit metadata, and the edited `workspace/`. Codex also stores its JSONL event stream as `session.jsonl`. `runs/reference/` contains the known-good historical patches.

Tasks:

- `flare-loading`: diagnose and improve slow image loading without reducing quality.
- `whatsapp-integrity`: make corrupt backup JSONL fail safely and diagnostically.
- `mcpserver-console`: redesign fast-scrolling tool logs for human scanability.

Useful partial runs:

```bash
./benchmark.sh prepare
./benchmark.sh gemma
./benchmark.sh qwen
./benchmark.sh codex
```

A plain `./benchmark.sh` continues only missing model/task runs. Override the Codex model or reasoning level with `CODEX_MODEL=...` or `CODEX_REASONING=...`; override the 15-minute per-task limit with `BENCH_TIMEOUT=30m ./benchmark.sh`.
