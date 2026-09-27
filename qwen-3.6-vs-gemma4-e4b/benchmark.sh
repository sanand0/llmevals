#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMEVALS="$(git -C "$ROOT" rev-parse --show-toplevel)"
SCRIPTS="${HOME}/code/scripts"
RUNS="$ROOT/runs"
MODE="${1:-all}"
TIMEOUT="${BENCH_TIMEOUT:-15m}"

QWEN_MODEL='ggml-org/Qwen3.6-35B-A3B-GGUF:Q4_K_M'
GEMMA_MODEL='gemma4:e4b-it-qat'
QWEN_URL='http://127.0.0.1:8080'
OLLAMA_URL='http://127.0.0.1:11434'

# id|source repo|baseline commit|known-good commit|archive path (or .)|verification command
TASKS=(
  'flare-loading|LLMEVALS|c0b4e034c8ff9c76670fd28123ea9dbd4bedc314|931eb2810d659bced50790c5e2a9150a1500dcaf|gpt-image-flare-quality|git diff --check'
  'whatsapp-integrity|SCRIPTS|31043dbe87587dcdf2034a1945b2ff91b525ef90|96c6d3ec1332069f241e94432005681db54961ca|.|just test-backup-whatsapp && git diff --check'
  'mcpserver-console|SCRIPTS|8302d6266b295887e295d58cb6dd87a70c4828f7|31043dbe87587dcdf2034a1945b2ff91b525ef90|.|just test-mcpserver && git diff --check'
)

case "$MODE" in
  all|prepare|gemma|qwen) ;;
  *) echo "Usage: $0 [all|prepare|gemma|qwen]" >&2; exit 2 ;;
esac

for command in git pi curl timeout tar just; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 2; }
done
[[ -d "$SCRIPTS/.git" ]] || { echo "Missing source repo: $SCRIPTS" >&2; exit 2; }

repo_for() {
  case "$1" in
    LLMEVALS) printf '%s\n' "$LLMEVALS" ;;
    SCRIPTS) printf '%s\n' "$SCRIPTS" ;;
  esac
}

prepare_workspace() {
  local model="$1" task="$2" repo="$3" base="$4" archive_path="$5"
  local out="$RUNS/$model/$task"
  local workspace="$out/workspace"
  rm -rf "$out"
  mkdir -p "$workspace"

  if [[ "$archive_path" == "." ]]; then
    git -C "$repo" archive "$base" | tar -x -C "$workspace"
  else
    git -C "$repo" archive "$base" "$archive_path" | tar -x -C "$workspace"
  fi

  git -C "$workspace" init -q
  git -C "$workspace" add -A
  git -C "$workspace" -c user.name=benchmark -c user.email=benchmark@localhost commit -qm baseline
}

prepare_all() {
  rm -rf "$RUNS"
  mkdir -p "$RUNS"
  for row in "${TASKS[@]}"; do
    IFS='|' read -r task repo_name base reference archive_path verify <<<"$row"
    repo="$(repo_for "$repo_name")"
    git -C "$repo" cat-file -e "$base^{commit}"
    git -C "$repo" cat-file -e "$reference^{commit}"
    prepare_workspace gemma "$task" "$repo" "$base" "$archive_path"
    prepare_workspace qwen "$task" "$repo" "$base" "$archive_path"
  done
}

qwen_is_ready() {
  curl -fsS "$QWEN_URL/v1/models" 2>/dev/null | grep -Fq "$QWEN_MODEL"
}

port_8080_open() {
  (echo >/dev/tcp/127.0.0.1/8080) >/dev/null 2>&1
}

qwen_pids() {
  pgrep -u "$UID" -f 'llama.*Qwen3[.]6-35B-A3B-GGUF' 2>/dev/null || true
}

