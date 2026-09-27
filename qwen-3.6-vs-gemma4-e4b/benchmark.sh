#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMEVALS="$(git -C "$ROOT" rev-parse --show-toplevel)"
SCRIPTS="${HOME}/code/scripts"
RUNS="$ROOT/runs"
RESULTS="$ROOT/results"
ORIGINALS="$ROOT/originals"
MODE="${1:-all}"
TIMEOUT="${BENCH_TIMEOUT:-15m}"

QWEN_MODEL='ggml-org/Qwen3.6-35B-A3B-GGUF:Q4_K_M'
GEMMA_MODEL='gemma4:e4b-it-qat'
CODEX_MODEL="${CODEX_MODEL:-gpt-6-luna}"
CODEX_REASONING="${CODEX_REASONING:-medium}"
QWEN_URL='http://127.0.0.1:8080'
OLLAMA_URL='http://127.0.0.1:11434'

# id|source repo|baseline commit|known-good commit|archive path (or .)|verification command
TASKS=(
  'flare-loading|LLMEVALS|c0b4e034c8ff9c76670fd28123ea9dbd4bedc314|931eb2810d659bced50790c5e2a9150a1500dcaf|gpt-image-flare-quality|git diff --check'
  'whatsapp-integrity|SCRIPTS|31043dbe87587dcdf2034a1945b2ff91b525ef90|96c6d3ec1332069f241e94432005681db54961ca|.|just test-backup-whatsapp && git diff --check'
  'mcpserver-console|SCRIPTS|8302d6266b295887e295d58cb6dd87a70c4828f7|31043dbe87587dcdf2034a1945b2ff91b525ef90|.|just test-mcpserver && git diff --check'
)

case "$MODE" in
  all|prepare|gemma|qwen|codex|export) ;;
  *) echo "Usage: $0 [all|prepare|gemma|qwen|codex|export]" >&2; exit 2 ;;
esac

for command in git curl timeout tar just flock jaq; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 2; }
done
if [[ "$MODE" == all || "$MODE" == gemma || "$MODE" == qwen ]]; then
  command -v pi >/dev/null || { echo "Missing required command: pi" >&2; exit 2; }
fi
if [[ "$MODE" == all || "$MODE" == codex ]]; then
  command -v codex >/dev/null || { echo "Missing required command: codex" >&2; exit 2; }
fi
[[ -d "$SCRIPTS/.git" ]] || { echo "Missing source repo: $SCRIPTS" >&2; exit 2; }

mkdir -p "$RUNS"
exec 9>"$RUNS/.benchmark.lock"
flock -n 9 || { echo "Another benchmark.sh run is already active." >&2; exit 2; }

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

run_done() {
  local model="$1" task="$2" out="$RUNS/$1/$2"
  [[ -f "$out/meta.tsv" ]] || return 1
  if [[ "$model" == codex ]]; then
    [[ -s "$out/session.jsonl" ]] && grep -q '"type":"thread.started"' "$out/session.jsonl"
  else
    find "$out/session" -maxdepth 1 -type f -name '*.jsonl' -print -quit 2>/dev/null | grep -q .
  fi
}

has_pending() {
  local model="$1" row task
  for row in "${TASKS[@]}"; do
    IFS='|' read -r task _ <<<"$row"
    run_done "$model" "$task" || return 0
  done
  return 1
}

