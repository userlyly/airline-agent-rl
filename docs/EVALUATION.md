# 官方 Test20 评测

本文件说明如何用原生 Qwen3-4B 在官方 airline Test20 上跑基线，以及哪些部分
已经实际验证、哪些还没有。脚本放在本项目下，运行时复用同级 `tau2-bench` 的
完整官方环境——不复制上游源码，不重写官方评估器。

## 授权边界

**运行 Test20 是付费且不可回退的动作**，需要用户单独授权。当前项目授权为
Phase 0 及其迁移，明确排除正式 Test20 评测。脚本因此 fail-closed：

- 未设置 `AIRLINE_RL_ALLOW_TEST20_EVAL=1` 即拒绝运行；
- `TASK_SPLIT` 不是官方 `test` 时拒绝，除非显式设置 `AIRLINE_RL_ALLOW_NON_TEST_SPLIT=1`；
- 目标 run 目录已存在 `results.json` 时拒绝，绝不静默续跑或覆盖。

没有任何一份配置或默认路径能在未经授权时启动评测。

## 本地计算与外部调用

| 环节 | 位置 | 是否计费 |
| --- | --- | --- |
| Agent（Qwen3-4B） | 本地 vLLM，`127.0.0.1:8001` | 否 |
| 仿真环境、DB、Policy、工具 | 本地，官方 tau2 代码 | 否 |
| **User Simulator** | 外部 API `ai.ahzm.top` | **是，唯一计费点** |
| 打分（`reward_basis = DB, COMMUNICATE`） | 本地，无 LLM judge | 否 |

打分不需要模型：50 个 airline task 的 `reward_basis` 全部是 `{DB, COMMUNICATE}`，
`COMMUNICATE` 是纯子串匹配，`DB` 是重放参考动作后的终态哈希对比。
`nl_assertions` 虽然在 task JSON 里存在，但因为不在 `reward_basis` 中而**不会**被评估，
所以默认路径不会调用 LLM judge，CLI 也没有可以打开它的开关。

## 前置条件

1. Python >= 3.12 的 tau2 环境，位于 `<TAU2_DIR>/.venv`（本项目不复制上游源码）。
2. `<TAU2_DIR>` 的 Git HEAD 必须等于 [configs/tau2.lock.json](../configs/tau2.lock.json)
   锁定的 Commit；不一致时脚本拒绝运行，避免对着移动的 HEAD 出结果。
3. 本地 vLLM 环境（conda `qwen-vllm`）与已缓存的 `Qwen/Qwen3-4B-Instruct-2507` 权重。
4. User Simulator 的 `OPENAI_API_KEY`。

`serve_qwen3_4b.sh` 额外处理了两个本机坑，缺任一个都会让评测静默失败：

- **工具调用**：tau2 的 `llm_agent` 走原生 OpenAI tools API 且使用
  `tool_choice="auto"`。vLLM 必须带 `--enable-auto-tool-choice
  --tool-call-parser hermes`，否则请求直接 400，agent 一个工具都调不了。
- **nvcc 版本**：FlashInfer 启动时要用 nvcc 即时编译采样算子，本机
  `/usr/bin/nvcc` 是 CUDA 11.5，不认识 `--compress-mode=size` 会导致引擎起不来。
  脚本按 torch 的 CUDA 版本选 `/usr/local/cuda-<ver>`。

启动后建议先跑一次本地工具调用冒烟测试，确认 `/v1/models` 可用且带 `tools` 的
请求返回 `finish_reason: tool_calls`，再开始计费运行。

## 运行步骤

```bash
# 1. 物化并校验运行数据（离线，只读上游 + 写 gitignore 的 data/）
python scripts/eval/prepare_data.py

# 2. 起本地 agent 服务（消耗 GPU）
GPU=0 scripts/eval/serve_qwen3_4b.sh

# 3. 干跑：只校验本地条件并打印解析后的配置，不发起任何调用
scripts/eval/run_base_test20.sh --dry-run

# 4. 获得授权后正式运行
AIRLINE_RL_ALLOW_TEST20_EVAL=1 \
AIRLINE_RL_ENV_FILE=/path/to/tau2-bench/.env \
scripts/eval/run_base_test20.sh
```

