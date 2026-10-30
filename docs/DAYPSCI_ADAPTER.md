# DAYPSCI v1 授权数据适配器

## 当前状态

没有找到可核验的公开 DAYPSCI v1 原始文件、论文数据附件或许可证，因此本仓库不会伪造 DAYPSCI 验证结果，也不会自动抓取不明镜像。

已提供：

- `src/wm_maint/adapters/daypsci.py`：schema 验证和基础统计；
- `scripts/validate_daypsci.py`：对授权 CSV 做验证；
- `tests/test_daypsci.py`：合成 schema 测试。

## 期望字段

至少包含：

- `timestamp`、`time` 或 `datetime`；
- 两组以上 PLC 数值信号；
- `fault_active`、`is_fault`、`fault_label` 等标签字段之一。

## 合规使用

若未来获得授权文件，可按以下方式扩展；本次提交不执行：

```powershell
$env:PYTHONPATH = "src"
python scripts\validate_daypsci.py --input "path\to\authorized_daypsci.csv"
```

验证通过后，再把文件接入外部验证脚本。不得把未授权或不明来源的 DAYPSCI 数据放入公开仓库。

## 结论

当前项目可以诚实表述为：

> 已完成 TEP 公开过程仿真外部验证，并准备好 DAYPSCI PLC 测试台数据接入契约；DAYPSCI 本次不列入验证范围；适配器仅作为未来扩展。
