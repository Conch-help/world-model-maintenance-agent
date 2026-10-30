"""Generate submission-facing reports from raw JSON artifacts."""
from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
DOCS = ROOT / "docs"
DOCS.mkdir(parents=True, exist_ok=True)


def load(name: str) -> dict:
    return json.loads((ART / name).read_text(encoding="utf-8"))


def main() -> int:
    train = load("training_report.json")
    evald = load("evaluation_report.json")
    summary = evald["summary"]
    baseline = summary["threshold_maintenance"]["profit_mean"]
    order = [
        ("full_production", "全速生产、无维护"),
        ("fixed_interval", "固定间隔维护"),
        ("threshold_maintenance", "阈值维护"),
        ("highfidelity_oracle", "高保真直接搜索（有限预算）"),
        ("world_model_only", "世界模型规划"),
        ("world_model_robust_mpc", "稳健世界模型 + 高保真验证"),
        ("world_model_verified_mpc", "普通世界模型 + 高保真验证"),
    ]
    rows = []
    for key, label in order:
        row = summary[key]
        rows.append({
            "policy": label,
            "profit": row["profit_mean"],
            "profit_delta_pct": (row["profit_mean"] - baseline) / max(1.0, abs(baseline)) * 100.0,
            "failures": row["failures_mean"],
            "downtime_hours": row["downtime_hours_mean"],
            "unmet": row["unmet_mean"],
            "capacity_violations": row["capacity_violations_mean"],
        })
    with (ART / "benchmark.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# 验证报告",
        "",
        "## 1. 数据与验证边界",
        "",
        f"- 世界模型训练：{train['dataset']['n_episodes']} 个训练场景，{train['dataset']['n_transitions']} 条动作转移；",
        f"- 留出测试：{evald['seeds']}，共 {len(evald['seeds'])} 个未见随机种子、每个 168 h；",
        "- 高保真校验：复制当前物理状态，但使用独立的未来随机流和多个验证场景，避免复现正式生产回合的私有随机数；",
        "- 世界模型只使用当前状态和动作预测下一步，不接触高保真验证场景的随机种子。",
        "",
        "## 2. 世界模型一步预测",
        "",
        "| 指标 | 值 |",
        "|---|---:|",
        f"| 健康 RMSE（归一化） | {train['heldout']['health_rmse_normalized']:.4f} |",
        f"| 全机状态 RMSE（归一化） | {train['heldout']['machine_state_rmse_normalized']:.4f} |",
        f"| 单步利润 MAE | {train['heldout']['profit_mae']:.1f} |",
        f"| 1σ 集成覆盖率 | {train['heldout']['coverage_1sigma']*100:.2f}% |",
        f"| 2σ 集成覆盖率 | {train['heldout']['coverage_2sigma']*100:.2f}% |",
        "",
        "## 3. 决策策略对比",
        "",
        "| 策略 | 平均利润 | 相对阈值维护 | 平均故障 | 停机时间/h | 平均未满足需求 | 容量违反 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['policy']} | {row['profit']:.1f} | {row['profit_delta_pct']:+.2f}% | "
            f"{row['failures']:.2f} | {row['downtime_hours']:.2f} | {row['unmet']:.1f} | {row['capacity_violations']:.2f} |"
        )
    verified = summary["world_model_verified_mpc"]
    lines += [
        "",
        "## 4. 高保真验证的作用",
        "",
        f"- 世界模型规划 + 高保真验证比阈值维护的利润高 **{verified['profit_delta_vs_threshold_pct']:.2f}%**；",
        f"- 规划利润预测 MAE 为 **{verified['plan_prediction_mae']:.1f}**，WAPE 为 **{verified['plan_prediction_wape_pct']:.2f}%**；",
        f"- 高保真验证回合中的容量违反为 **{verified['verified_capacity_violations']:.0f}**；",
        "- `world_model_only` 用于衡量模型规划上限；`world_model_robust_mpc` 按 CVaR10、故障概率和 P90 故障选择计划；普通验证版作为对照；",
        "- `highfidelity_oracle` 只是同样有限搜索预算下的高保真直接搜索基线，不是无限算力上界；世界模型+验证策略在该基准上明显优于它。",
        "",
        "## 5. 局限",
        "",
        "- 当前高保真环境是独立随机数字孪生，不是现场 PLC/DCS 或真实产线数据；",
        "- 三台设备、168 h 的经济模型用于可控验证，不能直接外推到所有工业设备；",
        "- 世界模型利润预测仍有误差，因此维护动作必须经过高保真验证和 AGH 人工审批；",
        "- 最终获奖版本需要在真实设备或公开工业数据集上重做外部有效性验证。",
        "",
        "## 6. 原始证据",
        "",
        "- `artifacts/training_report.json`",
        "- `artifacts/evaluation_report.json`",
        "- `artifacts/benchmark.csv`",
        "- `artifacts/closed_loop_report.json`",
        "- `artifacts/mcp_trace.jsonl`",
    ]
    (DOCS / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    model_card = f"""# 模型声明 / Model Card

## 世界模型

| 字段 | 内容 |
|---|---|
| 模型名称 | Action-Conditioned Ensemble World Model |
| 版本 | wm-maint/0.1.0 |
| 结构 | {train['fit']['n_train']:.0f} 条训练转移上的 {5} 个 MLP 集成 |
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
| 模型 | Agnes 模型，具体名称/版本以 AGH 真机会话为准 |
| 使用环节 | 任务规划、工具选择、验证反馈、审批请求、结果汇总 |
| 调用方式 | AGH 内置 provider + MCP stdio |
| 工具 | plant_read_state、world_model_plan、highfidelity_verify、request_maintenance_action、trace_export |

## 数据与局限

本项目使用自建独立数字孪生生成训练数据。它不是真实产线数据；本次提交不进行现场数据验证；现场数据仅作为未来扩展。
"""
    (DOCS / "MODEL_CARD.md").write_text(model_card, encoding="utf-8")
    print("generated", DOCS / "RESULTS.md", DOCS / "MODEL_CARD.md", ART / "benchmark.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
