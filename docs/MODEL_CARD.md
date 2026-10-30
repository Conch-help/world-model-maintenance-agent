# 模型声明 / Model Card

## 世界模型

| 字段 | 内容 |
|---|---|
| 模型名称 | Action-Conditioned Ensemble World Model |
| 版本 | wm-maint/0.1.0 |
| 结构 | 28560 条训练转移上的 5 个 MLP 集成 |
| 输入 | 设备健康/温度/振动/停机状态、需求、电价、时间、联合维护动作 |
| 输出 | 下一步设备状态、产量和单步利润 |
| 不确定性 | 集成模型预测标准差 |
| 验证 | 未见种子单步误差、集成覆盖率、独立高保真多场景回放 |
| 用途 | 生成维护/生产候选动作，不直接替代高保真验证和生产许可 |

## 高保真数字孪生

| 字段 | 内容 |
|---|---|
| 名称 | Reference Production Plant |
| 动力学 | 连续退化、热力学、振动、随机故障、维护停机 |
| 决策周期 | 1 h |
| 验证方式 | 相同当前状态、独立未来随机流、多场景平均 |
| 用途 | 验证世界模型计划的利润、故障、停机、未满足需求和容量约束 |

## Agnes / AGH

| 字段 | 内容 |
|---|---|
| 模型 | `agnes-3.0-flash` |
| 使用环节 | 任务规划、工具选择、验证反馈、审批请求、结果汇总 |
| 调用方式 | AGH 内置 provider + MCP stdio |
| 工具 | plant_read_state、world_model_plan、highfidelity_verify、request_maintenance_action、execute_verified_plan、plan_status、calibration_status、trace_export |

## 数据与局限

本项目使用自建独立数字孪生生成训练数据。它不是真实产线数据；本次提交不进行现场数据验证；现场数据仅作为未来扩展。