prepare_all() {
  mkdir -p "$RUNS"
  for row in "${TASKS[@]}"; do
    IFS='|' read -r task repo_name base reference archive_path verify <<<"$row"
    repo="$(repo_for "$repo_name")"
    git -C "$repo" cat-file -e "$base^{commit}"
    git -C "$repo" cat-file -e "$reference^{commit}"
    for model in gemma qwen codex; do
      run_done "$model" "$task" || prepare_workspace "$model" "$task" "$repo" "$base" "$archive_path"
    done
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
  local start end agent_exit verify_exit

  if run_done "$model" "$task"; then
    echo "=== $model / $task: already completed; skipping ==="
    return
  fi

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
  elif [[ "$model" == qwen ]]; then
    (
      cd "$workspace"
      timeout --signal=INT --kill-after=30s "$TIMEOUT" \
        pi --provider "llama-server=$QWEN_URL" --model "$QWEN_MODEL" --thinking medium \
        --approve --exclude-tools ask_question --session-dir "$out/session" -p "$(cat "$prompt")"
    ) >"$out/agent.txt" 2>"$out/stderr.txt"
  else
    timeout --signal=INT --kill-after=30s "$TIMEOUT" \
      codex exec \
        --model "$CODEX_MODEL" \
        -c "model_reasoning_effort=\"$CODEX_REASONING\"" \
        --sandbox workspace-write \
        --cd "$workspace" \
        --ephemeral \
        --json \
        --color never \
        --output-last-message "$out/agent.txt" \
        - <"$prompt" >"$out/session.jsonl" 2>"$out/stderr.txt"
  fi
  agent_exit=$?
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
model	task	elapsed_seconds	agent_exit	verify_exit
$model	$task	$((end - start))	$agent_exit	$verify_exit
META

  printf 'Agent exit: %s; verifier: %s; elapsed: %ss; changed: ' "$agent_exit" "$verify_exit" "$((end - start))"
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
    echo -e 'model\ttask\telapsed_seconds\tagent_exit\tverify_exit\tchanged_files\tinsertions\tdeletions'
    for model in gemma qwen codex; do
      for row in "${TASKS[@]}"; do
        IFS='|' read -r task _ <<<"$row"
        out="$RUNS/$model/$task"
        [[ -f "$out/meta.tsv" ]] || continue
        IFS=$'\t' read -r _ _ elapsed agent_exit verify_exit < <(tail -1 "$out/meta.tsv")
        stat="$(git -C "$out/workspace" diff --numstat | awk '{files++; add+=$1; del+=$2} END {printf "%d\t%d\t%d", files+0, add+0, del+0}')"
        printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$model" "$task" "$elapsed" "$agent_exit" "$verify_exit" "$stat"
      done
    done
  } >"$RUNS/summary.tsv"
}

model_id_for() {
  case "$1" in
    gemma) printf '%s\n' "$GEMMA_MODEL" ;;
    qwen) printf '%s\n' "$QWEN_MODEL" ;;
    codex) printf '%s\n' "$CODEX_MODEL" ;;
  esac
}

runner_for() {
  case "$1" in
    gemma) printf 'pi+ollama\n' ;;
    qwen) printf 'pi+llama.cpp\n' ;;
    codex) printf 'codex\n' ;;
  esac
}