结果写入 `outputs/runs/<RUN_NAME>/results.json`（被 gitignore），
脚本随后自动汇总到同目录的 `summary.json` 与 `summary.md`。

## 冻结协议

| 项 | 值 |
| --- | --- |
| domain / split | `airline` / `test`（20 个 task） |
| num_trials | 5（每个 trial 由主 seed 派生出独立 seed） |
| seed | 300 |
| max_steps / max_errors | 200 / 10 |
| temperature | 0.0（agent 与 simulator，与上游默认一致） |
| agent | `llm_agent` + `openai/qwen3-4b` @ 本地 vLLM |
| user | `user_simulator` + `openai/gpt-5.6-sol` @ `ai.ahzm.top` |
| run name | `qwen3_4b_airline_base_test20_x5` |

20 task × 5 trial = **100 次运行**；报告的头条数字是 成功数 / 100，
即该配置下单次运行成功率的估计。tau2 从主 seed 派生每个 trial 的 seed
（`runner/batch.py`），所以 5 次是真正独立的运行，不是同一次运行的复制。

同一份协议记录在 [configs/eval.yaml](../configs/eval.yaml)。这些值在第一次报告
Test20 数字之前冻结，之后不因为看到结果而调整。

## 统计口径

- 成功判据沿用 tau2：reward 与 1.0 的差在 `1e-6` 以内。
- 分母是**实际被评估**的 trajectory 数；未被评估的单独记为 `unevaluated`，
  不与失败混同。
- 分母为零时成功率记为 `null`／`n/a`，不写成 0 或 1。
- `--split test20` 会先经 `EvalGuard` 校验切片与官方 Test20 完全相等：
  少一个、多一个或重复都会拒绝，避免把不完整的运行当成可比基线。
- 多次 trial 时额外报告逐 task 的 `reward_std` 与全局 `trial_spread`：
  **若多数 task 的 5 次 reward 完全相同，说明这些重复没有带来额外信息**
  （temperature 0 下两侧都可能高度确定），此时 100 次并不比 20 次更可信。
  报告必须先看这一项，再决定是否引用平均值。
- Test20 中只有 1 个 task 有 `communicate_info`，因此 19 个 task 的
  `COMMUNICATE` 恒为 1.0，**分数实质上由 DB 检查决定**；报告需同时给出
  DB 与 COMMUNICATE 分量，避免把 COMMUNICATE 的平凡通过误读为沟通能力达标。

## 准入设计

`LeakageChecker` 按设计**没有** `eval` stage：它的职责是拦住进入训练的
held-out ID，而评测正是要看到 Test20 内容。评测使用独立模块
`airline_data.eval_guard`，做相反的检查——选择必须**恰好等于**官方 Test20。
两个准入器不共用 stage，`stage="eval"` 依旧被拒绝。

## 对既有证据的离线复核

无需 GPU、不花钱，可以复核 2026-09-30 的 `base` 五十任务运行：

```bash
python scripts/eval/summarize_results.py \
  --results ../tau2-bench/data/simulations/qwen3_4b_airline_base50/results.json \
  --split test20
# -> 5/20 (0.250)
```

## 已验证 / 未验证

已实际验证（本仓库内可复现）：

- 锁定的三个 vendor 快照文件与本地 `tau2-bench` 当前 Commit 逐字节一致。
- 官方环境可离线加载：`get_tasks("test")` 返回 20 个 ID，`get_environment()` 加载
  DB、Policy 与 14 个工具。
- 全部 50 个 task 的 `reward_basis` 为 `{DB, COMMUNICATE}`，且既有运行记录中
  `nl_assertions` 全为 `None`。
- 上述 `base` 运行切片得到 Test20 = 5/20。
- 所有门控（授权、Commit、endpoint、密钥、run 目录冲突）在未授权场景下均拒绝。

**未验证**（不得声称通过）：

- 本次没有启动 vLLM、没有调用任何模型或 API、没有运行 Test20。
- `TAU2_DATA_DIR` 重定向到本项目 `data/` 的完整链路尚未端到端跑通。
- 锁文件中的 URL 未联网核对：只比对过本地 `tau2-bench` checkout 的字节。
