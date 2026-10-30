import json
from pathlib import Path
from wm_maint.tools import MaintenanceAgent

agent=MaintenanceAgent(seed=20261008)
plan=agent.world_model_plan(horizon=12)
verification=agent.highfidelity_verify(plan['plan_id'], n_scenarios=32)
execution=agent.execute_verified_plan(plan['plan_id'], approved=True)
report={'plan':plan,'verification':verification,'execution':execution,'calibration':agent.calibration_status(),'trace_valid':agent.trace.verify()}
Path('artifacts/shielded_plan_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'verification':verification,'execution':{k:execution.get(k) for k in ['status','total_profit','total_failures','final_hour','actual_vs_verified']},'calibration':repr(report['calibration'])},ensure_ascii=False,indent=2))
