# 实施状态

阶段：Phase 0 及其向本地主项目 `main` 的迁移，外加「Test20 评测接入」的**能力**部分。
日期：2026-10-10。当前开发目标：Windows 本地主项目 `main`。
原始初始化在 `phase/00-project-init` Worktree 完成，迁移记录见 `LOCAL_MIGRATION_REPORT.md`。

## 已实现

- 简洁 Python 工程、`airline_data` 可安装包、固定 pytest/Ruff 开发依赖。
- 固定 τ² Git Commit 与可选环境依赖，官方 Task/Split/License 原始快照及 SHA256 锁。
- 官方 Train30/Test20 验证、固定 seed=42 的 Train24/Dev6 生成和一致性检查。
- Teacher/SFT/GRPO 训练 ID 与逐行 JSONL 来源准入检查，违规立即失败。
- CPU 单元测试、Ruff、GitHub Actions 文件、敏感文件与训练产物忽略规则。
- README、AGENTS、项目规划、架构、数据协议、开发流程、评测手册和上游调查记录。
- 后续 teacher/sft/grpo/eval YAML 契约均禁用，无后续执行入口。

本次新增（评测接入的能力层，**未实际执行评测**）：

- 上游 pin 从 `4ce7c039` 对齐到 `5bfa7e3`（数据逐字节相同，划分不变），
  锁文件新增 `runtime_files` 段锁定 `db.json` / `policy.md` 的 SHA256。
- `airline_data.runtime_lock`：把运行数据从本地 τ² checkout 物化到被忽略的
  `data/`，写入前先校验**全部**来源，逐文件 SHA256 复核。
- `airline_data.eval_guard`：评测准入，选择必须恰好等于官方 Test20；
  与 `LeakageChecker` 分离，`stage="eval"` 依旧被拒绝。
- `airline_data.summary` + `scripts/eval/` 五个脚本：数据准备、preflight、
  汇总、vLLM 启动封装、fail-closed 的 Test20 主入口（支持 `--dry-run`）。
- `configs/eval.yaml` 记录冻结协议；`.env.example` 提供占位符（真实 `.env` 被忽略）。

## 实际验收

Linux 服务器，仓库内 `.venv`，Python 3.13.5，pytest 8.3.5，Ruff 0.11.6。
Windows 本地后续复核需用同一套命令重跑，本节**不代表** Windows 结果。

| 检查 | 实际结果 |
| --- | --- |
| `python -m pytest` | **152 passed in 0.89s** |
| `python -m ruff check .` | All checks passed |
| `python -m ruff format --check .` | 16 files already formatted |
| `python scripts/check_splits.py` | commit `5bfa7e3`、Train30/Test20、Train24/Dev6、三份快照 SHA256 均通过，两两无交集 |
| `scripts/eval/run_base_test20.sh --dry-run` | 退出码 0；物化并校验 4 份运行数据，解析出 20 个 Test20 ID，未发起任何调用 |
| 无授权时 `run_base_test20.sh` | 退出码 1，打印授权要求后拒绝 |
| 既有 base50 运行按 Test20 切片 | **5/20 (0.250)**；DB 均值 0.250、COMMUNICATE 均值 0.950 |

测试分布：`test_splits.py` 25、`test_leakage_checker.py` 77、`test_runtime_lock.py` 11、
`test_eval_guard.py` 26、`test_summarize_results.py` 13，合计 152。
全部 24 个训练 ID 在三类训练入口准入，全部 6 个 Dev 和 20 个 Test ID 在
Teacher/SFT/GRPO 入口均被拒绝，即使它们自报 `split=train24` 也拒绝。

Dev6 的确切 ID 为 `10, 11, 40, 0, 4, 36`；Train24 与 Test20 的完整 ID 列表见
`configs/splits/train_dev_split.json` 和 `official_airline.json`。
官方 Commit：`5bfa7e37b36656b37dc6d022156be6563c1007f3`。

GitHub Actions 尚未推送或运行，Linux 与 Python 3.12/3.13 的 **CI** 结果尚未实际运行
（上表是本机手动执行，不是 CI）。

