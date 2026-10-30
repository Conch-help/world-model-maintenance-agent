import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'artifacts'/'evaluation_report.json'
d=json.loads(p.read_text(encoding='utf-8'))
s=d['summary']
base=s['world_model_verified_mpc']
rob=s['world_model_robust_mpc']
report={
  'comparison':{
    'baseline':base,
    'robust':rob,
    'delta':{
      'profit_mean_pct':(rob['profit_mean']-base['profit_mean'])/max(1.0,abs(base['profit_mean']))*100,
      'profit_std_pct':(rob['profit_std']-base['profit_std'])/max(1.0,abs(base['profit_std']))*100,
      'failures_mean_pct':(rob['failures_mean']-base['failures_mean'])/max(1.0,abs(base['failures_mean']))*100,
      'failure_probability_pp':(rob['verified_failure_probability_mean']-base['verified_failure_probability_mean'])*100,
      'failures_p90_delta':rob['verified_failures_p90_mean']-base['verified_failures_p90_mean'],
      'cvar10_delta':rob['verified_cvar10_mean']-base['verified_cvar10_mean'],
    }
  },
  'seeds':d['seeds']
}
out=root/'artifacts'/'optimization_comparison.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
