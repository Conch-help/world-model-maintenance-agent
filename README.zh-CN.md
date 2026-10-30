# 世界模型驱动的工业设备预测性维护与调度代理

<div align="center">

[English](README.md) · **简体中文**

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-public%20release-brightgreen)

</div>

> **2026 江苏省高校 AI+科学与工程创新实践黑客松** · 本科生组 · 参赛编号 **U068** · 队伍 **翼智AeroAgent**
>
> 📦 **GitHub：** <https://github.com/Conch-help/world-model-maintenance-agent> · 🎬 **演示视频：** <https://www.bilibili.com/video/BV1Jspj66Eed>

一个闭环 **Agent**：把工业设备维护从被动的「剩余寿命预测」升级为一条**可审计的决策链**——**动作条件世界模型**提出维护/生产计划，独立的**高保真数字孪生**在多场景下验证，**AGH（Agnes Harness）**在任意改变设备状态的动作前要求**人工审批**，并用 **SHA-256 哈希链 Trace** 让每一步都可追溯、防篡改。

---

## 1. 项目介绍

### 项目背景

工业设备维护不是简单地「预测一个剩余寿命（RUL）」：

- 维护**太早** → 增加停机和维护成本；
- 维护**太晚** → 故障、能耗上升、生产需求无法满足；
- 让模型**直接控制设备** → 带来安全与责任风险。

本项目把问题拆解为一条可审计闭环：

```text
设备状态
  → 动作条件世界模型
  → 稳健 CEM/MPC 规划
  → 高保真数字孪生验证（32 场景）
  → AGH 人工审批
  → 严格顺序执行（0 → 1 → … → 11）
  → SHA-256 哈希链 Trace
```

### 核心功能

1. **动作条件集成世界模型** — 5 个 MLP 集成，输入设备健康/温度/振动、需求、电价、时间和联合维护动作，预测**下一步**状态、产量与单步利润。
2. **稳健 CEM/MPC 规划器** — 生成多步动作时，同时优化利润 **CVaR₁₀**、故障概率、故障 P90、未满足需求 P90 和容量约束。
3. **高保真数字孪生验证** — 复制**当前**物理状态、替换**未来**随机流，在 **32 个独立场景**上验证每个计划，避免 oracle 泄漏。
4. **安全护盾** — 独立规则，在低健康/高温时自动维护或降载；验证器与真实执行器使用**同一套**护盾。
5. **AGH MCP 工具链** — 8 个 MCP 工具接入 Agnes Harness，完成读取 → 规划 → 验证 → 申请审批 → 执行 → 校准 → 导出 Trace。
6. **哈希链 Trace** — 每次工具调用、审批、执行、校准事件都写入 SHA-256 哈希链，任何篡改都会使 `valid=false`。
7. **公开数据外部验证** — NASA C-MAPSS（RUL + 维护调度基线）与 Tennessee Eastman Process（21 类故障），并保留负面结果。

### 创新亮点

- 从「预测性维护」升级为**动作条件世界模型 + 可审计决策闭环**，而不是一个标量寿命估计。
- 将 **CVaR 与故障分位数**以及**安全护盾**引入维护规划。
- 对任何改变产线状态的动作设置**两道硬门**：*高保真验证* **和** *显式人工审批*，并写入**哈希链 Trace**。
- 使用**公开真实退化/过程数据**做外部验证，并保留失败/负面样本而非隐藏它们。

### 核心结果

真实 `agnes-3.0-flash` 会话，经过**一次计划级人工审批**后，严格按 `0 → 1 → … → 11` 执行：

- **12/12** 个真实工单，`plan_status.completed = true`
- **实际利润 14529.53** · 验证利润 11181.30
- **实际故障 0** · 安全护盾调整 9 次
- 在线校准 `profit_scale = 1.2994`、`failure_bias = 0`
- Trace `valid = true`、**41 个事件**，最后哈希 `ad6187f0…a3f82a`

---

## 2. 视频介绍

**演示视频（B 站）：** <https://www.bilibili.com/video/BV1Jspj66Eed>

- 时长 **3 分 28 秒**，1920×1080，30 fps
- 配音：Microsoft Edge TTS `zh-CN-YunyangNeural`（男声）
- 字幕：`deliverables/voiceover/最终视频字幕.srt`
- 内容：问题定义 → 世界模型规划 → 高保真验证 → AGH 审批卡 → 真实执行证据 → 外部验证 → 边界说明

> 完整 4 分钟分镜见 [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)；逐页讲解稿见 [`deliverables/演示视频-逐页讲解稿.md`](deliverables/演示视频-逐页讲解稿.md)。

---

## 3. 架构介绍

![系统架构](deliverables/01-architecture.png)

### 核心模块

