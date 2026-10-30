import json
from pathlib import Path
from wm_maint.tools import MaintenanceAgent

agent = MaintenanceAgent(seed=20261008)
plan = agent.world_model_plan(horizon=12)
verification = agent.highfidelity_verify(plan["plan_id"], n_scenarios=32)
report = {
    "plan_id": plan["plan_id"],
    "horizon": plan["horizon"],
    "verification": verification,
    "trace_valid": agent.trace.verify(),
}
out = Path("artifacts/tail_risk_validation.json")
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
