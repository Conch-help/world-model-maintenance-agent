# AGH 执行证据说明

## 已完成的真实 AGH 集成验证

本地已使用 AGH 源码构建出的 `agnes.mjs` 启动 daemon，并把本项目的
`wm-maintenance-agent` MCP 服务注册、信任、启用。AGH 的工具目录中可见：

- `plant_read_state`
- `world_model_plan`
- `highfidelity_verify`
- `request_maintenance_action`
- `trace_export`

导出证据：`artifacts/agh_toolchain_session.json`

该会话中 AGH 连续调用了：

```text
plant_read_state
 -> world_model_plan(horizon=12)
 -> highfidelity_verify(plan_id=PLAN-20261008-0)
 -> trace_export
```

最新连续链为 4 次工具调用；导出文件中累计 9 次工具调用，工具返回错误数为 0。这个证据证明：

- MCP 服务可以被真实 AGH 进程发现和调用；
- AGH 能读取工具返回的结构化状态；
- 多步骤工具链在 AGH 会话中连续成立；
- 导出记录可供人工核查。

## 重要限制

当前 `agh_toolchain_session.json` 使用**本地确定性模型夹具**驱动 AGH 工具链，
不是 Agnes 自研模型的真实推理，只作为 MCP 集成回归测试。真实 `agnes-3.0-flash` 会话已经完成，见下方“最终安全护盾会话”；该夹具不再作为正式模型证据。以下步骤保留为复现清单：

1. 在 AGH Web 或 CLI 的 Provider 设置中录入有效的 Agnes API Key；
2. 选择 `agnes-3.0-flash` 或赛事目录中实际可用的 Agnes 模型；
3. 使用 `agnes/AGH_RUNBOOK.md` 的标准任务提示词重新运行；
4. 用 `agh export <sessionId> --raw` 覆盖或另存真实会话记录；
5. 在模型中确认真实工具调用序列包含 `request_maintenance_action` 的人工审批。

不要删除本地夹具会话；它用于证明集成层，而真实 Agnes 会话用于证明模型层。


## 历史真实 Agnes 会话（部分执行）

真实会话 `b1761ca3-274d-42dc-9f79-21a19ee00b6c` 使用 `agnes-3.0-flash` 完成：

- `plant_read_state`
- `world_model_plan`
- `highfidelity_verify`
- 8 次 `request_maintenance_action` 审批与执行
- `trace_export`

真实执行工单：

| step | ticket | modes | profit | failures |
|---:|---|---|---:|---:|
| 0 | MNT-6359E602 | [1,2,1] | 1249.18 | 0 |
| 2 | MNT-AEB0530A | [3,2,2] | 818.99 | 0 |
| 4 | MNT-CC190454 | [1,1,1] | 432.09 | 0 |
| 5 | MNT-331AE838 | [2,2,2] | 1164.39 | 0 |
| 6 | MNT-BDB95CDC | [2,2,1] | 1563.74 | 0 |
| 8 | MNT-CADBC329 | [2,2,1] | 1638.42 | 0 |
| 9 | MNT-F612A7B8 | [2,2,1] | -3363.84 | 1 |
| 11 | MNT-5DDF7B42 | [2,1,2] | 1153.72 | 0 |

Trace 校验：`valid=true`、`n_events=32`、`last_hash=21604f828e1203e73ed3a084197f2fad30f54e6f8b798702c997db737c6784a4`。

注意事项：

- 该会话执行了 8 个动作，实际 `hour=8`，没有严格执行完整的 12 步序列；
- step9 的实际故障数为 1，而验证多场景平均故障数为 0，属于随机尾事件；
- 先前自然语言生成的 `MNT-8C42F1A7` 无工具返回，已作废。


## 最终干净会话：0→1→…→11

AGH 使用 `agnes-3.0-flash` 重新执行最终干净计划，并通过 `execute_verified_plan(approved=true)` 在**一次计划级人工审批**后严格顺序执行 12 步。

`plan_status`：

```text
executed_steps = [0,1,2,3,4,5,6,7,8,9,10,11]
remaining_steps = []
next_step_index = null
completed = true
```

12 个真实工单：

| step | ticket | modes | profit | failures |
|---:|---|---|---:|---:|
| 0 | MNT-6359E602 | [1,2,1] | 1249.18 | 0 |
| 1 | MNT-4B5184AC | [1,2,1] | 1319.93 | 0 |
| 2 | MNT-AEB0530A | [3,2,2] | 782.47 | 0 |
| 3 | MNT-0D80758A | [2,2,2] | 1164.20 | 0 |
| 4 | MNT-CC190454 | [1,1,1] | 356.98 | 0 |
| 5 | MNT-331AE838 | [2,2,2] | 1637.60 | 0 |
| 6 | MNT-BDB95CDC | [2,2,1] | -3363.64 | 1 |
| 7 | MNT-3DBB69F9 | [2,2,2] | 1153.88 | 0 |
| 8 | MNT-CADBC329 | [2,2,1] | 782.01 | 0 |
| 9 | MNT-F612A7B8 | [2,2,1] | 778.77 | 0 |
| 10 | MNT-B2E26833 | [2,2,2] | 1143.61 | 0 |
| 11 | MNT-5DDF7B42 | [2,1,2] | 1158.57 | 0 |

汇总：

- `total_profit = 8163.56`
- `total_failures = 1`
- `final_hour = 12`
- `trace_export.valid = true`
- `n_events = 40`
- `last_hash = 616962db076de208115fe46a630fc60bdec40eff5e20badea8b9f5433de7ea86`

高保真验证预测 0 故障，实际在 step6 发生 1 次尾部故障。该差异已保留，不用平均值掩盖单次随机结果。


## 验证器升级说明

早期真实会话使用较少的验证场景，曾记录 `verified_failures=0`。新版验证器已升级为 32 场景，并报告故障概率、P90/P95、CVaR 和最大故障数；最终 12 步计划的故障概率为 46.88%，故障 P90/P95 为 1/1.45。历史会话不回改，但最终提交应以新版尾部风险报告为准。


新版 32 场景验证器同时报告：failure_probability=0.4688、failures_p90=1、failures_p95=1.45、failures_max=2、profit_cvar10=1205.82。step6 实际 1 次故障位于该预测分布内。


## 最终安全护盾会话

新版优化后的真实 AGH 会话：

- 模型：`agnes-3.0-flash`
- 12/12 步完整执行
- 实际利润：14529.53
- 实际故障：0
- 验证利润：11181.30
- 实际/验证利润比：1.2994
- 安全护盾调整：9 次
- `plan_status.completed=true`
- `trace_export.valid=true`
- Trace 事件数：41
- 最后哈希：`ad6187f058caa7a36d3fbb6bcfc27fb3ea6449048663465f387ebedb55a3f82a`
- 新增 `calibration/outcome` 事件，记录利润缩放、故障偏差和护盾调整。
