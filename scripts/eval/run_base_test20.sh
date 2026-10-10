#!/usr/bin/env bash
# Run the frozen base Qwen3-4B baseline on the official airline Test20 split.
#
# This is a held-out evaluation: it spends user-simulator API calls and produces
# the number every later phase is compared against. It therefore refuses to run
# without an explicit authorization flag, and it never silently resumes an
# existing run.
#
#   AIRLINE_RL_ALLOW_TEST20_EVAL=1 scripts/eval/run_base_test20.sh
#   scripts/eval/run_base_test20.sh --dry-run       # print the command, call nothing
#
# Requires a local vLLM endpoint serving the agent (see serve_qwen3_4b.sh) and
# OPENAI_API_KEY for the user simulator. Supplying the tau2 .env file is easiest:
#
#   AIRLINE_RL_ENV_FILE=/path/to/tau2-bench/.env AIRLINE_RL_ALLOW_TEST20_EVAL=1 \
#     scripts/eval/run_base_test20.sh
#
# Overridable: TAU2_DIR TAU2_PYTHON RUN_NAME GPU-less protocol vars in the block below.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TAU2_DIR="${TAU2_DIR:-$(dirname "$REPO")/tau2-bench}"
TAU2_PYTHON="${TAU2_PYTHON:-$TAU2_DIR/.venv/bin/python}"
PINNED_COMMIT="5bfa7e37b36656b37dc6d022156be6563c1007f3"

if [[ -x "$REPO/.venv/bin/python" ]]; then
  REPO_PYTHON="$REPO/.venv/bin/python"
else
  REPO_PYTHON="$(command -v python3 || true)"
fi

# --- Frozen evaluation protocol. Changing any of these changes the baseline. ---
TASK_SPLIT="${TASK_SPLIT:-test}"
# 5 trials x 20 tasks = 100 simulations; the reported success rate is
# successes/100, i.e. an estimate of single-run per-task success probability.
NUM_TRIALS="${NUM_TRIALS:-5}"
SEED="${SEED:-300}"
MAX_STEPS="${MAX_STEPS:-200}"
MAX_ERRORS="${MAX_ERRORS:-10}"
TEMPERATURE="${TEMPERATURE:-0.0}"
AGENT_MODEL="${AGENT_MODEL:-openai/qwen3-4b}"
AGENT_BASE_URL="${AGENT_BASE_URL:-http://127.0.0.1:8001/v1}"
USER_MODEL="${USER_MODEL:-openai/gpt-5.6-sol}"
USER_BASE_URL="${USER_BASE_URL:-https://ai.ahzm.top/v1}"
RUN_NAME="${RUN_NAME:-qwen3_4b_airline_base_test20_x5}"

RUN_DIR="$REPO/outputs/runs/$RUN_NAME"
DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

die() { echo "Refusing to run: $*" >&2; exit 1; }

if [[ "$TASK_SPLIT" != "test" && "${AIRLINE_RL_ALLOW_NON_TEST_SPLIT:-}" != "1" ]]; then
  die "TASK_SPLIT=$TASK_SPLIT is not the held-out Test20 split. Set
  AIRLINE_RL_ALLOW_NON_TEST_SPLIT=1 only if you really mean a non-held-out run."
fi

command -v "$TAU2_PYTHON" >/dev/null 2>&1 || [[ -x "$TAU2_PYTHON" ]] \
  || die "tau2 python not found at $TAU2_PYTHON (set TAU2_PYTHON)"

# The pinned code version is part of the result; never run against a moving HEAD.
actual_commit="$(git -C "$TAU2_DIR" rev-parse HEAD 2>/dev/null || true)"
[[ "$actual_commit" == "$PINNED_COMMIT" ]] \
  || die "$TAU2_DIR is at '${actual_commit:-unknown}', expected $PINNED_COMMIT"

# Materialize and hash-check the airline data, and prove the split tau2 will read
# is exactly the official Test20 set.
if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="$REPO/src:$PYTHONPATH"
else
  export PYTHONPATH="$REPO/src"
