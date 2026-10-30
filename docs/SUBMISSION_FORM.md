# 作品提交表单草稿

> 本文件用于提交前回填。公开内容和代码仓库已完成；仅保留视频和签名为待填项。

## A. 基本信息

| 字段 | 内容 |
|---|---|
| 项目名称 | 世界模型驱动的工业设备预测性维护与调度代理 |
| 参考方向 | AI 驱动科学发现 / 工程仿真与优化 / 智能制造与系统 |
| 项目摘要 | 使用动作条件世界模型生成维护与生产计划，在独立高保真数字孪生中多场景验证，再经 AGH 人工审批顺序执行，并输出哈希链 Trace。 |
| 问题来源 | 工业维护存在过维护、故障停机和模型擅自下发关键动作三重风险。 |
| 目标 | 在未知未来场景中降低维护成本、停机时间和需求损失，同时保证关键动作可验证、可审批、可追溯。 |

## B. 技术信息

| 字段 | 内容 |
|---|---|
| AGH 作用 | 任务规划、工具编排、验证反馈、人工审批、顺序执行、Trace 导出 |
| 世界模型 | Action-Conditioned Ensemble World Model，5 个 NumPy MLP 集成 |
| 高保真验证 | 独立随机数字孪生，复制当前状态并使用独立未来随机流，32 场景验证 |
| 规划器 | 稳健 CEM/MPC，动作包括 full/derate/off/maintenance |
| 数据 | 自建数字孪生；NASA C-MAPSS FD001；Tennessee Eastman Mode 1 |
| 外部边界 | TEP 是公开过程仿真；DAYPSCI 不在本次范围；虚拟 Modbus 不代表现场 PLC |
| API / 设备接口 | MCP stdio；PLC 命令契约；虚拟 Modbus TCP 回环 |
| Agnes 模型名称 | `agnes-3.0-flash` |
| 模型使用环节 | 任务规划、工具选择、验证反馈、审批请求、结果汇总 |
| 模型调用方式 | AGH 内置 Provider + MCP stdio |
| MCP 工具 | plant_read_state、world_model_plan、highfidelity_verify、request_maintenance_action、execute_verified_plan、plan_status、calibration_status、trace_export |

## B2. 全部模型披露

| 模型/组件 | 名称与版本 | 提供方 | 使用环节 | 调用方式 |
|---|---|---|---|---|
| AGH 核心模型 | `agnes-3.0-flash`，版本以 AGH Provider 目录为准 | Agnes / 赛事组委会提供 Key | 任务规划、工具选择、验证反馈、审批请求、结果汇总 | AGH 内置 Provider + MCP stdio |
| 自研世界模型 | Action-Conditioned Ensemble World Model v0.1.0，5 个 MLP 集成 | 翼智AeroAgent（本队） | 预测设备状态、产量和单步利润 | 本地 Python/NumPy，经 MCP 工具调用 |
| 自研规划器 | Robust CEM/MPC v0.1.0 | 翼智AeroAgent（本队） | 生成维护与生产候选计划 | 本地 Python |
| 自研数字孪生 | Reference Production Plant v0.1.0 | 翼智AeroAgent（本队） | 32 场景高保真验证 | 本地 Python |
| 外部验证基线 | HistGradientBoosting、RandomForest、Ridge；版本以 `pyproject.toml` 依赖为准 | scikit-learn 开源项目 | C-MAPSS RUL、TEP 故障分类对照 | Python/scikit-learn |
| 序列对照模型 | LSTM；版本以运行环境为准 | PyTorch 开源项目 | 序列世界模型对照，未进入生产模型 | Python/PyTorch |
| 视频配音 | Edge TTS `zh-CN-YunyangNeural` | Microsoft | 演示视频中文配音 | 本地 `edge-tts` CLI 调用 Microsoft Edge 在线语音 |

说明：Agnes 模型 Key 仅保存在本地环境或 `.env`，未写入公开仓库、视频、截图或提交包。C-MAPSS 与 TEP 是公开数据基准，不是商业模型。


## C. 可运行作品

| 字段 | 内容 |
|---|---|
| 代码仓库 | https://gitee.com/ZzX729183/world-model-maintenance-agent |
| 在线体验地址 | 〔可选〕 |
| 安装与复现 | 见 `README.md`、`docs/RESULTS.md` |
| 提交 ZIP 命名 | 本科生组-U068-翼智AeroAgent-张子轩.zip |

## D. 演示视频

| 字段 | 内容 |
|---|---|
| 主链接（3–5 分钟） | https://www.bilibili.com/video/BV1Jspj66Eed |
| 备用链接 | 〔可选〕 |
| 视频脚本 | `docs/DEMO_SCRIPT.md` |

## E. 运行证据

| 要求 | 对应文件 |
|---|---|
| AGH 执行记录 | `artifacts/agh_real_summary.json`、`artifacts/agh_real_session_sanitized.json` |
| ≥1 条工具调用链 | `plant_read_state → world_model_plan → highfidelity_verify → execute_verified_plan → plan_status → calibration_status → trace_export` |
| Agnes 模型参与证据 | 真实 `agnes-3.0-flash` 会话 `b1761ca3-274d-42dc-9f79-21a19ee00b6c` |
| 关键配置 | `configs/default.json`、`agnes/mcp_config.json` |
| 专业验证结果 | `docs/RESULTS.md`、`docs/EXTERNAL_VALIDATION.md` |
| 测试样例 | `tests/`、`scripts/mcp_smoke.py`、`artifacts/closed_loop_report.json` |

## F. 测试样例

- 正常：默认未知种子下完成世界模型规划与 32 场景高保真验证；
- 边界：未验证或未批准计划调用 `request_maintenance_action` / `execute_verified_plan`，必须返回 `approval_required` 或 `blocked`；
- 失败：损坏 Trace、缺少 DAYPSCI 标签、急停或缺少 watchdog 时 fail closed；
- 审批：批准且验证通过后严格按 `0→1→…→11` 执行并返回真实工单。

## G. 最终验证结果

- 12/12 步真实工单；
- `plan_status.completed=true`；
- 实际利润 14529.53；
- 实际故障 0；
- 验证利润 11181.30；
- 安全护盾调整 9 次；
- `profit_scale=1.2994`、`failure_bias=0`；
- Trace `valid=true`、41 个事件；
- C-MAPSS 调度：预测 RUL ≤35 的平均成本 778.74，低于不维护的 913.17；
- TEP：平均故障检出率 86.67%，正常误报率 1.34%，故障类型宏 F1 0.700。

## H. 成员分工与独立完成声明

〔按 `成员分工与独立完成声明.md` 填写并签名〕

## I. 公开内容

| 平台 | 链接 | 截图 | 发布日期 |
|---|---|---|---|
| Gitee | https://gitee.com/ZzX729183/world-model-maintenance-agent/releases/tag/v0.1.0 | 公开内容-Gitee发行版截图.png | 2026-10-09 |
