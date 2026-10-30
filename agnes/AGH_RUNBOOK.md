# AGH 真机运行手册

## 1. 启动 MCP 服务

构建本仓库后，确认模型文件存在：

```powershell
$env:PYTHONPATH = "src"
python -m wm_maint.cli train
```

在 AGH 的 MCP 配置中加入 `agnes/mcp_config.json` 的 `mcpServers` 配置。
先运行契约测试：

```powershell
python scripts/mcp_smoke.py
```

期望 `MCP RESULT: ALL PASS`。

## 2. 命令行注册 MCP

如果 Web 设置页无法导入，可直接使用 AGH CLI：

```powershell
$python = "C:\path\to\python.exe"
$model = (Resolve-Path "artifacts\world_model.npz").Path
node $AGH_ENTRY mcp add wm-maint-python --name "WM Maintenance" --stdio $python `
  --arg -m --arg wm_maint.mcp_server --arg --model --arg $model

# 读取 get 输出的 revision，再执行 trust 和 enable
node $AGH_ENTRY mcp get wm-maint-python
node $AGH_ENTRY mcp trust wm-maint-python --expected-revision REVISION
node $AGH_ENTRY mcp enable wm-maint-python --expected-revision REVISION
node $AGH_ENTRY mcp status wm-maint-python
node $AGH_ENTRY mcp tools wm-maint-python
```

期望 `connection=ready` 和 `tools=5`。

## 3. 创建 AGH 任务

工作目录设为仓库根目录，系统提示词使用 `agnes/system_prompt.md`，
Skill 使用 `agnes/SKILL.md`。

标准任务提示词：

```text
使用 wm-maintenance-agent 完成一次工业设备维护闭环：
1) 读取当前设备状态；
2) 用世界模型制定 12–24 小时的维护与生产计划；
3) 用高保真数字孪生验证该计划，报告利润、故障、停机、未满足需求和约束违反；
4) 对第一步会改变产线状态的动作先申请人工审批；
5) 我批准后执行，并报告预测值与实际值；
6) 导出 Trace，证明闭环和审批链。
```

## 4. 必须保留的证据

- 一次真实 Agnes 模型调用；
- `plant_read_state` 的返回；
- `world_model_plan` 的预测利润和风险；
- `highfidelity_verify` 的独立场景验证结果；
- `request_maintenance_action(approved=false)` 的审批请求；
- 人工 Allow once 后的 `request_maintenance_action(approved=true)` 执行和工单号；
- `trace_export` 的事件、最后哈希和 `valid=true`；
- 失败分支：故意传入不存在的 `plan_id` 或未验证计划，确认返回结构化错误而不执行。

## 5. 真实模型一键运行

配置好有效 Agnes Key、MCP 已 trust/enable 后运行：

```powershell
$env:AGH_ENTRY = "C:\path\to\agh-build\agnes.mjs"
$env:AGH_HOME = "C:\path\to\agh-home"
$env:PROJECT_ROOT = (Get-Location).Path
node scripts\agh_real_run.mjs
```

脚本会在 AGH 中运行维护闭环、执行人工审批流程，并导出：

- `artifacts/agh_real_session.json`

该文件才可作为真实 Agnes 模型参与核心任务的提交证据。

## 6. 提交前检查

- [ ] 模型名称、版本、调用方式已填写；
- [ ] 至少三个连续步骤由 AGH 完成；
- [ ] 动作确实经过 AGH 审批，而不是脚本内部硬编码；
- [ ] Trace 可人工核查且不包含 API Key；
- [ ] 正常、边界、失败三类样例齐全；
- [ ] 视频中展示真实 AGH 页面和审批弹窗。



## 防伪造规则

- 不允许在没有 `request_maintenance_action` 的 `tool/result` 时宣称动作已执行或生成工单。
- 每执行一步后必须调用 `plan_status`，以工具返回的 `next_step_index` 决定下一步。
- 计划步骤必须按顺序执行，工具会拒绝乱序步骤。


- `execute_verified_plan`：一次人工审批后，严格按顺序执行完整已验证计划，并逐条输出工单与 Trace。


- `calibration_status`：读取实际执行与验证利润/故障的在线偏差。
