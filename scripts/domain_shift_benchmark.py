import json
from dataclasses import replace
from pathlib import Path
import numpy as np

from wm_maint.config import load_config, default_machine_specs
from wm_maint.evaluation import WorldModelPolicy
from wm_maint.plant import ProductionPlant
from wm_maint.world_model import EnsembleWorldModel

cfg=load_config(); pcfg=cfg['planner']; model=EnsembleWorldModel.load('artifacts/world_model.npz')

def shifted_specs(kind: str):
    specs=default_machine_specs(3)
    out=[]
    for s in specs:
        if kind=='degradation':
            out.append(replace(s, base_degradation=s.base_degradation*1.25, failure_sensitivity=s.failure_sensitivity*1.30, temp_gain=s.temp_gain*1.10))
        elif kind=='demand':
            out.append(s)
        else:
            out.append(s)
    return tuple(out)

def run(name, kind, seeds, hours=168):
    rows=[]
    for seed in seeds:
        plant=ProductionPlant(specs=shifted_specs(kind), seed=seed, episode_hours=hours)
        policy=WorldModelPolicy(model, plan_every=int(pcfg['replan_every']), verify_candidates=4, horizon=int(pcfg['horizon']), population=int(pcfg['population']), elite=int(pcfg['elite']), iterations=int(pcfg['iterations']), robust_verify=True, safety_shield_enabled=True)
        profit=0.0; failures=0; downtime=0.0; unmet=0.0; production=0.0
        for hour in range(hours):
            modes=policy(plant,hour)
            # Demand/price shift is implemented by changing the plant economics globally.
            _,p,done,info=plant.step(modes)
            profit+=p; failures+=info.failures; downtime+=info.downtime_count; unmet+=info.unmet; production+=info.production
            if done: break
        rows.append({'seed':seed,'profit':profit,'failures':failures,'downtime':downtime,'unmet':unmet,'production':production,'final_health':float(np.mean(plant.state.health))})
    return {'scenario':name,'rows':rows,'mean':{k:float(np.mean([r[k] for r in rows])) for k in ['profit','failures','downtime','unmet','production','final_health']}}

# The demand/price shift is represented by a subclass-free explicit demand multiplier.
original_demand=ProductionPlant.demand

def demand_shift(self,hour):
    return original_demand(self,hour)*1.15

report={'seeds':[101,202,303],'scenarios':[]}
report['scenarios'].append(run('nominal','nominal',[101,202,303]))
report['scenarios'].append(run('degradation_and_failure_shift','degradation',[101,202,303]))
ProductionPlant.demand=demand_shift
report['scenarios'].append(run('demand_15pct_shift','demand',[101,202,303]))
ProductionPlant.demand=original_demand
Path('artifacts/domain_shift_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