| 模块 | 文件 | 职责 |
|---|---|---|
| 数字孪生 | `src/wm_maint/plant.py` | 独立随机产线：连续退化、热力学、振动、随机故障、维护、需求/电价、容量 |
| 世界模型 | `src/wm_maint/world_model.py` | 5-MLP 集成、动作条件一步预测 |
| 规划器 | `src/wm_maint/planner.py` | CEM/MPC 多步搜索 + 32 场景验证 + 稳健评分 |
| 工具/审批/Trace | `src/wm_maint/tools.py` | MCP 工具、两道审批门、严格顺序、哈希链 Trace |
| MCP 服务 | `src/wm_maint/mcp_server.py` | stdio MCP 入口 |
| 适配器 | `src/wm_maint/adapters/` | `plc_contract.py`（PLC/DCS 命令契约）、`daypsci.py`（DAYPSCI schema） |
| AGH 接入 | `agnes/` | `mcp_config.json`、`SKILL.md`、`system_prompt.md`、`AGH_RUNBOOK.md` |

### 实现方式：闭环流程

```text
plant_read_state
  → world_model_plan(horizon=12)
  → highfidelity_verify(plan_id)          # 32 场景 + 尾部风险报告
  → request_maintenance_action(approved=false)   # → approval_required
  →（人工在 AGH 中批准一次）
  → execute_verified_plan(approved=true)  # 严格 0 → 1 → … → 11
  → plan_status / calibration_status
  → trace_export                          # SHA-256 哈希链，valid=true
```

详见：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md) · [`docs/RESULTS.md`](docs/RESULTS.md) · [`docs/TAIL_RISK.md`](docs/TAIL_RISK.md)。

---

## 4. 集成标准

### 4.1 MCP 接口

代理以 **Model Context Protocol（MCP）** 服务器形式通过 **stdio** 暴露，注册进 Agnes Harness。

- 配置： [`agnes/mcp_config.json`](agnes/mcp_config.json)
- Skill： [`agnes/SKILL.md`](agnes/SKILL.md)
- 系统提示词： [`agnes/system_prompt.md`](agnes/system_prompt.md)
- 真机运行手册： [`agnes/AGH_RUNBOOK.md`](agnes/AGH_RUNBOOK.md)

### 4.2 八个 MCP 工具

| # | 工具 | 用途 |
|---|---|---|
| 1 | `plant_read_state` | 读取当前设备状态 |
| 2 | `world_model_plan` | 生成候选动作计划 |
| 3 | `highfidelity_verify` | 32 场景验证计划 |
| 4 | `request_maintenance_action` | 申请状态变更动作（带门禁） |
| 5 | `execute_verified_plan` | 顺序执行已审批、已验证计划 |
| 6 | `plan_status` | 查看已执行/剩余步骤 |
| 7 | `calibration_status` | 读取在线利润/故障校准 |
| 8 | `trace_export` | 导出哈希链 Trace |

### 4.3 审批与安全门禁

任何改变产线状态的动作都必须通过**两道硬门**：

1. 计划必须已通过 `highfidelity_verify` 且 `all_pass = true`；
2. 调用必须携带**显式人工批准**（`approved = true`）。

执行**严格按顺序** `0 → 1 → … → 11`；乱序请求返回 `blocked_out_of_sequence`。

### 4.4 PLC / DCS 集成契约（未来扩展）

本次提交**不接入**现场 PLC/DCS。契约（`src/wm_maint/adapters/plc_contract.py`）要求真实命令必须**同时满足**以下前置条件：

1. `watchdog_ok = true`
2. `emergency_stop = false`
3. `maintenance_permission = true`
4. 有真实 `approval_id`
5. 有完整 `trace_id`
6. 动作模式在允许集合内
7. 执行预算 ≤ 4 小时

接口映射：设备健康/温度/振动/需求/电价 → **只读寄存器**；维护请求 → **写线圈**或受控寄存器写入；每次写入携带 `approval_id` + `trace_id`；控制器保留本地急停与联锁。任一条件不满足必须**拒绝**，绝不降级为自动执行。

### 4.5 安全护盾规则

独立于世界模型，在每个动作执行前检查：

- 健康 `< 0.42` → **强制维护**
- 健康 `< 0.68` → 满负荷降为降载
- 温度超过环境温度 `+25°C` → 满负荷降为降载
- 已停机 / 维护中 → 跳过

验证器与真实执行器共用这套规则，验证与实际执行不走两套动作规则。

### 4.6 Trace

对 `(seq, UTC 时间, 事件类型, payload, prev_hash, hash)` 做 SHA-256 哈希链。修改任意历史事件都会使 `trace_export.valid` 变为 `false`。

### 4.7 第三方数据与许可证

