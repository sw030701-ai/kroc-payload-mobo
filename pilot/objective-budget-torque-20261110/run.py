import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/kroc-mpl')
import json,time,sys,platform,itertools
from pathlib import Path
import numpy as np
import pandas as pd
from numba import njit
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
NAMES=['IAE','ISE','ITAE','ITSE']
BOUNDS=np.array([200.,50.,10.,200.,50.,10.])
@njit
def terms(q,v):
    h=.1*np.sin(q[1]);c=np.cos(q[1])
    M=np.array([[.65+.2*c,.05+.1*c],[.05+.1*c,.05]])
    C=np.array([-h*(2*v[0]*v[1]+v[1]**2),h*v[0]**2])
    G=np.array([29.43*np.cos(q[0])+4.905*np.cos(q[0]+q[1]),4.905*np.cos(q[0]+q[1])])
    return M,C,G
@njit
def deriv(y,u):
    M,C,G=terms(y[:2],y[2:]);r=u-C-G
    det=M[0,0]*M[1,1]-M[0,1]**2
    return np.array([y[2],y[3],(M[1,1]*r[0]-M[0,1]*r[1])/det,(-M[0,1]*r[0]+M[0,0]*r[1])/det])
@njit
def sim(k,lim,task=0,dt=.002,sub=2,trace=False,derivative_weight=0.):
    n=int(round(10/dt));y=np.zeros(4);z=np.zeros(2);s=np.zeros(4);peakr=0.;peaka=0.;sat=0.;lastbad=-1;over=0.;ok=1.
    data=np.zeros((n if trace else 1,9));target=np.array([1.,.5])
    if task==1:target=np.array([.8,.7])
    if task==2:target=np.array([1.2,.3])
    e=np.zeros(2)
    for i in range(n):
        t=i*dt;r=target.copy();rdot=np.zeros(2)
        if task==2:
            a=min(t/2.,1.);r=target*(10*a**3-15*a**4+6*a**5);rdot=target*(30*a**2-60*a**3+30*a**4)/2.
        e=r-y[:2];u=np.zeros(2);ap=np.zeros(2)
        for j in range(2):
            u[j]=k[3*j]*e[j]+k[3*j+1]*z[j]-k[3*j+2]*y[j+2]+derivative_weight*k[3*j+2]*rdot[j]
            ap[j]=min(max(u[j],-lim[j]),lim[j])
            if abs(u[j])<=lim[j] or e[j]*(u[j]-ap[j])<=0:z[j]+=dt*e[j]
            sat+=(1. if abs(u[j])>lim[j] else 0.)
            peakr=max(peakr,abs(u[j]));peaka=max(peaka,abs(ap[j]))
            over=max(over,(y[j]-target[j])/target[j])
        if max(abs(e[0]),abs(e[1]))>.02:lastbad=i
        s[0]+=dt*np.sum(np.abs(e));s[1]+=dt*np.sum(e**2);s[2]+=dt*t*np.sum(np.abs(e));s[3]+=dt*t*np.sum(e**2)
        if trace:
            data[i,0]=t;data[i,1:3]=y[:2];data[i,3:5]=r;data[i,5:7]=u;data[i,7:9]=ap
        h=dt/sub
        for _ in range(sub):
            a=deriv(y,ap);b=deriv(y+h*a/2,ap);c=deriv(y+h*b/2,ap);d=deriv(y+h*c,ap);y+=h*(a+2*b+2*c+d)/6
        if not np.all(np.isfinite(y)) or np.max(np.abs(y[:2]))>20 or np.max(np.abs(y[2:]))>200:
            ok=0.;break
    settling=(lastbad+1)*dt if lastbad<n-1 and task!=2 and ok else np.nan
    metrics=np.array([np.sqrt(s[1]/20),s[0],settling,over if task!=2 else np.nan,peakr,peaka,sat/(2*n),ok,(1. if ok and np.max(np.abs(e))<=.02 else 0.)])
    if not ok:s[:]=1e12
    return s,metrics,data
