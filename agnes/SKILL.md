# World-Model Maintenance Agent

## Purpose

Use the `wm-maintenance-agent` MCP tools to plan, verify and execute industrial
maintenance actions under human approval.

## Mandatory workflow

1. `plant_read_state` — read current health, temperature, demand and energy price.
2. `world_model_plan` — plan with the action-conditioned ensemble world model.
3. `highfidelity_verify` — validate the candidate plan across independent
   digital-twin scenarios. Never execute a plan that has not passed verification.
4. `request_maintenance_action` with `approved=false` — request human approval.
5. After an explicit human approval, call `request_maintenance_action` with
   `approved=true`.
6. `trace_export` — return the hash-chained trace.

## Hard constraints

- Do not invent sensor values or predicted profits.
- Never treat the world-model prediction as high-fidelity truth.
- Any action that changes plant state must pass both high-fidelity verification
  and human approval.
- If verification fails or is uncertain, recommend manual review instead of execution.
- State-changing actions include `maintenance`, `derate` and `off`.


## 防伪造规则

- 不允许在没有 `request_maintenance_action` 的 `tool/result` 时宣称动作已执行或生成工单。
- 每执行一步后必须调用 `plan_status`，以工具返回的 `next_step_index` 决定下一步。
- 计划步骤必须按顺序执行，工具会拒绝乱序步骤。


- `execute_verified_plan`：一次人工审批后，严格按顺序执行完整已验证计划，并逐条输出工单与 Trace。


- `calibration_status`：读取实际执行与验证利润/故障的在线偏差。
