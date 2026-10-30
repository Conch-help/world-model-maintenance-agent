# 架构说明

## 1. 世界模型

`EnsembleWorldModel` 接收当前设备状态、时间和联合动作，预测下一步：

- 每台设备的健康、温度、振动、剩余停机和维护剩余时间；
- 总产量和单步利润。

模型由 5 个 NumPy MLP 组成。集成标准差提供预测不确定性。训练数据只来自独立数字孪生，测试使用未见随机种子。

## 2. 规划器

`CEMPlanner` 使用交叉熵方法搜索多步联合动作：

- 动作包括 full、derate、off、maintenance；
- 目标是最大化预测利润，同时惩罚健康风险、集成不确定性和容量不足；
- 规划频率为每 6 小时一次，每次预测未来 24 小时。

## 3. 高保真验证

`Reference Production Plant` 是独立随机数字孪生，包含：

- 连续退化和热力学；
- 振动和随机故障；
- 预防性维护、紧急修复和停机；
- 需求、电价、产能和未满足需求。

验证时复制当前物理状态，但替换未来随机流，并在 3 个独立场景取平均。它不能使用正式回合的私有未来随机数，避免 oracle leakage。

## 4. AGH 与审批

MCP 工具链由 AGH 调用：

```text
plant_read_state
  -> world_model_plan
  -> highfidelity_verify
  -> request_maintenance_action(approved=false)
  -> human approval
  -> request_maintenance_action(approved=true)
  -> trace_export
```

`request_maintenance_action` 有两道门：

1. 计划必须经过 `highfidelity_verify` 且 `all_pass=true`；
2. 必须显式传入人工批准的 `approved=true`。

## 5. Trace

Trace 使用 SHA-256 哈希链。每个事件包含：

- `seq`、UTC 时间、事件类型、结构化 payload；
- `prev_hash` 和 `hash`。

对任何历史事件或 payload 的修改都会使 `trace_export.valid=false`。


## 6. 顺序与防伪

`plan_status` 返回已执行步骤、剩余步骤和下一步骤。`request_maintenance_action` 强制按 0→1→…→11 顺序执行，乱序请求返回 `blocked_out_of_sequence`，模型不得在缺少工具返回时宣称已生成工单。


- `execute_verified_plan`：一次人工审批后，严格按顺序执行完整已验证计划，并逐条输出工单与 Trace。


## 7. 风险感知规划

候选计划不再只按平均利润排序，而是按 `RobustScore = CVaR10 - 3000×P90故障 - 80×P90未满足需求 - 900×最大容量违反` 选择。10 种子对比中，故障 P90 从 2.67 降至 2.26，CVaR10 从 -2041 提升至 +2802。


- `calibration_status`：读取实际执行与验证利润/故障的在线偏差。