MET=['rmse','iae','settling','overshoot','peak_requested','peak_applied','saturation_duty','numerical_ok','tracking_feasible']
def run():
    start=time.time();candidates=[];selected=[];checks=[]
    for phase,seeds,budget in [('exploratory',range(101,104),256),('confirmatory',range(201,211),1024)]:
        for seed in seeds:
            for condition,limits in [('nominal',[70.,10.]),('reduced',[42.,6.])]:
                for obj,name in enumerate(NAMES):
                    rng=np.random.default_rng(seed);pop=rng.random((32,6));inc=1e99;best=None;cnt=0;tm=time.time()
                    while cnt<budget:
                        scores=[]
                        for x in pop:
                            gain=x*BOUNDS;sc,met,_=sim(gain,np.array(limits));cnt+=1;scores.append(sc[obj])
                            candidates.append(dict(phase=phase,seed=seed,condition=condition,objective=name,evaluation=cnt,score=sc[obj],**dict(zip(['kp1','ki1','kd1','kp2','ki2','kd2'],gain)),**dict(zip(NAMES,sc)),**dict(zip(MET,met))))
                            if sc[obj]<inc:inc=sc[obj];best=x.copy()
                        if cnt in [32,128,256,512,1024]:
                            for task in [0,1,2]:
                                _,met,_=sim(best*BOUNDS,np.array(limits),task)
                                selected.append(dict(phase=phase,seed=seed,condition=condition,objective=name,budget=cnt,task=task,train_score=inc,**dict(zip(['kp1','ki1','kd1','kp2','ki2','kd2'],best*BOUNDS)),**dict(zip(MET,met))))
                        scores=np.array(scores);worst=np.argmax(scores);pop[worst]=best;scores[worst]=inc
                        parents=[]
                        for _ in range(32):
                            a,b=rng.integers(0,32,2);parents.append(pop[a if scores[a]<scores[b] else b].copy())
                        new=np.array(parents)
                        for j in range(0,32,2):
                            if rng.random()<.8:
                                mask=rng.random(6)<.5;a=new[j].copy();new[j,mask]=new[j+1,mask];new[j+1,mask]=a[mask]
                        mask=rng.random((32,6))<1/6;new=np.clip(new+mask*rng.normal(0,.1,(32,6)),0,1);pop=new
                    print(phase,seed,condition,name,cnt,round(time.time()-tm,2),flush=True)
    pd.DataFrame(candidates).to_csv(OUT/'candidates.csv.gz',index=False)
    S=pd.DataFrame(selected);S.to_csv(OUT/'selected_metrics.csv',index=False)
    for _,r in S[(S.phase=='confirmatory')&(S.budget==1024)&(S.task!=0)].iterrows():
        gain=r[['kp1','ki1','kd1','kp2','ki2','kd2']].to_numpy(float);lim=np.array([70.,10.] if r.condition=='nominal' else [42.,6.]);base=sim(gain,lim,int(r.task))[1]
        for kind,dt,sub in [('plant_refined',.002,4),('controller_refined',.001,2)]:
            m=sim(gain,lim,int(r.task),dt,sub)[1];checks.append(dict(seed=r.seed,condition=r.condition,objective=r.objective,task=r.task,kind=kind,rmse=base[0],refined_rmse=m[0],relative_change=(m[0]-base[0])/base[0]))
    pd.DataFrame(checks).to_csv(OUT/'integration_checks.csv',index=False)
    for cond,lim in [('nominal',np.array([70.,10.])),('reduced',np.array([42.,6.]))]:
        r=S[(S.seed==201)&(S.condition==cond)&(S.objective=='IAE')&(S.budget==1024)&(S.task==1)].iloc[0]
        _,_,tr=sim(r[['kp1','ki1','kd1','kp2','ki2','kd2']].to_numpy(float),lim,1,trace=True)
        pd.DataFrame(tr,columns=['t','q1','q2','r1','r2','requested1','requested2','applied1','applied2']).to_csv(OUT/f'trace_{cond}.csv.gz',index=False)
    (OUT/'execution_summary.json').write_text(json.dumps(dict(elapsed_seconds=time.time()-start,candidate_evaluations=len(candidates),selected_rollouts=len(selected),refinement_rollouts=len(checks),python=sys.version,platform=platform.platform()),indent=2))
if __name__=='__main__':run()
