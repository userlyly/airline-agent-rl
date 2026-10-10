# 官方数据与隔离协议

## 来源与信任锚点

官方仓库：[sierra-research/tau2-bench](https://github.com/sierra-research/tau2-bench)。
固定 Commit：`5bfa7e37b36656b37dc6d022156be6563c1007f3`。
实际从此 Commit 下载 `data/tau2/domains/airline/tasks.json`、`split_tasks.json`
和 `LICENSE`，按原始字节保存到 `vendor/tau2/`。

`configs/tau2.lock.json` 保存完整 URL 与 SHA256；`splits.py` 中的同版本哈希锚点
用于拒绝快照和锁文件被同时替换的情况。该 Commit 是 2026-10-10 从 Phase 0 原 pin
`4ce7c039` 对齐而来：两个 Commit 的 airline 三个文件逐字节相同，哈希锚点未变，
因此只替换 Commit 与 URL，未改动任何划分结果（理由见
[UPSTREAM_REVIEW](UPSTREAM_REVIEW.md)）。

锁文件另有 `runtime_files` 段，记录运行评测才需要、但**不入库**的 6 个文件的
SHA256：airline 的 `db.json`、`policy.md`，以及 τ² 同样从 `TAU2_DATA_DIR`
读取的 `tau2/user_simulator/simulation_guidelines*.md`（4 个）。这些文件属
运行态数据（`db.json` 单文件 ~7 MB），由 `airline_data.runtime_lock` 从本地
τ² checkout 物化到被忽略的 `data/` 目录，并在使用前逐文件校验。
入库只保存锁定值，不保存字节。信任根仍是经审核的仓库代码，不能抵抗攻击者
同时修改验证代码。更新上游版本必须重新审核，不能运行时跟随 HEAD。
`.gitattributes` 对官方快照禁用换行转换，防止 Windows checkout 的 CRLF 转换破坏字节哈希；
项目自有文本统一 LF。

## 官方 30/20 与项目 24/6

- 已核实官方 50 个 Task ID 全部为字符串，并对应真实 tasks 中的对象。
- Train30/Test20 数量为 30/20，无交集，全集与真实 50 个 ID 一致。
- 官方 `base` 包含全部 50 个任务，禁止作为训练选择。
- `configs/splits/official_airline.json` 保留官方 Train/Test 的原始顺序和来源。
- `random.Random(42).shuffle(list(official_train))`：前 24 个为 Train24，后 6 个为 Dev6。
- 算法标识 `python-random.Random(42).shuffle-official-train-order-v1`。
- `configs/splits/train_dev_split.json` 保存 seed、算法、父划分和来源。
- 每次加载都重新核实哈希并重算结果；不仅检查数量，还要求与保存的确切划分一致。
- Train24、Dev6、Test20 两两无交集；Train24 ∪ Dev6 = 官方 Train30。

命令 `python scripts/check_splits.py` 默认只读。显式 `--write` 仅重建两个派生 JSON，
不修改官方数据。固定 seed、官方顺序和算法均属于实验协议，不随实验结果改动。

## 使用边界

| 数据集 | 允许 | 禁止 |
| --- | --- | --- |
| Train24 | Teacher 采集、Verified SFT、GRPO 采集/更新 | 合成新 Task、导入旧轨迹冒充新采集 |
| Dev6 | 验证、Checkpoint 选择、超参数与安全阈值选择 | 进入 Teacher 训练采集、SFT 样本、GRPO 训练 Rollout |
| Test20 | 冻结方案后的正式最终对比 | 用于选模型、调参、示例提示、教师数据或训练奖励优化 |

同 Task 的全部 trial、轨迹片段、重采样和派生样本必须继承相同划分。
Phase 0 只检查官方文件的 ID、数量和版本，没有运行 Test20 对话或性能评估。
正式 Test20 评测的准入见下文「评测准入」。

## 训练记录准入契约

训练 JSONL 每行一个对象，`task_id` 必须是 Train24 中的官方字符串 ID。
来源对象 `source` 必須包含以下字段，值需与 `training_source()` 完全一致：

| 字段 | 值 |
| --- | --- |
| `repository` | `https://github.com/sierra-research/tau2-bench` |
| `commit` | 固定的完整 40 位 Commit |
| `domain` | `airline` |
| `split` | `train24` |
| `task_file` / `task_file_sha256` | 官方 tasks 路径 / 锁文件中的哈希 |
| `split_file` / `split_file_sha256` | 官方 split_tasks 路径 / 锁文件中的哈希 |
| `project_split` | `configs/splits/train_dev_split.json` |
| `split_algorithm` | 上述固定算法标识 |

允许增加模型/trial/seed 等来源字段；不能覆盖必需字段。
Phase 0 不规定或验证 `messages`、reward、SFT mask 等后续载荷格式。

`LeakageChecker.validate_task_ids(ids, stage=...)` 用于采集前的选择校验，
`validate_record` / `validate_jsonl` 用于数据入口。
`stage` 只接受 `teacher`、`sft`、`grpo`，不存在可绕过校验的 `eval` 模式。
缺 ID、非字符串 ID、非法 ID、Dev/Test ID、缺失或错误来源立即拒绝。
JSONL 逐行读取，首条错误给出文件/行号，不能跳过坏行；空文件、空行、非对象、
无效 JSON、重复 JSON key、NaN/Infinity 和非法 UTF-8 也拒绝。

上游原生轨迹通常没有本协议完整来源字段，不能直接送入训练。
Phase 1 适配器必须从真实采集配置填写来源并保留审计关联，而非无条件给旧数据盖章。

## 评测准入

评测**不是**训练入口，因此**不新增 `LeakageChecker` 的 `eval` stage**。上文的
`stage` 依旧只接受 `teacher`/`sft`/`grpo`，也不存在任何能绕过校验的模式：
保留这一限制，才能保证「训练侧永远看不到 Test20 ID」这一不变量在代码里可被检查。

评测需要相反的准入：选择必须**恰好等于**冻结的 Test20。这由独立模块
`airline_data.eval_guard` 负责，与 `LeakageChecker` 无共享 stage：

| 准入器 | 方向 | 判定 |
| --- | --- | --- |
| `LeakageChecker` | 训练 | 任何 Test20/Dev6 ID 一律拒绝 |
| `EvalGuard` | 评测 | 集合必须与官方 Test20 完全相等，多、少、重复、非字符串均拒绝 |

`EvalGuard.validate_task_ids` 只接受 `split="test20"`，出现 Train24/Dev6 ID、
未知 ID、重复 ID 或空集合都会失败。汇总 Test20 结果时同样走该准入器，
因此把一次不完整或越界的运行当作可比基线在结构上不可能发生。

评测本身还有独立于数据层的运行门控：必须显式设置
`AIRLINE_RL_ALLOW_TEST20_EVAL=1`，且 τ² 代码 Commit 必须等于锁文件值。
细节见 [EVALUATION](EVALUATION.md)。

## 污染风险

不能仅相信记录自报 `split=train24`：Task ID 会与实际 Train24 集合交叉核对。
不能按成功/失败结果或轨迹条目重新划分；同 Task 的改写和片段仍可能造成污染。
不能借用参考项目看似相同数量的 30/20 集合。
元数据校验不能检测伪造消息、模型预训练污染或内容中嵌入的其他 Task；后续采集和
转换需绑定原始记录、内容哈希与验证证据。此阶段只提供训练准入的基础防线。
