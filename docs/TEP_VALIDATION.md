# Tennessee Eastman Process 外部验证

## 数据来源

- 数据集：Tennessee Eastman Process Mode 1；
- 仓库：`Blound04/tennessee-eastman-dataset`；
- 许可证：MIT；
- 原始模型引用：
  - Downs, J.J. and Vogel, E.F. (1993), A plant-wide industrial process control problem；
  - Bathelt, Ricker and Jelali (2015), Revision of the Tennessee Eastman process model；
- 边界：TEP 是公开过程仿真基准，不是真实生产 DCS 数据。

## 无监督异常检测

使用 500 小时正常数据的前半段拟合变量均值和标准差，后半段估计阈值。对 21 类故障批次做短窗口异常评分。

| 指标 | 结果 |
|---|---:|
| 平均故障检出率 | 86.67% |
| 最低单类检出率 | 0%（故障 21） |
| 正常误报率 | 1.34% |
| 故障 5 检出率 | 40% |
| 故障 21 检出率 | 0% |

结论：TEP 中部分慢变/未标注故障难以仅靠简单统计门检测，必须保守转人工复核。

## 监督故障分类

使用每类前 5 个批次训练 HistGradientBoosting，后 5 个批次作为留出测试。

| 指标 | 结果 |
|---|---:|
| 故障类型准确率 | 68.60% |
| 宏 F1 | 0.700 |
| 加权 F1 | 0.699 |
| 测试窗口 | 15360 |
| 较强类别 | 故障 1/2/3/8/10 |
| 较弱类别 | 故障 15/16/21 |

## 不接受的结果

监督式正常/故障二分类虽然故障检出率 99.75%，但正常误报率高达 99.73%，不可用于生产门控。

因此最终建议：

```text
无监督异常检测负责“是否异常”
监督分类负责“异常属于哪一类”
两者都必须经过人工审批或保守降级
```

## 原始结果

- `artifacts/tep_validation.json`
- `artifacts/tep_supervised_validation.json`
- `scripts/validate_tep.py`
- `scripts/validate_tep_supervised.py`
