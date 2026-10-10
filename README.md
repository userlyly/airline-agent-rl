# AirlineAgent-RL

基于官方 τ²-bench Airline、Qwen3-4B 的 Agentic RL 工程。当前仅完成
**Phase 0：项目初始化、官方数据划分、防泄漏校验与 CPU 测试**。

训练协议：官方 Train30 / Test20；固定种子 `42` 将 Train30 划分为
Train24 / Dev6。Teacher、SFT、GRPO 只允许 Train24；Dev6 用于验证与模型选择；
Test20 留待最终对比。禁止合成新任务或导入参考项目的划分、轨迹。

上游固定 Commit：`5bfa7e37b36656b37dc6d022156be6563c1007f3`。
仓库保留带 SHA256 校验的官方任务、划分、许可证原始快照，离线检查不访问模型服务。
该 Commit 由 Phase 0 原 pin `4ce7c039` 对齐而来，两个 Commit 的 airline 数据逐字节
相同，划分结果未变，理由见 [上游调查](docs/UPSTREAM_REVIEW.md)。

## 本地检查

Phase 0 支持 Python 3.11–3.13。Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements-dev.lock -e ".[dev]"
.\.venv\Scripts\python.exe scripts/check_splits.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Linux/macOS 激活 `.venv` 后执行相同的 `python` 命令。包名为 `airline_data`，
源文件在 `src/data/`；采用显式 setuptools 映射，测试不依赖临时修改 `sys.path`。

显式重新生成划分：`python scripts/check_splits.py --write`。默认只验证、不写入。
验证未来训练数据：

```bash
python scripts/check_splits.py --jsonl data/my_records.jsonl --stage teacher
# --stage 可选 teacher / sft / grpo；首条违规立即返回非零退出码。
```

固定版本的完整 τ² 环境要求 **Python >=3.12,<3.14**。
`.[environment]` 是后续环境接入的固定 Git 依赖，本次没有安装。
Phase 1 还需准备同 Commit 的完整数据目录并验证重置机制；此最小快照不是可运行模拟环境。

## 官方 Test20 评测

`scripts/eval/` 下的薄封装脚本复用同级 `tau2-bench` 的官方环境（不复制源码、
不重写评估器），用原生 Qwen3-4B 跑官方 airline Test20 基线：

```bash
python scripts/eval/prepare_data.py          # 物化并哈希校验运行数据（离线）
scripts/eval/run_base_test20.sh --dry-run    # 只校验本地条件，不发起任何调用
```

**跑正式 Test20 需要单独授权**：脚本 fail-closed，未设置
`AIRLINE_RL_ALLOW_TEST20_EVAL=1` 时拒绝运行，且会核对 τ² 代码 Commit、本地
agent 服务可达性、User Simulator 密钥与目标 run 目录冲突。打分
（`DB` + `COMMUNICATE`）全部本地完成、无 LLM judge，唯一计费点是 User Simulator。
完整操作手册、冻结协议与已验证/未验证项见 [EVALUATION](docs/EVALUATION.md)。

本次没有起服务、没有调用任何模型或 API、没有运行 Test20。

## 实际目录

```text
.github/workflows/ci.yml
.gitattributes                     # 官方快照禁用换行转换
.env.example                       # 占位符；真实 .env 被忽略
configs/
  tau2.lock.json
  splits/{official_airline.json,train_dev_split.json}
  {teacher,sft,grpo,eval}.yaml       # 禁用的后续配置契约
src/data/{__init__,splits,leakage_checker,runtime_lock,eval_guard,summary}.py
scripts/check_splits.py
scripts/eval/{prepare_data,preflight,summarize_results}.py
scripts/eval/{serve_qwen3_4b,run_base_test20}.sh
tests/{conftest,test_splits,test_leakage_checker,test_runtime_lock,test_eval_guard,test_summarize_results}.py
docs/
  PROJECT_PLAN.md
  ARCHITECTURE.md
  DATA_PROTOCOL.md
  DEVELOPMENT_WORKFLOW.md
  EVALUATION.md
  IMPLEMENTATION_STATUS.md
  LOCAL_MIGRATION_REPORT.md
  UPSTREAM_REVIEW.md
vendor/tau2/                        # 官方原始快照，无嵌套 Git 仓库
  README.md
  LICENSE
  data/tau2/domains/airline/{tasks,split_tasks}.json
data/.gitignore
outputs/.gitignore
AGENTS.md
pyproject.toml
requirements-dev.lock
.gitignore
```

未来 `teacher/training/rewards/safety` 的职责见 [架构说明](docs/ARCHITECTURE.md)，
当前不创建空 Python 实现。配置中的 `enabled: false` 仅是保留契约；当前没有读取
配置并运行后续阶段的入口，评测的唯一入口是被授权门控挡住的 shell 脚本。

完整协议见 [DATA_PROTOCOL](docs/DATA_PROTOCOL.md)，开发规范见
[AGENTS](AGENTS.md)，验收结果与未完成项见
[IMPLEMENTATION_STATUS](docs/IMPLEMENTATION_STATUS.md)。

后续采用 Windows Codex **Local** 模式，在本地主项目 `main` 工作区开发，测试与敏感文件
检查通过后按用户授权提交、推送 GitHub main，再由 Linux 服务器 `git pull --ff-only`。
不再要求各 Phase 使用 Worktree 或 PR，流程见 [开发规范](docs/DEVELOPMENT_WORKFLOW.md)。

本次只迁移 Phase 0 并验证，不提交、不推送，不运行模型、付费 API 或正式 Test20 评测。
迁移结果见 [本地迁移报告](docs/LOCAL_MIGRATION_REPORT.md)。
