# Qwen 3.6 vs Gemma 4 E4B

Compare local coding-agent quality on three real tasks from recent work.

Run on the Ubuntu host, not inside `dev.sh`, because the benchmark temporarily stops/restarts the host llama.cpp server so only one model owns the 8 GB GPU at a time.

```bash
./benchmark.sh
```

It recreates clean, history-free workspaces in `runs/`, runs Gemma 4 E4B through Ollama, unloads it, starts Qwen 3.6 35B-A3B through llama.cpp, and runs the same prompts. Existing Qwen on port 8080 is stopped first; Qwen is left running when the benchmark finishes.

Each `runs/{gemma,qwen}/{task}/` contains `agent.txt`, `stderr.txt`, `diff.patch`, `status.txt`, `verify.txt`, timing/exit metadata, and the edited `workspace/`. `runs/reference/` contains the known-good historical patches, generated only after both models finish so agents cannot inspect them.

Tasks:

- `flare-loading`: diagnose and improve slow image loading without reducing quality.
- `whatsapp-integrity`: make corrupt backup JSONL fail safely and diagnostically.
- `mcpserver-console`: redesign fast-scrolling tool logs for human scanability.

Useful partial runs:

```bash
./benchmark.sh prepare
./benchmark.sh gemma
./benchmark.sh qwen
```

Override the 15-minute per-task limit with `BENCH_TIMEOUT=30m ./benchmark.sh`.
