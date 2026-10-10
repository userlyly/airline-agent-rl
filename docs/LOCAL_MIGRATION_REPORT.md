# Phase 0 向 Windows 本地主项目迁移

日期：2026-10-10。用户授权把 Phase 0 整合到本地 main，后续采用 Local 模式；本次不 Push。
为延续此前“不 Commit”的边界，此次也不暂存或提交。

## 迁移前核实与备份

- 来源：`C:/Users/lili/.codex/worktrees/d6b6/airline-agent-rl`，分支 `phase/00-project-init`。
- 目标：`D:/Desktop/agentProject/airline-agent-rl`，已在 `main`，无已跟踪文件修改。
- 实际远程 `refs/heads/main` 与本地 HEAD 均为 `c322198466487237e4f02ef30de68d3572e6a669`。
- 来源原有 33 个项目文件，逐文件记录 SHA256。被忽略的虚拟环境和缓存不属于代码迁移。
- 原目录有一张未跟踪截图 `屏幕截图 2026-10-10 133350.png`，原样保留，不属于 Phase 0 提交清单。
- 迁移前完整备份：`outputs/phase0-migration-backup-05c832b7/`，包含 source/、destination/ 与 manifest.json。
  来源 Worktree 与目标本地主项目的 outputs/ 均保留这份备份，输出目录由 Git 忽略。

## 安全整合方式

目标主目录已经检出 main，原 Worktree 尚无 Phase 0 提交，因此采用经过路径和冲突检查的文件复制，
将未提交成果整合到 main 工作区；没有强制切换分支、reset、clean、merge 或删除源目录。

官方数据、划分、Python 实现、测试与配置原样保留。
迁移过程中仅更新 AGENTS、README、开发流程、项目计划、实施状态五份文档，并新增本报告。
目标项目文件合计 34 个。复制后核验每个文件的 SHA256，并单独对照原始备份验证代码和数据没有改变。
写入前检查目标已有内容，出现未知改动即停止，不静默覆盖。

主目录重新创建 `.venv` 并本地 editable 安装，测试必须确认 `airline_data` 导入路径属于主目录，
不能误用原 Worktree 的 editable 包。原目录截图和备份保持可恢复。

## 实际检查结果

以下检查实际运行于 `D:/Desktop/agentProject/airline-agent-rl`，Python 3.11.9。
解释器为主目录 `.venv/Scripts/python.exe`；`airline_data` 实际导入路径为
`D:/Desktop/agentProject/airline-agent-rl/src/data/__init__.py`。

| 检查 | 实际结果 |
| --- | --- |
| 迁移完整性 | 34/34 项目文件与源目录 SHA256 一致；原 28 个代码/数据/配置/测试等未修改文件与迁移前备份一致 |
| 原文件保留 | 原 README 在备份中；原有截图字节未改变；原 Worktree 与备份均保留 |
| `python -m pytest` | **102 passed in 1.89s**；防泄漏 77 项，划分/快照/CLI 25 项 |
| `python -m ruff check .` | All checks passed |
| `python -m ruff format --check .` | 7 files already formatted |
| `python scripts/check_splits.py` | 官方 Train30/Test20、Train24/Dev6、两两无交集与快照 SHA256 校验通过 |
| `python -m pip check` | No broken requirements found |
| 项目文件 diff 空白检查 | 34 个文件，0 个错误 |
| 敏感文件与常见凭据模式扫描 | 34 个项目文件，0 个发现；检查了私钥及 GitHub/OpenAI/AWS/Slack 常见令牌模式，不把模式扫描声称为完整安全证明 |
| `git check-ignore` | .env、credentials、key、Checkpoint、JSONL、虚拟环境、outputs、日志和模型产物被忽略 |
| Git 暂存区 | 空；用户原有截图仍未跟踪，不属于项目待提交清单 |
| 实际远程 main | `c322198466487237e4f02ef30de68d3572e6a669`，与本地主项目 HEAD 一致 |

检查日志位于主目录 `outputs/phase0-migration-validation.log`，由 Git 忽略。
后续阶段的模型运行、完整 τ² 环境、Linux 检查和远程 GitHub CI 尚未执行。

## 最终 Git 与运行边界

main 提交引用保持原值，成果以未提交修改保存在本地主项目。原 Worktree 和阶段分支仍保留。
本次没有 Commit、Push、PR、GPU 训练、付费 API 调用、Test20 正式评估或 Phase 1 操作。
后续从本地主项目的 Codex Local 模式开始，测试后按用户授权提交、推送 main，由 Linux 拉取。
