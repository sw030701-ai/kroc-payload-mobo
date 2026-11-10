# EXPLORATORY mechanism/implementation audit added after inspecting main results.
# No new optimization, no main data overwrite, no confirmatory status claimed.
import json
import numpy as np,pandas as pd
from run import sim,OUT,ROOT,MET
S=pd.read_csv(OUT/'selected_metrics.csv');S=S[(S.phase=='confirmatory')&(S.budget==1024)&(S.task==2)]
rows=[]
for _,r in S.iterrows():
    k=r[['kp1','ki1','kd1','kp2','ki2','kd2']].to_numpy(float)
    for deploy,lim in [('nominal',[70.,10.]),('reduced',[42.,6.])]:
        for weight in [0.,1.]:
            _,m,_=sim(k,np.array(lim),2,derivative_weight=weight)
            if weight==0 and deploy==r.condition:assert np.isclose(m[0],r.rmse,atol=1e-13,rtol=1e-13)
            rows.append(dict(phase='posthoc_exploratory',seed=r.seed,objective=r.objective,training_torque=r.condition,deployment_torque=deploy,derivative_weight=weight,**dict(zip(MET,m))))
D=pd.DataFrame(rows);D.to_csv(OUT/'posthoc_crossover_and_derivative.csv',index=False)
D.groupby(['training_torque','deployment_torque','derivative_weight','objective'])[MET].mean().to_csv(OUT/'posthoc_summary.csv')
print(D.groupby(['training_torque','deployment_torque','derivative_weight','objective'])[['rmse','saturation_duty']].mean().to_string())
# Strong ranking effect sensitivity: leave-one-seed-out paired difference-in-differences
X=S.pivot(index='seed',columns=['condition','objective'],values='rmse')
d=(X[('reduced','ISE')]-X[('reduced','IAE')])-(X[('nominal','ISE')]-X[('nominal','IAE')])
lo=[d.drop(seed).mean() for seed in d.index]
info=dict(posthoc=True,no_reoptimization=True,simulator_calls=len(D),default_simulator_matches_all_original_final_smooth_results=True,iae_ise_interaction_min_leave_one_out=float(min(lo)),max_leave_one_out=float(max(lo)),per_seed_interaction={str(k):float(v) for k,v in d.items()})
(OUT/'posthoc_checks.json').write_text(json.dumps(info,indent=2));print(info)
