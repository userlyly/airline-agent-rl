# AirlineAgent-RL 开发规范

## 当前授权

当前为 Phase 0 及其向本地主项目 main 的迁移。只初始化工程、固定上游、验证划分、
实现防泄漏检查及迁移核验。本次不提交、不推送。
完成检查后停止，等待用户审核。未经新授权不进入 Phase 1，不运行 Teacher、
SFT、GRPO、GPU 训练、付费 API 或正式 Test20 评测。

## Windows Local 与 Git

- 用户已改为 Windows Local 开发，在本地主项目的 `main` 工作区完成后续 Phase。
- 不再为各 Phase 创建 Git Worktree 或 PR；Linux 服务器通过 `git pull --ff-only` 接收代码。
- 不创建嵌套 Git 仓库，不修改旧项目或历史数据。
- 提交和推送按照当次用户授权执行；禁止强制推送、未经授权删除分支或丢弃工作区修改。
- 完成每阶段时运行相关测试和静态检查，审查 Git diff，报告文件清单和真实结果。
- 推送前检查远程 main 与本地的关系，远程有新增提交时先安全整合、重新测试，不能覆盖。
- 使用明确文件清单暂存，避免把用户截图、密钥和其他无关文件加入提交。
- 原 Phase 0 Worktree 和迁移备份保留以便审核，不自动清理含未提交成果的目录。

## 数据约束

- 使用 `configs/tau2.lock.json` 固定版本的官方 Airline 数据；不合成新 Task。
- 训练只允许 Train24，Dev6 只用于验证和模型选择，Test20 只用于最终性能对比。
- 禁止使用上游默认 `base` 作为训练选择，它包含 Train 和 Test 全集。
- 后续任何采集入口先调用 `LeakageChecker.validate_task_ids`，任何数据入口调用
  `validate_jsonl` 或 `validate_record`；失败必须向上传播，禁止忽略异常继续训练。
- 缺 Task ID、缺来源或版本不匹配时默认拒绝，不通过补写伪造字段绕过校验。
- 官方快照不可就地修改。版本更新必须同步审查 Commit、哈希锚点、锁文件、
  生成划分、测试和文档，重新取得审核。
- 不导入参考项目的训练轨迹、Checkpoint、自定义划分或结果作为本项目证据。
- 不提交密钥、完整 JSONL 轨迹、模型权重、训练日志或评测输出。

## 工程与检查

Phase 0 使用 `pyproject.toml`，核心模块仅标准库，包名 `airline_data`。
后续模块按实际需要实现，避免空实现、伪造模拟结果和大量历史代码复制。

```bash
python scripts/check_splits.py
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

CI 仅 CPU 检查，不配置 API 密钥，不安装 `.[environment]` 或训练依赖。
无法实际验证的运行环境、CI 服务结果或算法指标必须写为未验证，不能声称通过。