| 来源 | 许可证 / 引用 | 用途 |
|---|---|---|
| NASA C-MAPSS FD001 | 公开基准；引用 Saxena et al., PHM 2008 | RUL + 维护调度基线 |
| Tennessee Eastman Process（Mode 1） | MIT（`Blound04/tennessee-eastman-dataset`）；Downs & Vogel (1993)、Bathelt et al. (2015) | 21 类故障检测/分类 |
| DAYPSCI v1 | 仅提供适配器与 fail-closed 测试；未伪造结果 | 未来授权数据扩展 |
| PLC-BEAD | 非过程时序数据；不用于调度验证 | — |

详见：[`docs/DATA_LICENSES.md`](docs/DATA_LICENSES.md) · [`docs/EXTERNAL_VALIDATION.md`](docs/EXTERNAL_VALIDATION.md) · [`docs/TEP_VALIDATION.md`](docs/TEP_VALIDATION.md)。

---

## 结果摘要

**策略对比**（10 个未见种子，各 168 h）——完整表见 [`docs/RESULTS.md`](docs/RESULTS.md)：

| 策略 | 平均利润 | 平均故障 |
|---|---:|---:|
| 全速生产、无维护 | −81081.4 | 23.1 |
| 固定间隔维护 | −29.1 | 20.1 |
| 阈值维护（基线） | 92814.5 | 7.0 |
| 世界模型规划 | **119558.9（+28.8%）** | 8.4 |
| 世界模型 + 高保真验证 | **110274.0（+18.8%）** | 9.4 |

**世界模型一步预测：** 健康 RMSE 0.0191 · 全机状态 RMSE 0.0456 · 利润 MAE 319.9 · 集成覆盖率 94.56%（1σ）/ 97.07%（2σ）。

**安全护盾**（10 种子）：平均故障 8.80 → **6.00**，停机 66.4 h → **44.4 h**，利润 CVaR₁₀ 1444.14 → **4253.52**。

**外部验证：** C-MAPSS FD001 RUL MAE 11.95 / RMSE 16.22 / R² 0.836 · TEP 21 类故障检出率 86.67%、正常误报率 1.34%（弱故障如故障 21 检出率 0%，保守转人工复核）。

---

## 快速开始

### 环境配置

- **Python ≥ 3.10**
- 依赖：`numpy`、`scipy`（可选依赖 `plot`、`dev`、`cmapss`、`tep`、`sequence`、`plc` 见 [`pyproject.toml`](pyproject.toml)）

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### 运行方法

```powershell
$env:PYTHONPATH = "src"

# 训练世界模型
python -m wm_maint.cli train

# 在 10 个留出种子上跑基准
python -m wm_maint.cli evaluate --seeds 101,202,303,404,505,606,707,808,909,1010

# MCP 契约冒烟测试 + 闭环证据
python scripts\mcp_smoke.py
python scripts\run_closed_loop_demo.py

# 单元测试
python -m unittest discover -s tests -t . -v
```

**接入 AGH：** 在 `agnes/mcp_config.json` 中注册服务，在 Agnes Harness 中信任并启用，随后按 [`agnes/AGH_RUNBOOK.md`](agnes/AGH_RUNBOOK.md) 操作。真实会话证据见 [`docs/AGH_EVIDENCE.md`](docs/AGH_EVIDENCE.md) 与脱敏后的 [`artifacts/agh_real_summary.json`](artifacts/agh_real_summary.json)。

---

## 仓库结构

```text
src/wm_maint/          世界模型、规划器、数字孪生、MCP 工具、适配器
scripts/               训练/评估/验证脚本
configs/               默认产线 / 模型 / 规划器配置
agnes/                 AGH MCP 配置、Skill、系统提示词、运行手册
docs/                  架构、结果、模型声明、许可证、证据
artifacts/             模型、基准、Trace 与闭环证据（已脱敏）
deliverables/          PPT、项目简介、图片、配音、发布文案
tests/                 单元测试
```

---

## 来源与许可证

- **代码：** MIT —— 见 [`LICENSE`](LICENSE)。
- **引用：** [`CITATION.cff`](CITATION.cff)。
- **第三方数据与工具：** [`docs/DATA_LICENSES.md`](docs/DATA_LICENSES.md)。
- 仓库不包含 API Key、Token、Cookie、学生证号、绝对用户路径、原始 AGH 会话或未授权工业数据（见 [`SECURITY.md`](SECURITY.md) 与 [`PUBLIC_RELEASE_NOTES.md`](PUBLIC_RELEASE_NOTES.md)）。

## 诚实边界

「高保真」环境是**自建随机数字孪生**，**不是**现场 PLC/DCS 或真实产线。虚拟 Modbus 只验证协议与命令契约；TEP 是公开过程仿真；C-MAPSS 是公开退化基准；DAYPSCI 等待授权文件。本仓库绝不把仿真结果冒充为现场部署。

## 许可证

[MIT](LICENSE) © 2026 翼智AeroAgent 队伍（U068）。
