# 实施状态

阶段：Phase 0。日期：2026-10-10。当前开发目标：Windows 本地主项目 `main`。
原始初始化在 `phase/00-project-init` Worktree 完成，迁移记录见 `LOCAL_MIGRATION_REPORT.md`。

## 已实现

- 简洁 Python 工程、`airline_data` 可安装包、固定 pytest/Ruff 开发依赖。
- 固定 τ² Git Commit 与可选环境依赖，官方 Task/Split/License 原始快照及 SHA256 锁。
- 官方 Train30/Test20 验证、固定 seed=42 的 Train24/Dev6 生成和一致性检查。
- Teacher/SFT/GRPO 训练 ID 与逐行 JSONL 来源准入检查，违规立即失败。
- CPU 单元测试、Ruff、GitHub Actions 文件、敏感文件与训练产物忽略规则。
- README、AGENTS、项目规划、架构、数据协议、开发流程和上游调查记录。
- 后续 teacher/sft/grpo/eval YAML 契约均禁用，无后续执行入口。

## 实际验收

Windows 本地独立 `.venv`，Python 3.11.9，pytest 8.3.5，Ruff 0.11.6。
命令均使用 `.venv/Scripts/python.exe`，不是系统的旧版 `py` 或其他环境的 pytest。
以下为首次 Phase 0 Worktree 验收结果；迁移后在本地主项目重新运行的实际结果见
`LOCAL_MIGRATION_REPORT.md`，其中 pytest 为 102 passed in 1.89s。

| 检查 | 实际结果 |
| --- | --- |
| `python -m pytest` | **102 passed in 3.45s**；防泄漏 77 项，划分/快照/CLI 25 项 |
| `python -m ruff check .` | All checks passed |
| `python -m ruff format --check .` | 7 files already formatted |
| `python scripts/check_splits.py` | Train30 / Test20、Train24 / Dev6、真实 50 ID、三份快照 SHA256 均通过；两两无交集 |
| `python -m pip check` | No broken requirements found |
| `git diff --check` / 逐文件 `--no-index --check` | 全部 33 个项目文件检查完成，0 个空白错误 |
| Git 快照字节保留 | 三份官方文件经 Git 过滤与原始 hash-object 结果相同，换行转换不会破坏哈希 |
| `git check-ignore` | .env、密钥环境文件、Checkpoint、JSONL、虚拟环境、Python 缓存、日志、权重和临时产物均被忽略 |

全部 24 个训练 ID 在三类训练入口准入，全部 6 个 Dev 和 20 个 Test ID 在
Teacher/SFT/GRPO 入口均被拒绝，即使它们自报 `split=train24` 也拒绝。
测试还实际覆盖错误来源字段、缺 ID/来源、坏 JSONL 的文件与行号、重复 JSON key、
空数据、错误 seed/算法，以及快照字节或锁文件被改动时的失败行为。

Dev6 的确切 ID 为 `10, 11, 40, 0, 4, 36`；Train24 与 Test20 的完整 ID 列表见
`configs/splits/train_dev_split.json` 和 `official_airline.json`。
官方 Commit：`4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699`。

GitHub Actions 尚未推送或运行，Linux 与 Python 3.12/3.13 的检查尚未实际运行。
完整 τ² 模拟环境及 GPU 环境尚未验证；不将 CPU 数据检查表述为环境集成通过。

## 实际目录与完整文件清单

原 Phase 0 共 33 个项目文件：1 个已存在文件修改（README），32 个新增文件。
迁移时增加 `docs/LOCAL_MIGRATION_REPORT.md`，当前共 34 个项目文件。
本地 `.venv` 和缓存被忽略，不计入提交清单。未创建未来模块的空 Python 文件。

```text
airline-agent-rl/
├── .github/workflows/ci.yml
├── .gitattributes
├── .gitignore
├── AGENTS.md
├── README.md                         # 修改
├── pyproject.toml
├── requirements-dev.lock
├── configs/
│   ├── tau2.lock.json
│   ├── teacher.yaml
│   ├── sft.yaml
│   ├── grpo.yaml
│   ├── eval.yaml
│   └── splits/
│       ├── official_airline.json
│       └── train_dev_split.json
├── src/data/
│   ├── __init__.py
│   ├── splits.py
│   └── leakage_checker.py
├── scripts/check_splits.py
├── tests/
│   ├── conftest.py
│   ├── test_splits.py
│   └── test_leakage_checker.py
├── docs/
│   ├── PROJECT_PLAN.md
│   ├── ARCHITECTURE.md
│   ├── DATA_PROTOCOL.md
│   ├── DEVELOPMENT_WORKFLOW.md
│   ├── IMPLEMENTATION_STATUS.md
│   ├── LOCAL_MIGRATION_REPORT.md
│   └── UPSTREAM_REVIEW.md
├── vendor/tau2/
│   ├── README.md
│   ├── LICENSE
│   └── data/tau2/domains/airline/
│       ├── tasks.json
│       └── split_tasks.json
├── data/.gitignore
└── outputs/.gitignore
```

## Git 与本地迁移状态

本地主项目：`D:/Desktop/agentProject/airline-agent-rl`，分支 `main`。
迁移前本地 HEAD 与实际远程 main 均为
`c322198466487237e4f02ef30de68d3572e6a669`。
迁移通过校验后复制文件整合到 main 工作区，没有提交、推送或改变 main 的提交引用。
原 Worktree `C:/Users/lili/.codex/worktrees/d6b6/airline-agent-rl` 及完整备份保留。
后续 Phase 使用 Local 模式，不再新建 Worktree 或 PR。
新的本地主项目测试、完整性和敏感文件结果见 `LOCAL_MIGRATION_REPORT.md`。

## 未完成与下一阶段

Teacher 采集、轨迹验证、Verified SFT Dataset、SFT、GRPO、IRC、Runtime Gate 与
正式评估均未实现；这是阶段边界，不作为 Phase 0 的伪完成项。
完整 τ² 环境、DB、Policy 的本地运行与重置隔离尚未接入。
本机默认 Python 3.11.9 不符合完整 τ² 的 >=3.12,<3.14 要求；Phase 1 需独立 Python
3.12/3.13 环境。官方数据获取和划分核验无阻塞。

审核通过后的 Phase 1 建议：在本地主项目 Local 模式中准备固定版本完整环境，
先做不调用付费模型的加载/Schema/重置隔离测试，再实现 Train24 采集准入、真实来源记录、
轨迹验证及 Verified SFT 数据输出。模型/Simulator 选择、预算与 API 调用须在获准后执行。

没有模型训练、付费 API 调用、Test20 正式评测、GitHub push、PR 或 main 合并。
Phase 0 完成后停止，等待用户审核。