### 关于 5/20 这一数字

它是**既有** `qwen3_4b_airline_base50` 运行（2026-09-30，全 50 task）按 Test20
切分得到的复核值，不是本次新跑的结果；本次没有运行任何模型。它的用途是证明汇总
口径可复现、并与冻结协议一致。正式基线仍需按
[EVALUATION](EVALUATION.md) 显式重跑 `--task-split-name test` 后才可引用。

## 未验证（不得声称通过）

- 本次**没有**启动 vLLM、**没有**占用 GPU、**没有**调用任何模型或付费 API、
  **没有**运行 Test20。
- `TAU2_DATA_DIR` 指向本项目 `data/` 后的完整端到端跑通路径尚未验证。
- `5bfa7e3` 在远程仓库的字节内容未联网核对，只比对了本地 checkout；锁文件 URL 属未验证项。
- 评测用 vLLM 服务与 `qwen3-4b` 的 function calling 兼容性未验证（`llm_agent` 走
  原生 tools API，需要模型支持工具调用）。
- 完整 τ² 模拟环境及 GPU 环境尚未在本项目侧验证；不将 CPU 数据检查表述为环境集成通过。

## 实际目录与完整文件清单

当前 git 跟踪 35 个项目文件，本次新增 13 个、修改 13 个，合计触及 26 个文件。
本地 `.venv`、`data/`、`outputs/` 和缓存被忽略，不计入。未创建未来模块的空 Python 文件。

新增（13）：

```text
.env.example
docs/EVALUATION.md
src/data/{runtime_lock,eval_guard,summary}.py
scripts/eval/{prepare_data,preflight,summarize_results}.py
scripts/eval/{serve_qwen3_4b,run_base_test20}.sh
tests/{test_runtime_lock,test_eval_guard,test_summarize_results}.py
```

修改（13）：

```text
README.md
pyproject.toml
configs/tau2.lock.json
configs/eval.yaml
configs/splits/{official_airline,train_dev_split}.json
src/data/splits.py
vendor/tau2/README.md
docs/{ARCHITECTURE,DATA_PROTOCOL,IMPLEMENTATION_STATUS,PROJECT_PLAN,UPSTREAM_REVIEW}.md
```

未改动：`.github/workflows/ci.yml`（保持纯 CPU、离线）、`requirements-dev.lock`、
`.gitignore` / `.gitattributes`、`configs/{teacher,sft,grpo}.yaml`、
`tests/{conftest,test_splits,test_leakage_checker}.py`、`vendor/tau2/` 下的官方快照字节。

## Git 与本地迁移状态

本地主项目：`D:/Desktop/agentProject/airline-agent-rl`，分支 `main`。
迁移前本地 HEAD 与实际远程 main 均为
`c322198466487237e4f02ef30de68d3572e6a669`。
迁移通过校验后复制文件整合到 main 工作区，没有提交、推送或改变 main 的提交引用。
原 Worktree `C:/Users/lili/.codex/worktrees/d6b6/airline-agent-rl` 及完整备份保留。
后续 Phase 使用 Local 模式，不再新建 Worktree 或 PR。

本次同样**未提交、未推送**。改动位于工作区，等待用户审核后再决定提交范围。

## 未完成与下一阶段

Teacher 采集、轨迹验证、Verified SFT Dataset、SFT、GRPO、IRC 与 Runtime Gate
均未实现；这是阶段边界，不作为已完成项。评测路径已接通但未运行，因此没有本项目的
Test20 基线数字。

下一步由用户决定，按依赖顺序大致为：

1. 审核本次改动与文件清单，授权后再提交。
2. 单独授权后起 vLLM 并跑正式 Test20，产出 base 基线。
3. 进入 Train24 采集准入、真实来源记录、轨迹验证与 Verified SFT 数据输出；
   模型/Simulator 选择、预算与 API 调用须再次获准。

审核前的最后状态：没有模型训练、没有付费 API 调用、没有 Test20 正式评测、
没有 GitHub push、PR 或 main 合并。完成后停止，等待用户审核。
