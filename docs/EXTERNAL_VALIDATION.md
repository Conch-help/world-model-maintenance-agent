# 外部验证：NASA C-MAPSS FD001

## 数据来源

- 数据集：NASA C-MAPSS Turbofan Engine Degradation Simulation Data Set，FD001；
- 原始来源：NASA Prognostics Center of Excellence (PCoE)；
- 引用：Saxena, A., Goebel, K., Simon, D., & Eklund, N. (2008). Damage propagation modeling for aircraft engine run-to-failure simulation. PHM 2008；
- 许可证与再分发：使用前应核对 NASA/原始数据集的当前条款；本项目只保留公开访问说明、校验脚本和结果，不把原始数据作为私有数据分发。

## 验证任务

使用 30 个时间步窗口，提取每个窗口的均值、标准差和最后一步传感器特征，预测剩余寿命（RUL）。训练使用官方 development/validation 划分，测试使用 100 条官方 test 运行。

## 结果

| 模型 | MAE | RMSE | R² | 误差 ≤10 周期 | 误差 ≤20 周期 |
|---|---:|---:|---:|---:|---:|
| 均值基线 | 35.02 | 40.66 | -0.030 | 14% | 28% |
| Ridge | 14.62 | 17.71 | 0.805 | 40% | 73% |
| Random Forest | 12.93 | 17.53 | 0.809 | 52% | 75% |
| HistGradientBoosting | **11.95** | **16.22** | **0.836** | **54%** | **76%** |

原始结果：`artifacts/cmapss_validation.json`

## 结论与边界

- 公开数据验证说明：从传感器窗口恢复退化/RUL 信号是可行的，不是随机噪声；
- 它验证的是健康/RUL 信号，不是当前三设备产线调度经济性和动作转移；
- 不得把 C-MAPSS 结果写成“真实产线部署验证”；
- 当前数字孪生仍是动作条件规划和 AGH 闭环的主验证环境。

## 合规命令

```powershell
$env:PYTHONPATH = "src"
python scripts\validate_cmapss.py --data-root "<公开数据根目录>" --out "artifacts\cmapss_validation.json"
```

数据在本地下载，不提交原始数据文件；提交包只包含来源说明、引用和验证结果。


## Tennessee Eastman Process

- 数据源：Blound04/tennessee-eastman-dataset（MIT）；
- 模式 1，21 类故障；
- 无监督异常检测：平均故障检出率 86.67%，正常误报率 1.34%；
- 监督故障类型：留出批次准确率 68.60%，宏 F1 0.700；
- 监督二分类误报率过高，不采用；异常门使用无监督阈值，分类使用监督模型；
- 详细报告：`docs/TEP_VALIDATION.md`。

## DAYPSCI v1

目前未找到可核验的公开原始数据与许可证，因此未伪造验证结果；本项目本次也不进行现场授权数据验证。已提供 schema 适配器和 fail-closed 测试，仅作为未来扩展。

## PLC-BEAD

PLC-BEAD 是 PLC 程序/编译二进制数据，不是过程时间序列，不用于维护调度验证。


## C-MAPSS 调度对照

除 RUL 预测外，项目还在 100 条 FD001 退化轨迹上比较维护调度策略。该对照采用明确的成本模型：维护成本 80、故障成本 800、运行成本 1；维护会将单元重置到首个观测轨迹状态，这是公开轨迹上的反事实假设，不冒充真实维修工单。

| 策略 | 平均成本 | 平均故障 | 平均维护次数 |
|---|---:|---:|---:|
| 不维护 | 913.17 | 0.83 | 0.00 |
| 固定间隔 50 | 566.00 | 0.00 | 4.00 |
| Oracle RUL ≤20 | 325.84 | 0.00 | 0.96 |
| 预测 RUL ≤35 | 778.74 | 0.64 | 0.22 |
| 预测 RUL ≤50 | 726.67 | 0.56 | 0.37 |

结果说明：预测 RUL 已经优于不维护和固定间隔基线，但距离 Oracle RUL 仍有明显差距。原始证据见 `artifacts/cmapss_scheduling.json`。
