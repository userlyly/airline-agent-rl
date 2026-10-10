# 上游调查与选型记录

调查日期：2026-10-10。仅只读访问开源代码和数据，未执行上游 runner。

## 官方 τ²-bench

固定 Commit：`4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699`。
[固定版本源码](https://github.com/sierra-research/tau2-bench/tree/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699)。

| 已阅读文件 | 发现及后续用途 |
| --- | --- |
| `data/tau2/domains/airline/tasks.json`、`split_tasks.json` | 真实 50 Task、官方 Train30/Test20；base 为全集；本项目只据此派生划分 |
| `src/tau2/domains/airline/environment.py` | `get_environment` 默认加载 FlightDB、AirlineTools 和官方 Policy；`get_tasks` 默认 base，接入必须显式选择 |
| `data/tau2/domains/airline/policy.md` | 数据库更新前需说明细节并取得确认，工具调用串行；后续授权/WRITE 验证必须依官方政策 |
| `src/tau2/domains/airline/tools.py` | `is_tool(ToolType.READ/WRITE/GENERIC)` 标注业务工具类型；不凭工具名称猜测 WRITE |
| `src/tau2/user/user_simulator.py` | 使用任务场景、对话状态与全局指南生成后续消息；实际运行会涉及模型，Phase 0 不调用 |
| `src/tau2/environment/environment.py`、`db.py` | 支持 `set_state`、初始化数据/动作、历史重放和 DB hash；每个 trial 应创建独立初始环境，不复用被修改 DB |
| `src/tau2/evaluator/evaluator.py`、`evaluator_env.py`、`docs/evaluation.md` | 官方依据任务 reward_basis 合成奖励；DB 对照参考动作重放后的 gold 终态，动作列表不等于唯一合法路径 |
| `pyproject.toml` | τ² 1.0.1 要求 Python >=3.12,<3.14；Phase 0 核心可以不安装这些依赖 |

官方 `db.json` 已通过固定版本目录树确认存在（7,042,725 字节），Policy 和 Tool 源码
也真实存在。Phase 0 仅保存 tasks/splits/license；完整 DB 和运行环境尚未下载或验证。
上游 `ALL_WITH_NL_ASSERTIONS` 等评估模式可能触发额外模型判定，后续应明确模式及成本，
不能把 CLI 默认调用假设为纯本地计算。

## 依赖方式

选择等价于固定 Submodule 的“固定 VCS 可选依赖 + 最小不可变数据快照”：
`pyproject.toml` 指向完整 Git SHA；锁文件和代码锚点记录官方文件哈希。
与 Submodule 相比，不引入嵌套 Git checkout、递归初始化或 Windows 共享元数据复杂度，
CPU CI 可以离线验证真实官方数据。没有复制模型、结果文件、旧轨迹或大段上游源码。
MIT 许可证原样保留。

Phase 1 必须准备同 Commit 的完整官方数据目录，明确 τ² 数据定位方式，
检查环境 reset/重放隔离后再实现采集；不能仅凭 `pip install` 就声称完整环境可运行。

## Agentic RL 参考项目

[yuyu0529nya/tau2-agentic-rl 固定调查版本](https://github.com/yuyu0529nya/tau2-agentic-rl/tree/2e038bfcf32f5cf7aa033c9efb4124dcc90d9654)
Commit：`2e038bfcf32f5cf7aa033c9efb4124dcc90d9654`。仅工程参考，不是训练数据来源。

| 已调查文件 | 可借鉴设计 |
| --- | --- |
| `scripts/grpo/collect_rollouts.py` | 复用 τ² 对话、工具执行与奖励机制，显式 Task IDs 和多 trial 采集，检查工具错误与组内奖励方差 |
| `scripts/grpo/build_rft_dataset.py` | 成功过滤、Task 内轨迹去重、每 Task 数量上限；本项目还必须加入独立轨迹验证与来源准入 |
| `scripts/grpo/grpo_update.py` | rollout 输入与更新分离、组相对优势、assistant token mask；后续需针对 Qwen3 实际验证，不能直接搬用旧模型实现 |
| `scripts/grpo/run_teacher_collect.sh` | Teacher 使用相同 Policy/Schema 与 τ² machinery；脚本含 API 调用，本次仅阅读，没有执行 |
| `reports/airline_distill_sft.md` | 完整多轮轨迹、序列长度与 mask 的工程风险，不把参考实验数字当成本项目结果 |
| `reports/airline_distill_grpo.md` | SFT warm start、组内方差与公平评测的工程参考，不据此承诺本项目收益 |

该项目采用自定义 30/20 划分，与官方划分不同。数量相同不代表 Task 集相同。
本次没有下载其划分、Rollout、模型或日志，没有复用其训练数据和实验结论。
