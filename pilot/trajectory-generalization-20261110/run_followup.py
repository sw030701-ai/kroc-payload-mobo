import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/kroc-mpl')
import json,time,hashlib,platform,itertools
from pathlib import Path
import numpy as np
import pandas as pd
from simulator import sim,MET
R=Path(__file__).resolve().parent
O=R/'results';O.mkdir(exist_ok=True)
C=json.loads((R/'config.json').read_text())
GAIN=['kp1','ki1','kd1','kp2','ki2','kd2']
def main():
    start=time.time();archive=[];chosen=[];timings=[]
    for seed,obj,condition,bound,training in itertools.product(C['seeds'],C['objectives'],C['limits'],C['bounds'],C['training']):
        tick=time.time();rng=np.random.default_rng(seed);pop=rng.random((32,6));bounds=np.array(C['bounds'][bound],float);lim=np.array(C['limits'][condition],float)
        tasks=C['training'][training];cost=len(tasks);inc=1e99;best=None;count=0
        keys=dict(seed=seed,objective=obj,condition=condition,bound=bound,training=training)
        while count*cost<max(C['rollout_budgets']):
            scores=[]
            for x in pop:
                comp=[];valid=True
                for task in tasks:
                    sc,met,_=sim(x*bounds,lim,task);comp.append(sc[0 if obj=='IAE' else 1]);valid=valid and bool(met[7])
                score=float(np.mean(comp));count+=1;scores.append(score)
                archive.append(dict(**keys,candidate=count,training_rollouts=count*cost,score=score,numerical_ok=valid,component0=comp[0],component1=comp[1] if cost==2 else np.nan,**dict(zip(GAIN,x*bounds))))
                if score<inc:inc=score;best=x.copy()
            if count*cost in C['rollout_budgets']:
                chosen.append(dict(**keys,budget=count*cost,candidates=count,score=inc,**dict(zip(GAIN,best*bounds))))
            scores=np.array(scores);worst=np.argmax(scores);pop[worst]=best;scores[worst]=inc
            parents=[]
            for _ in range(32):
                a,b=rng.integers(0,32,2);parents.append(pop[a if scores[a]<scores[b] else b].copy())
            new=np.array(parents)
            for j in range(0,32,2):
                if rng.random()<.8:
                    mask=rng.random(6)<.5;a=new[j].copy();new[j,mask]=new[j+1,mask];new[j+1,mask]=a[mask]
            mask=rng.random((32,6))<1/6;pop=np.clip(new+mask*rng.normal(0,.1,(32,6)),0,1)
        timings.append(dict(**keys,seconds=time.time()-tick));print(keys,round(time.time()-tick,2),flush=True)
        # Recovery artifacts contain training only; no intermediate test inspection.
        if len(timings)%8==0:
            pd.DataFrame(archive).to_csv(O/'candidates.csv.gz',index=False)
            pd.DataFrame(chosen).to_csv(O/'selected.csv',index=False)
    A=pd.DataFrame(archive);S=pd.DataFrame(chosen);A.to_csv(O/'candidates.csv.gz',index=False);S.to_csv(O/'selected.csv',index=False)
    training_end=time.time();rows=[];refined=[]
    for _,s in S.iterrows():
        gain=s[GAIN].to_numpy(float);lim=np.array(C['limits'][s.condition],float)
        for task in C['test_tasks']:
            _,m,_=sim(gain,lim,task)
            row=dict(s.to_dict(),task=task,**dict(zip(MET,m)));rows.append(row)
            if s.budget==256:
                _,mr,_=sim(gain,lim,task,sub=4)
                refined.append(dict(seed=int(s.seed),objective=s.objective,condition=s.condition,bound=s.bound,training=s.training,task=task,rmse=m[0],refined_rmse=mr[0],numerical_ok=mr[7],relative_change=(mr[0]-m[0])/m[0]))
    pd.DataFrame(rows).to_csv(O/'test_metrics.csv',index=False);pd.DataFrame(refined).to_csv(O/'refinement.csv',index=False);pd.DataFrame(timings).to_csv(O/'timings.csv',index=False)
    (O/'execution.json').write_text(json.dumps(dict(ga_runs=len(timings),gain_candidates=len(A),training_simulator_calls=sum(256 for _ in timings),test_simulator_calls=len(rows),refinement_simulator_calls=len(refined),training_seconds=training_end-start,total_seconds=time.time()-start,platform=platform.platform()),indent=2))
if __name__=='__main__':main()