stop_qwen() {
  if ! port_8080_open; then
    return
  fi
  qwen_is_ready || {
    echo "Port 8080 is occupied by something other than the expected Qwen server." >&2
    exit 2
  }

  mapfile -t pids < <(qwen_pids)
  if ((${#pids[@]} == 0)); then
    echo "Qwen is reachable on host port 8080 but its process is outside this PID namespace." >&2
    echo "Run benchmark.sh on the Ubuntu host, not inside dev.sh." >&2
    exit 2
  fi

  echo "Stopping Qwen llama.cpp server for Gemma benchmark..."
  kill "${pids[@]}"
  for _ in {1..60}; do
    port_8080_open || return
    sleep 0.5
  done
  echo "Qwen server did not stop." >&2
  exit 2
}

QWEN_PID=''
start_qwen() {
  qwen_is_ready && return
  port_8080_open && {
    echo "Port 8080 is already occupied." >&2
    exit 2
  }
  command -v llama >/dev/null || { echo "Missing llama executable." >&2; exit 2; }

  echo "Starting Qwen llama.cpp server..."
  llama serve \
    -hf "$QWEN_MODEL" \
    --ctx-size 65536 \
    --n-gpu-layers all \
    --n-cpu-moe 35 \
    --flash-attn on \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
    --parallel 1 \
    --host 127.0.0.1 \
    --port 8080 \
    >"$RUNS/qwen-server.log" 2>&1 &
  QWEN_PID=$!

  for _ in {1..240}; do
    qwen_is_ready && return
    kill -0 "$QWEN_PID" 2>/dev/null || {
      echo "Qwen server exited during startup. See $RUNS/qwen-server.log" >&2
      exit 2
    }
    sleep 0.5
  done
  echo "Timed out waiting for Qwen server. See $RUNS/qwen-server.log" >&2
  exit 2
}

run_task() {
  local model="$1" task="$2" verify="$3"
  local out="$RUNS/$model/$task"
  local workspace="$out/workspace"
  local prompt="$ROOT/tasks/$task/prompt.md"
  local start end pi_exit verify_exit

  echo
  echo "=== $model / $task ==="
  start="$(date +%s)"

  set +e
  if [[ "$model" == gemma ]]; then
    (
      cd "$workspace"
      timeout --signal=INT --kill-after=30s "$TIMEOUT" \
        pi --provider ollama --model "$GEMMA_MODEL" --thinking medium \
        --approve --exclude-tools ask_question --session-dir "$out/session" -p "$(cat "$prompt")"
    ) >"$out/agent.txt" 2>"$out/stderr.txt"
  else
    (
      cd "$workspace"
      timeout --signal=INT --kill-after=30s "$TIMEOUT" \
        pi --provider "llama-server=$QWEN_URL" --model "$QWEN_MODEL" --thinking medium \
        --approve --exclude-tools ask_question --session-dir "$out/session" -p "$(cat "$prompt")"
    ) >"$out/agent.txt" 2>"$out/stderr.txt"
  fi
  pi_exit=$?
  set -e

  end="$(date +%s)"
  git -C "$workspace" status --short >"$out/status.txt"
  git -C "$workspace" diff --binary >"$out/diff.patch"
  git -C "$workspace" diff --stat >"$out/diffstat.txt"

  set +e
  (cd "$workspace" && bash -lc "$verify") >"$out/verify.txt" 2>&1
  verify_exit=$?
  set -e

  cat >"$out/meta.tsv" <<META
model	task	elapsed_seconds	pi_exit	verify_exit
$model	$task	$((end - start))	$pi_exit	$verify_exit
META

  printf 'Pi exit: %s; verifier: %s; elapsed: %ss; changed: ' "$pi_exit" "$verify_exit" "$((end - start))"
  if [[ -s "$out/status.txt" ]]; then
    tr '\n' ' ' <"$out/status.txt"
    echo
  else
    echo 'none'
  fi
}

write_references() {
  mkdir -p "$RUNS/reference"
  for row in "${TASKS[@]}"; do
    IFS='|' read -r task repo_name base reference archive_path verify <<<"$row"
    repo="$(repo_for "$repo_name")"
    if [[ "$archive_path" == "." ]]; then
      git -C "$repo" diff --binary "$base" "$reference" >"$RUNS/reference/$task.patch"
    else
      git -C "$repo" diff --binary "$base" "$reference" -- "$archive_path" >"$RUNS/reference/$task.patch"
    fi
  done
}

write_summary() {
  {
    echo -e 'model\ttask\telapsed_seconds\tpi_exit\tverify_exit\tchanged_files\tinsertions\tdeletions'
    for model in gemma qwen; do
      for row in "${TASKS[@]}"; do
        IFS='|' read -r task _ <<<"$row"
        out="$RUNS/$model/$task"
        [[ -f "$out/meta.tsv" ]] || continue
        IFS=$'\t' read -r _ _ elapsed pi_exit verify_exit < <(tail -1 "$out/meta.tsv")
        stat="$(git -C "$out/workspace" diff --numstat | awk '{files++; add+=$1; del+=$2} END {printf "%d\t%d\t%d", files+0, add+0, del+0}')"
        printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$model" "$task" "$elapsed" "$pi_exit" "$verify_exit" "$stat"
      done
    done
  } >"$RUNS/summary.tsv"
}

prepare_all
if [[ "$MODE" == prepare ]]; then
  echo "Prepared clean workspaces under $RUNS"
  exit
fi

if [[ "$MODE" == all || "$MODE" == gemma ]]; then
  command -v ollama >/dev/null || { echo "Missing ollama executable." >&2; exit 2; }
  curl -fsS "$OLLAMA_URL/api/tags" >/dev/null || { echo "Ollama is not reachable at $OLLAMA_URL." >&2; exit 2; }
  stop_qwen
  echo "Warming Gemma..."
  curl -fsS "$OLLAMA_URL/api/generate" \
    -H 'Content-Type: application/json' \
    -d '{"model":"gemma4:e4b-it-qat","prompt":"","stream":false,"keep_alive":"30m"}' \
    >/dev/null
  for row in "${TASKS[@]}"; do
    IFS='|' read -r task repo_name base reference archive_path verify <<<"$row"
    run_task gemma "$task" "$verify"
  done
  ollama stop "$GEMMA_MODEL" >/dev/null 2>&1 || true
fi

if [[ "$MODE" == all || "$MODE" == qwen ]]; then
  command -v ollama >/dev/null || { echo "Missing ollama executable." >&2; exit 2; }
  ollama stop "$GEMMA_MODEL" >/dev/null 2>&1 || true
  start_qwen
  for row in "${TASKS[@]}"; do
    IFS='|' read -r task repo_name base reference archive_path verify <<<"$row"
    run_task qwen "$task" "$verify"
  done
fi

write_references
write_summary

echo
column -t -s $'\t' "$RUNS/summary.tsv" 2>/dev/null || cat "$RUNS/summary.tsv"
echo
echo "Results: $RUNS"
if [[ "$MODE" == all || "$MODE" == qwen ]]; then
  echo "Qwen server is left running on $QWEN_URL."
else
  echo "Qwen server is stopped."
fi