usage_for() {
  local model="$1" task="$2" out="$RUNS/$1/$2" session
  if [[ "$model" == codex ]]; then
    jaq -s -r '
      [.[] | select(.type=="turn.completed") | .usage] | last as $u
      | [($u.input_tokens // 0), ($u.cached_input_tokens // 0), ($u.output_tokens // 0),
         ($u.reasoning_output_tokens // 0), ""] | @tsv
    ' "$out/session.jsonl"
  else
    session="$(find "$out/session" -maxdepth 1 -type f -name '*.jsonl' -print -quit)"
    jaq -s -r '
      [.[] | select(.type=="message" and .message.role=="assistant" and .message.usage) | .message.usage] as $u
      | [($u | map(.input // 0) | add // 0),
         ($u | map(.cacheRead // 0) | add // 0),
         ($u | map(.output // 0) | add // 0),
         ($u | map(.reasoning // 0) | add // 0),
         ($u | last | .totalTokens // 0)] | @tsv
    ' "$session"
  fi
}

export_originals() {
  rm -rf "$ORIGINALS"
  mkdir -p "$ORIGINALS"
  local row task model workspace file destination
  for row in "${TASKS[@]}"; do
    IFS='|' read -r task _ <<<"$row"
    declare -A changed=()
    workspace=''
    for model in gemma qwen codex; do
      run_done "$model" "$task" || continue
      workspace="$RUNS/$model/$task/workspace"
      while IFS= read -r file; do
        [[ -n "$file" ]] && changed["$file"]=1
      done < <(git -C "$workspace" diff --name-only HEAD)
    done
    [[ -n "$workspace" ]] || continue
    for file in "${!changed[@]}"; do
      git -C "$workspace" cat-file -e "HEAD:$file" 2>/dev/null || continue
      destination="$ORIGINALS/$task/$file"
      mkdir -p "$(dirname "$destination")"
      git -C "$workspace" show "HEAD:$file" >"$destination"
    done
  done
}

export_results() {
  rm -rf "$RESULTS"
  mkdir -p "$RESULTS/reference"
  cp "$RUNS/summary.tsv" "$RESULTS/summary.tsv"
  cp "$RUNS/reference/"*.patch "$RESULTS/reference/"

  {
    echo -e 'model\tmodel_id\trunner\ttask\telapsed_seconds\tagent_exit\tverify_exit\tchanged_files\tinsertions\tdeletions\tinput_tokens\tcached_input_tokens\toutput_tokens\treasoning_output_tokens\tfinal_context_tokens'
    local model row task out elapsed agent_exit verify_exit stat usage model_id runner
    for model in gemma qwen codex; do
      model_id="$(model_id_for "$model")"
      runner="$(runner_for "$model")"
      for row in "${TASKS[@]}"; do
        IFS='|' read -r task _ <<<"$row"
        run_done "$model" "$task" || continue
        out="$RUNS/$model/$task"
        mkdir -p "$RESULTS/$model/$task"
        cp "$out/agent.txt" "$out/diff.patch" "$out/verify.txt" "$RESULTS/$model/$task/"
        [[ ! -s "$out/stderr.txt" ]] || cp "$out/stderr.txt" "$RESULTS/$model/$task/"

        IFS=$'\t' read -r _ _ elapsed agent_exit verify_exit < <(tail -1 "$out/meta.tsv")
        stat="$(git -C "$out/workspace" diff --numstat | awk '{files++; add+=$1; del+=$2} END {printf "%d\t%d\t%d", files+0, add+0, del+0}')"
        usage="$(usage_for "$model" "$task")"
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
          "$model" "$model_id" "$runner" "$task" "$elapsed" "$agent_exit" "$verify_exit" "$stat" "$usage"
      done
    done
  } >"$RESULTS/details.tsv"

  {
    printf 'kernel\t%s\n' "$(uname -srmo)"
    if command -v nvidia-smi >/dev/null; then
      nvidia-smi --query-gpu=name,memory.total,driver_version,power.limit --format=csv,noheader |
        sed 's/^/gpu\t/'
    fi
    command -v ollama >/dev/null && printf 'ollama\t%s\n' "$(ollama --version 2>&1 | head -1)"
    command -v llama >/dev/null && printf 'llama\t%s\n' "$(llama --version 2>&1 | head -1)"
    command -v pi >/dev/null && printf 'pi\t%s\n' "$(pi --version 2>&1 | head -1)"
    command -v codex >/dev/null && printf 'codex\t%s\n' "$(codex --version 2>&1 | head -1)"
    printf 'qwen_context\t65536\n'
    printf 'qwen_cpu_moe\t35\n'
    printf 'qwen_kv_cache\tq8_0\n'
  } >"$RESULTS/environment.tsv"

  export_originals
}

prepare_all
if [[ "$MODE" == prepare ]]; then
  echo "Prepared missing workspaces under $RUNS; completed runs were preserved."
  exit
fi
if [[ "$MODE" == export ]]; then
  write_references
  write_summary
  export_results
  echo "Exported review artifacts to $RESULTS and $ORIGINALS."
  exit
fi

if [[ "$MODE" == all || "$MODE" == gemma ]] && has_pending gemma; then
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

if [[ "$MODE" == all || "$MODE" == qwen ]] && has_pending qwen; then
  command -v ollama >/dev/null || { echo "Missing ollama executable." >&2; exit 2; }
  ollama stop "$GEMMA_MODEL" >/dev/null 2>&1 || true
  start_qwen
  for row in "${TASKS[@]}"; do
    IFS='|' read -r task repo_name base reference archive_path verify <<<"$row"
    run_task qwen "$task" "$verify"
  done
fi

if [[ "$MODE" == all || "$MODE" == codex ]] && has_pending codex; then
  for row in "${TASKS[@]}"; do
    IFS='|' read -r task repo_name base reference archive_path verify <<<"$row"
    run_task codex "$task" "$verify"
  done
fi

write_references
write_summary
export_results

echo
column -t -s $'\t' "$RUNS/summary.tsv" 2>/dev/null || cat "$RUNS/summary.tsv"
echo
echo "Results: $RUNS"
qwen_is_ready && echo "Qwen server is running on $QWEN_URL." || true
