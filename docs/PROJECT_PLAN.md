# 项目规划

## 背景与问题定义

AirlineAgent-RL 研究 Qwen3-4B 如何在官方 τ²-bench Airline 的多轮交互中完成
工具调用，同时遵守政策和用户授权。仅以终态成功衡量行为可能遗漏过程中不安全的
WRITE；项目计划并列报告官方成功、安全行为与有效业务完成情况。

数据单位为官方 Task，轨迹与多次 trial 均继承 Task 的划分，不能按轨迹随机重划。
训练预算限定 Train24；Dev6 用于超参数、Checkpoint 与阈值选择；Test20 冻结至最终对比。

## 训练路线与阶段

| 阶段 | 计划产物 | 验收重点 |
| --- | --- | --- |
| Phase 0 | 工程初始化、固定依赖、30/20 与 24/6 划分、Leakage Checker | CPU 检查通过、数据来源可追溯 |
| Phase 1 Teacher | 官方环境接入、Teacher Rollout Collection、Trajectory Verification、Verified SFT Dataset | Train24 入口隔离、真实重置、原始/验证轨迹关联、来源和成本记录 |
| Phase 2 SFT | Qwen3-4B LoRA SFT | assistant-only loss mask、完整多轮轨迹、Dev6 选择 |
| Phase 3 GRPO | Online Multi-turn GRPO | 在线采集/更新闭环、同 Task 分组、优势方差与工具错误记录 |
| Phase 4 IRC / Safety | IRC / Reward Calibration、Runtime Safety Gate | 独立校准、授权与 WRITE 风险、避免用 Test 选择阈值 |
| Phase 5 Evaluation | Held-out Evaluation 与对照报告 | 固定试验协议、Test20 最终对比、结果可复现 |

当前只实现 Phase 0。后续各阶段在 Windows 本地主项目的 main 工作区以 Local 模式开发，
测试与敏感文件检查通过后按用户授权提交、推送，再由 Linux 服务器拉取。
不再要求 Worktree 或 PR；本次没有模型输出。

## 最终对照

1. Qwen3-4B Base。
2. Qwen3-4B + SFT。
3. Qwen3-4B + SFT + GRPO。
4. Qwen3-4B + SFT + GRPO + IRC。
5. Full Pipeline（加入 Runtime Gate）。

五组使用相同官方版本、Task 集、User Simulator、trial 数与随机种子协议。
完整 τ² 环境版本已固定，模型 revision、推理参数、Simulator 与预算需在后续阶段锁定。
参考项目的数字或自定义 Test 集不能作为本项目的基线结果。

## 主要指标（规划，当前未测量）

| 指标 | 计划定义/待锁定项 |
| --- | --- |
| Official Success Rate | 使用固定版本官方 `reward_basis` 的成功判据；报告任务与 trial 聚合方式 |
| Verified Clean Success Rate | 官方成功且轨迹验证无违规；验证规则在 Phase 1/4 明确 |
| Unsafe WRITE Rate | 明确以 WRITE 尝试为分母，记录未经授权或违反政策的尝试；零分母单独标记 |
| Valid WRITE Completion Rate | 对需要且允许 WRITE 的任务统计正确完成；不能用“禁止全部 WRITE”获得安全收益 |
| Tool Error Rate | 以工具调用为分母记录调用/执行错误；零分母单独标记 |

Phase 4/5 需区分 Gate 拦截前的尝试和实际执行的 WRITE，避免隐藏风险。
具体判据、分母、置信区间和 trial 协议在首次实验前冻结，不根据 Test20 调整。
