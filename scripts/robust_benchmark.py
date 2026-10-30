import json
from pathlib import Path
import numpy as np
from wm_maint.config import load_config
from wm_maint.evaluation import WorldModelPolicy, evaluate_policy, threshold_policy
from wm_maint.world_model import EnsembleWorldModel

cfg=load_config()
model=EnsembleWorldModel.load('artifacts/world_model.npz')
seeds=[101,202,303,404,505,606,707,808,909,1010]
hours=int(cfg['plant']['episode_hours'])
pcfg=cfg['planner']
policies={
  'threshold': lambda: threshold_policy,
  'mean_mpc': lambda: WorldModelPolicy(model, plan_every=int(pcfg['replan_every']), verify_candidates=4, horizon=int(pcfg['horizon']), population=int(pcfg['population']), elite=int(pcfg['elite']), iterations=int(pcfg['iterations']), robust_verify=False, safety_shield_enabled=False),
  'robust_shielded_mpc': lambda: WorldModelPolicy(model, plan_every=int(pcfg['replan_every']), verify_candidates=4, horizon=int(pcfg['horizon']), population=int(pcfg['population']), elite=int(pcfg['elite']), iterations=int(pcfg['iterations']), robust_verify=True, safety_shield_enabled=True),
}
rows={}
for name,factory in policies.items():
    result=evaluate_policy(name,seeds,hours,factory)
    summary=result.summary()
    summary['actual_failure_probability']=float(np.mean([e.failures>0 for e in result.episodes]))
    summary['actual_unplanned_downtime_mean']=summary['downtime_hours_mean']
    summary['verified_failure_probability_mean']=summary.get('verified_failure_probability_mean',0.0)
    summary['verified_failures_p90_mean']=summary.get('verified_failures_p90_mean',0.0)
    summary['verified_cvar10_mean']=summary.get('verified_cvar10_mean',0.0)
    rows[name]=summary
    print(name,json.dumps(summary,ensure_ascii=False,indent=2))
# actual/verified ratio where both available
base=rows['mean_mpc']; rob=rows['robust_shielded_mpc']
report={'seeds':seeds,'policies':rows,'improvement':{
  'profit_delta_pct':(rob['profit_mean']-base['profit_mean'])/max(1.0,abs(base['profit_mean']))*100,
  'failure_probability_pp':(rob['actual_failure_probability']-base['actual_failure_probability'])*100,
  'failures_delta_pct':(rob['failures_mean']-base['failures_mean'])/max(1.0,abs(base['failures_mean']))*100,
  'downtime_delta_pct':(rob['downtime_hours_mean']-base['downtime_hours_mean'])/max(1.0,abs(base['downtime_hours_mean']))*100,
  'cvar10_delta':rob['verified_cvar10_mean']-base['verified_cvar10_mean'],
}}
Path('artifacts/robust_shield_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('wrote artifacts/robust_shield_comparison.json')
