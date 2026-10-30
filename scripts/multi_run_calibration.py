import json
from pathlib import Path
import numpy as np
from wm_maint.tools import MaintenanceAgent

seeds=[20261008,1001,2002,3003,4004]
runs=[]
for seed in seeds:
    agent=MaintenanceAgent(seed=seed)
    plan=agent.world_model_plan(horizon=12)
    verification=agent.highfidelity_verify(plan['plan_id'], n_scenarios=32)
    execution=agent.execute_verified_plan(plan['plan_id'], approved=True)
    calibration=agent.calibration_status()
    runs.append({
        'seed':seed,
        'plan_id':plan['plan_id'],
        'verified_profit':verification['verified_profit'],
        'verified_failures':verification['verified_failures'],
        'failure_probability':verification['failure_probability'],
        'failures_p90':verification['failures_p90'],
        'profit_cvar10':verification['profit_cvar10'],
        'actual_profit':execution['total_profit'],
        'actual_failures':execution['total_failures'],
        'actual_vs_verified':execution['actual_vs_verified'],
        'calibration':calibration,
        'trace_valid':agent.trace.verify(),
    })
report={
    'seeds':seeds,
    'runs':runs,
    'aggregate':{
        'profit_mean':float(np.mean([r['actual_profit'] for r in runs])),
        'failures_mean':float(np.mean([r['actual_failures'] for r in runs])),
        'profit_scale_mean':float(np.mean([r['actual_vs_verified']['profit_ratio'] for r in runs])),
        'profit_scale_std':float(np.std([r['actual_vs_verified']['profit_ratio'] for r in runs])),
        'failure_bias_mean':float(np.mean([r['actual_vs_verified']['failure_delta'] for r in runs])),
        'shield_adjustments_mean':float(np.mean([r['actual_vs_verified']['shield_adjustments'] for r in runs])),
        'trace_valid_rate':float(np.mean([r['trace_valid'] for r in runs])),
    },
    'boundary':'These are five independent MCP-agent calibration runs. They are not five separate human-approved AGH UI sessions; the official AGH evidence remains the approved real session.',
}
Path('artifacts/multi_run_calibration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report['aggregate'],ensure_ascii=False,indent=2))
