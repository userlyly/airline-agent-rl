#!/usr/bin/env bash
# Serve the base (non-fine-tuned) Qwen3-4B that the airline baseline uses as the AGENT.
#
# vLLM is not installed in the tau2 venv; it lives in its own conda environment.
# The served model name defaults to `qwen3-4b` so that `--agent-llm openai/qwen3-4b`
# resolves against the local endpoint. This script consumes a GPU: run it only
# when an evaluation has actually been authorized.
#
# Overridable: GPU PORT MODEL SERVED_NAME CONDA_ENV MAX_MODEL_LEN GPU_MEMORY_UTILIZATION
set -euo pipefail

CONDA_ENV="${CONDA_ENV:-$HOME/zhangmm/miniconda3/envs/qwen-vllm}"
MODEL="${MODEL:-Qwen/Qwen3-4B-Instruct-2507}"
SERVED_NAME="${SERVED_NAME:-qwen3-4b}"
PORT="${PORT:-8001}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
GPU="${GPU:-0}"

if [[ ! -x "$CONDA_ENV/bin/vllm" ]]; then
  echo "vLLM not found at $CONDA_ENV/bin/vllm; set CONDA_ENV to its environment." >&2
  exit 1
fi

# FlashInfer JIT-compiles its sampling kernels at startup and needs an nvcc new
# enough for the flags it passes. This host's /usr/bin/nvcc is CUDA 11.5 and dies
# on --compress-mode=size, so point CUDA_HOME at the toolkit matching the torch
# build (torch here is cu130 -> /usr/local/cuda-13.0) unless already set.
if [[ -z "${CUDA_HOME:-}" ]]; then
  torch_cuda="$("$CONDA_ENV/bin/python" -c 'import torch; print(torch.version.cuda or "")' 2>/dev/null || true)"
  if [[ -n "$torch_cuda" && -x "/usr/local/cuda-$torch_cuda/bin/nvcc" ]]; then
    export CUDA_HOME="/usr/local/cuda-$torch_cuda"
  fi
fi
if [[ -n "${CUDA_HOME:-}" ]]; then
  export PATH="$CUDA_HOME/bin:$PATH"
fi

export CUDA_VISIBLE_DEVICES="$GPU"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"

echo "Serving $MODEL as '$SERVED_NAME' on 127.0.0.1:$PORT (GPU $GPU, vLLM from $CONDA_ENV)"
echo "nvcc: ${CUDA_HOME:-<default>} ($(command -v nvcc || echo 'none on PATH'))"

# tau2's llm_agent calls the native OpenAI tools API with tool_choice="auto".
# Without these two flags vLLM rejects those requests with HTTP 400 ("auto tool
# choice requires --enable-auto-tool-choice and --tool-call-parser"), so the
# agent could never call a tool and every task would fail for the wrong reason.
# Qwen3-Instruct emits Hermes-style <tool_call> blocks, hence the hermes parser.
exec "$CONDA_ENV/bin/vllm" serve "$MODEL" \
  --served-model-name "$SERVED_NAME" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --max-model-len "$MAX_MODEL_LEN" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION:-0.90}" \
  --enable-auto-tool-choice \
  --tool-call-parser "${TOOL_CALL_PARSER:-hermes}"
