# 架构与模块职责

## 当前实现

| 路径 | 职责 |
| --- | --- |
| `pyproject.toml` | 安装 `airline_data`、固定开发工具与可选 τ² Git 依赖 |
| `requirements-dev.lock` | 固定 CPU 开发工具的完整传递依赖；CI 和本地安装共用 |
| `configs/tau2.lock.json` | 上游仓库、Commit、原始文件 URL 与 SHA256 |
| `vendor/tau2/` | 原样保存官方 tasks、split_tasks 与 MIT 许可证，不包含 `.git` |
| `configs/splits/` | 带来源信息的官方 Train30/Test20 和固定种子的 Train24/Dev6 |
| `src/data/splits.py` | 核验锁文件/字节哈希、真实 ID、数量、集合关系和可重复划分 |
| `src/data/leakage_checker.py` | Task 选择及逐行 JSONL 训练准入检查；首条违规立即失败 |
| `scripts/check_splits.py` | 离线检查 CLI；显式 `--write` 才重建划分 |
| `tests/` | 真正快照与负例验证，临时目录中的错误数据不成为正式训练数据 |
| `.github/workflows/ci.yml` | Python 3.11/3.12/3.13 CPU 测试与 Ruff，无模型、密钥、GPU |
| `data/`, `outputs/` | 被忽略的本地产物位置，仅提交目录级 `.gitignore` |
| `configs/{teacher,sft,grpo,eval}.yaml` | 禁用的后续阶段契约，没有执行入口 |

包名为 `airline_data`，显式映射到 `src/data`，避免与顶层 `data/` 产物目录发生导入冲突。
调用者传入仓库根目录；安装包本身不携带完整环境，CLI 默认定位脚本所属仓库。

## 未来模块（未创建实现）

| 规划路径 | 职责与依赖 |
| --- | --- |
| `src/environment/` | 接入固定 τ² 的 Policy、Schema、User Simulator、数据库和重置；不重写官方环境 |
| `src/teacher/` | 先校验 Train24 选择，再采集多轮轨迹；记录模型版本、seed、trial、来源、预算 |
| `src/training/` | Verified SFT Dataset 转换、LoRA SFT、在线多轮 GRPO；所有输入先经过防泄漏准入 |
| `src/rewards/` | 官方评估器适配、轨迹验证、IRC 校准；独立保留官方与扩展评分 |
| `src/safety/` | Runtime Gate 的政策/授权/WRITE 判定，记录被拒绝尝试和合法写完成 |
| `src/evaluation/` | Dev6 验证、经授权的 Test20 最终评估与统一指标汇总 |

当前不创建这些目录中的空 Python 文件。Phase 1 的完整环境数据、模型接口与验证器
尚未安装或实现，Phase 0 不声称模拟或奖励计算已经可运行。

## 数据流与依赖

```text
固定 Commit 的官方快照 + 哈希锚点
    -> 官方 Train30/Test20 验证
    -> Random(42) 对官方 Train 顺序 shuffle
    -> Train24 + Dev6（与 Test20 隔离）

未来：Train24 选择校验 -> Teacher / Online Rollout
    -> 每条 ID 与来源校验 -> 轨迹验证 -> Verified SFT / GRPO
    -> Dev6 模型/阈值选择 -> 冻结协议 -> Test20 最终对比
```

数据层只依赖标准库。后续环境依赖可选 `tau2`，训练依赖将在相应阶段单独声明。
来源校验是元数据准入机制，不能证明轨迹内容未被人伪造，也不是政策正确性验证器；
Phase 1 必须把来源绑定到真实采集记录，Phase 4 再实现安全判定。
