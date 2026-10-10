# Windows Local 开发流程

用户已决定采用 Windows 本地 main 开发，不再使用 Git Worktree 和 PR。

```text
Windows Codex Local / 本地主项目 main
  -> 开发当前 Phase
  -> 本地测试 + 静态检查 + 敏感文件检查 + diff 审查
  -> 按用户授权 commit / push GitHub main
  -> Linux 服务器 git pull --ff-only
  -> Linux 对相应阶段运行检查与经授权的实验
```

开发目录：`D:/Desktop/agentProject/airline-agent-rl`。在 Codex 中使用该项目的 Local 模式。
当前聊天原执行目录仍是旧 Worktree；迁移操作和新测试显式在本地主项目进行。
不以复制代码改变聊天的执行模式，后续任务应从本地主项目 Local 入口开始。

## Phase 与 Git 规范

所有 Phase 均使用本地主项目 main 工作区，不再要求 phase/* 分支或独立 Worktree。
当前仅迁移 Phase 0，原 Worktree、原阶段分支与备份保留，不自动删除或丢弃其修改。
本次不暂存、不提交、不推送；此时成果在本地 main 的未提交工作区中。

开始开发前检查 `git status --short --branch`、`git branch --show-current`、远程地址。
不使用 `git reset --hard`、`git clean` 或强制推送覆盖已有成果。
如果目录存在未知未提交修改，先区分并备份，不静默覆盖。

## 检查与提交

1. 在本地主项目创建独立 `.venv`，使用 `python -m pip install -c requirements-dev.lock -e ".[dev]"`。
2. 运行 `python scripts/check_splits.py`、`python -m pytest`、Ruff lint 和格式检查。
3. 审查 Git diff 与所有待提交文件，核实 .env/密钥、JSONL、模型、日志和临时输出均未被纳入。
4. 报告真实测试结果。提交和推送根据当次用户授权执行，使用明确文件清单暂存；不要把原有截图等无关文件一起提交。
5. 推送前获取远程 main 状态；如远程有新增提交，先备份本地成果再安全整合，冲突处理后重新测试。禁止强制覆盖远程。
6. 获准后提交并推送 main，Linux 在干净工作区 `git pull --ff-only origin main`；服务器如有修改或无法快进，先检查，不能强制重置。

远程检查可使用 `git ls-remote origin refs/heads/main`；正式整合前使用 fetch 获取所需历史。
GitHub Actions 仅 CPU 检查，不安装训练依赖、不配置 LLM Secrets、不使用 GPU。
本次没有推送，因此远程 CI 未运行；文件存在不代表远程 CI 已通过。

## Windows 与 Linux 环境

使用 `python` 核实解释器版本，本机默认 Python 3.11.9，系统 `py` 指向 3.6.7。
Phase 0 可用 Python 3.11–3.13；完整 τ² 环境要求 >=3.12,<3.14。
官方字节快照由 `.gitattributes` 禁用换行转换，项目文本采用 LF。
Git 所有权检查仅对已知目录使用单次 `-c safe.directory=<绝对路径>`，不全局通配信任。

GPU 训练、付费模型调用和 Test20 正式评估只属于经用户授权的后续阶段。
本次没有进入 Phase 1，没有连接 Linux 服务器或启动模型。
