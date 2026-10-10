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
| `src/data/runtime_lock.py` | 从本地 τ² checkout 物化 `db.json`/`policy.md` 到被忽略的 `data/`，逐文件 SHA256 校验 |
| `src/data/eval_guard.py` | 评测准入：选择必须恰好等于官方 Test20；与 `LeakageChecker` 分离 |
| `src/data/leakage_checker.py` | Task 选择及逐行 JSONL 训练准入检查；首条违规立即失败 |
| `src/data/summary.py` | 把 τ² `results.json` 归约为可复现的成功率、分量与逐 task 指标 |
| `scripts/check_splits.py` | 离线检查 CLI；显式 `--write` 才重建划分 |
| `scripts/eval/prepare_data.py` | 物化并校验运行数据；`--verify-only` 只校验 |
| `scripts/eval/preflight.py` | 起服务/运行前的组合检查，打印将使用的 Test20 ID |
| `scripts/eval/summarize_results.py` | 汇总 CLI，写 `summary.{json,md}`；可按 Test20 切片既有运行 |
| `scripts/eval/serve_qwen3_4b.sh` | 本地 vLLM 启动封装（GPU/端口/模型可配） |
| `scripts/eval/run_base_test20.sh` | Test20 主入口，fail-closed，支持 `--dry-run` |
| `tests/` | 真正快照与负例验证，临时目录中的错误数据不成为正式训练数据 |
| `.github/workflows/ci.yml` | Python 3.11/3.12/3.13 CPU 测试与 Ruff，无模型、密钥、GPU |
| `data/`, `outputs/` | 被忽略的本地产物位置，仅提交目录级 `.gitignore` |
| `configs/{teacher,sft,grpo,eval}.yaml` | 禁用的后续阶段契约；`eval.yaml` 另记录冻结评测协议 |

包名为 `airline_data`，显式映射到 `src/data`，避免与顶层 `data/` 产物目录发生导入冲突。
调用者传入仓库根目录；安装包本身不携带完整环境，CLI 默认定位脚本所属仓库。

## 评测接入的落点

`src/evaluation/` **不会**被创建。评测逻辑按包映射的既有约定平铺在 `src/data/` 下
（`eval_guard.py`、`summary.py`），执行入口在 `scripts/eval/`，与
`scripts/check_splits.py` 引用 `airline_data` 的方式一致。

`src/environment/` 同样**不会**被创建：仿真环境、Policy、DB、工具、User Simulator
和 Evaluator 全部复用同级 `tau2-bench` checkout。本项目只写薄封装脚本，不重写官方
环境、评估器或工具集，因此不存在会被误当成"官方实现"的本地副本。
评测数据的字节由 `runtime_lock` 对着锁文件校验，代码版本由运行脚本核对 Git Commit。

## 未来模块（未创建实现）

| 规划路径 | 职责与依赖 |
| --- | --- |
| `src/teacher/` | 先校验 Train24 选择，再采集多轮轨迹；记录模型版本、seed、trial、来源、预算 |
| `src/training/` | Verified SFT Dataset 转换、LoRA SFT、在线多轮 GRPO；所有输入先经过防泄漏准入 |
| `src/rewards/` | 官方评估器适配、轨迹验证、IRC 校准；独立保留官方与扩展评分 |
| `src/safety/` | Runtime Gate 的政策/授权/WRITE 判定，记录被拒绝尝试和合法写完成 |

当前不创建这些目录中的空 Python 文件。Teacher 采集、训练与安全判定尚未实现；
评测侧的路径已接通并离线验证，但**尚未实际运行**（未起服务、未调用任何模型、
未跑 Test20），因此不声称已有基线数字。详见 [EVALUATION](EVALUATION.md)。

## 数据流与依赖

```text
固定 Commit 的官方快照 + 哈希锚点
    -> 官方 Train30/Test20 验证
    -> Random(42) 对官方 Train 顺序 shuffle
    -> Train24 + Dev6（与 Test20 隔离）

评测（已接通，待授权运行）：
运行时数据 (db.json/policy.md) --runtime_lock--> data/ (gitignore)
    -> EvalGuard 校验选择 == 官方 Test20
    -> 本地 vLLM 起 agent + 付费 User Simulator
    -> 官方 τ² evaluator 打分 (DB + COMMUNICATE, 无 LLM judge)
    -> results.json -> summary.py -> summary.{json,md}

未来：Train24 选择校验 -> Teacher / Online Rollout
    -> 每条 ID 与来源校验 -> 轨迹验证 -> Verified SFT / GRPO
    -> Dev6 模型/阈值选择 -> 冻结协议 -> Test20 最终对比
```

数据层只依赖标准库，包括评测侧的 `runtime_lock`/`eval_guard`/`summary`；只有真正
发起评测的 shell 入口依赖 τ² 环境与外部 API，且被授权门控挡住。
来源校验是元数据准入机制，不能证明轨迹内容未被人伪造，也不是政策正确性验证器；
Phase 1 必须把来源绑定到真实采集记录，Phase 4 再实现安全判定。
