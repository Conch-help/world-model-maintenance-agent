# 世界模型驱动的工业设备维护 Agent：从预测到审批

> 2026 江苏省高校 AI+科学与工程创新实践黑客松｜本科生组 U068｜翼智AeroAgent

![公开封面](https://raw.githubusercontent.com/Conch-help/world-model-maintenance-agent/main/deliverables/04-public-cover.png)

## 问题

工业设备维护不是简单地预测一个剩余寿命：

- 维护太早，会增加停机和维护成本；
- 维护太晚，会增加故障、能耗和未满足需求；
- 关键动作如果由模型直接下发，又会带来安全和责任风险。

本项目把问题拆成一条可审计闭环：

```text
设备状态
 → 动作条件世界模型
 → 稳健 CEM/MPC 规划
 → 32 场景高保真验证
 → AGH 人工审批
 → 严格顺序执行
 → 哈希链 Trace
```

## 真实 AGH 执行结果

真实 `agnes-3.0-flash` 会话经过计划级人工审批后，严格执行 `0→1→…→11`：

- 12/12 个真实工单；
- 实际利润 14529.53；
- 实际故障 0；
- 验证利润 11181.30；
- 安全护盾调整 9 次；
- `plan_status.completed=true`；
- `trace_export.valid=true`，41 个事件。

历史未加护盾会话曾出现 1 次故障，该负面结果被完整保留，用于说明尾部风险、安全护盾和人工审批的必要性。

![最终结果](https://raw.githubusercontent.com/Conch-help/world-model-maintenance-agent/main/deliverables/02-final-results.png)

## 技术方案

1. 动作条件世界模型：5 个 MLP 集成，预测下一步状态、产量和利润；
2. 稳健规划：同时考虑 CVaR10、故障概率、故障 P90、未满足需求和容量约束；
3. 高保真验证：复制当前状态，替换未来随机流，使用 32 个独立场景；
4. 安全护盾：低健康或高温时自动维护或降载；
5. AGH 闭环：8 个 MCP 工具，完成读取、规划、验证、审批、顺序执行、校准和 Trace。

![系统架构](https://raw.githubusercontent.com/Conch-help/world-model-maintenance-agent/main/deliverables/01-architecture.png)

## 外部验证

### NASA C-MAPSS FD001

- RUL 预测：MAE 11.95、RMSE 16.22、R² 0.836；
- 调度对照：预测 RUL ≤35 的平均成本 778.74，低于不维护的 913.17；
- Oracle RUL ≤20 为 325.84，作为参考上限。

### Tennessee Eastman Process

- 21 类故障平均检出率 86.67%；
- 正常误报率 1.34%；
- 监督故障类型宏 F1 0.700；
- 故障 5 检出率 40%、故障 21 检出率 0%，弱故障结果被保留。

![外部验证](https://raw.githubusercontent.com/Conch-help/world-model-maintenance-agent/main/deliverables/03-benchmarks.png)

## 诚实边界

主环境是独立随机数字孪生，不是现场 PLC/DCS；虚拟 Modbus 只验证协议和命令契约；TEP 是公开过程仿真；本项目本次不进行现场工业授权数据验证。

## 演示视频

https://www.bilibili.com/video/BV1Jspj66Eed

## 代码仓库

https://github.com/Conch-help/world-model-maintenance-agent

## 标签

#世界模型 #工业智能 #预测性维护 #AI Agent #AGH #MCP #数字孪生