fi
prepare_args=(--root "$REPO")
if [[ -n "${TAU2_SOURCE:-}" ]]; then
  prepare_args+=(--source "$TAU2_SOURCE")
fi
"$REPO_PYTHON" "$REPO/scripts/eval/prepare_data.py" "${prepare_args[@]}"
"$REPO_PYTHON" "$REPO/scripts/eval/preflight.py" --root "$REPO"

[[ -e "$RUN_DIR/results.json" ]] \
  && die "$RUN_DIR/results.json already exists. Pick another RUN_NAME or move it
  aside; this script never resumes or overwrites a recorded run."

if [[ "$DRY_RUN" == "1" ]]; then
  echo "# dry run: nothing was called. Resolved configuration:"
  echo "TAU2_DIR=$TAU2_DIR"
  echo "TAU2_DATA_DIR=$REPO/data"
  echo "SAVE_TO=$RUN_DIR"
  exit 0
fi

# --- Authorization gate. Everything above is read-only; everything below spends. ---
[[ "${AIRLINE_RL_ALLOW_TEST20_EVAL:-}" == "1" ]] || die "held-out Test20 evaluation is not
  authorized in this session. Phase 0/1 authorization excludes it. Re-run with
  AIRLINE_RL_ALLOW_TEST20_EVAL=1 only after the user approves the run and budget."

if [[ -n "${AIRLINE_RL_ENV_FILE:-}" ]]; then
  [[ -f "$AIRLINE_RL_ENV_FILE" ]] || die "AIRLINE_RL_ENV_FILE not found: $AIRLINE_RL_ENV_FILE"
  # Parse KEY=VALUE lines rather than `source`-ing the file. tau2's .env is
  # dotenv data whose values bash cannot always parse, and executing a data file
  # as shell is unsafe regardless. Variables already set win over the file.
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line#export }"
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ "$value" == \"*\" || "$value" == \'*\' ]]; then
      value="${value:1:${#value}-2}"
    fi
    [[ -n "${!key:-}" ]] && continue
    export "$key=$value"
  done < "$AIRLINE_RL_ENV_FILE"
fi

[[ -n "${OPENAI_API_KEY:-}" ]] || die "OPENAI_API_KEY is required for the user simulator.
  Export it, or point AIRLINE_RL_ENV_FILE at the tau2 .env file."

curl -fsS --max-time 15 "$AGENT_BASE_URL/models" >/dev/null 2>&1 \
  || die "agent endpoint $AGENT_BASE_URL is not reachable. Start it with
  scripts/eval/serve_qwen3_4b.sh (GPU is consumed)."

mkdir -p "$RUN_DIR"
export TAU2_DATA_DIR="$REPO/data"
# Skip litellm's best-effort remote cost-map fetch on an offline server.
export LITELLM_LOCAL_MODEL_COST_MAP="${LITELLM_LOCAL_MODEL_COST_MAP:-True}"

cd "$TAU2_DIR"
"$TAU2_PYTHON" -m tau2.cli run \
  --domain airline \
  --task-split-name "$TASK_SPLIT" \
  --num-trials "$NUM_TRIALS" \
  --seed "$SEED" \
  --max-steps "$MAX_STEPS" \
  --max-errors "$MAX_ERRORS" \
  --agent llm_agent \
  --agent-llm "$AGENT_MODEL" \
  --agent-llm-args "{\"api_base\":\"$AGENT_BASE_URL\",\"api_key\":\"EMPTY\",\"temperature\":$TEMPERATURE}" \
  --user user_simulator \
  --user-llm "$USER_MODEL" \
  --user-llm-args "{\"api_base\":\"$USER_BASE_URL\",\"temperature\":$TEMPERATURE}" \
  --save-to "$RUN_DIR"

"$REPO_PYTHON" "$REPO/scripts/eval/summarize_results.py" \
  --results "$RUN_DIR/results.json" --split test20 --root "$REPO"
