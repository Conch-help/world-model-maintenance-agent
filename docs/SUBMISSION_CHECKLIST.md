# 提交前硬性检查清单

## 代码与证据

- [x] 世界模型训练脚本与模型文件
- [x] 独立高保真数字孪生
- [x] CEM/MPC 规划器
- [x] MCP stdio 服务，8 个工具
- [x] 12/12 单元测试通过
- [x] MCP 冒烟测试通过
- [x] 本地闭环审批/执行/Trace 证据
- [x] AGH 真实进程调用工具链证据
- [x] AGH 真实 `agnes-3.0-flash` 会话
- [x] AGH 真实会话中的人工审批与 0→11 顺序执行
- [x] Trace `valid=true`、41 个事件
- [x] C-MAPSS RUL 与维护调度外部对照
- [x] TEP 21 类故障外部异常检测与分类
- [x] 虚拟 Modbus TCP 回环与 PLC 命令契约测试
- [x] 序列 LSTM 对照实验，保留“未优于生产模型”的负面结果

## 官网必填

- [ ] 作品提交表单所有字段
- [x] Agnes 模型名称、使用环节和调用方式：`agnes-3.0-flash`、AGH 内置 Provider + MCP stdio
- [x] 代码仓库/可运行链接：https://gitee.com/ZzX729183/world-model-maintenance-agent
- [x] 3–5 分钟视频主链接和访问码：https://www.bilibili.com/video/BV1Jspj66Eed
- [x] 公开内容已完成：Gitee 发行版 v0.1.0；链接：https://gitee.com/ZzX729183/world-model-maintenance-agent/releases/tag/v0.1.0；截图：公开内容-Gitee发行版截图.png；日期：2026-10-09
- [x] 正常/边界/失败三类测试样例
- [x] 成员分工与独立完成声明草稿
- [x] ZIP 命名符合 `组别-参赛编号-队伍名称-队长姓名`
- [x] 提交包不包含 API Key、Token 或临时缓存（脚本检查）

## 提交展示

- [ ] 视频实际展示 AGH 页面、人工审批和 Trace
- [ ] 视频展示 12 个工单、`completed=true`、`valid=true`
- [ ] 视频展示 0 故障护盾会话，并说明历史 1 次故障仍被保留
- [ ] 视频中不出现 Key、邮箱、手机号、学号或绝对用户路径
