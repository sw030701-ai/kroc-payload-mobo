import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/kroc-new-mpl')
from pathlib import Path
import argparse, csv, hashlib, json, platform, sys, time
import numpy as np
from numba import njit

ROOT=Path(__file__).resolve().parent
BOUNDS=np.array([200.,50.,10.,200.,50.,10.])
METHODS=['IAE','ISE','ITAE','ITSE','PEN']
GKEYS=['kp1','ki1','kd1','kp2','ki2','kd2']
MKEYS=['rmse','iae','ise','itae','itse','torque_rms','saturation_duty','tracking_feasible','numerical_ok','overshoot_percent','settling','end_time','peak_requested','peak_applied','normalized_effort']
PAPER={'ISE':[147.1182,43.1268,9.9803,198.0562,.7428,9.9872], 'IAE':[68.7215,49.8198,9.7411,193.5716,.5723,3.2319], 'ITAE':[57.2846,49.0422,6.7107,181.3745,.6170,4.7110], 'ITSE':[192.9441,42.0097,9.6103,126.4812,.8804,9.8813]}

def params(family,m2):
    # m1,m2,l1,l2,r1,r2,I1,I2,g
    r1,r2=(.2,.1) if family==0 else (.1,.05)
    return np.array([10.,m2,.2,.1,r1,r2,0. if family==0 else 10*.2**2/12,0. if family==0 else m2*.1**2/12,9.81])

@njit
def terms(q,v,p):
    m1,m2,l1,l2,r1,r2,I1,I2,g=p
    b=m2*l1*r2;c=np.cos(q[1]);h=b*np.sin(q[1])
    d=I2+m2*r2*r2;a=I1+I2+m1*r1*r1+m2*(l1*l1+r2*r2)
    M=np.array([[a+2*b*c,d+b*c],[d+b*c,d]])
    C=np.array([-h*(2*v[0]*v[1]+v[1]**2),h*v[0]**2])
    G=np.array([(m1*r1+m2*l1)*g*np.cos(q[0])+m2*r2*g*np.cos(q[0]+q[1]),m2*r2*g*np.cos(q[0]+q[1])])
    return M,C,G

@njit
def deriv(y,u,p):
    M,C,G=terms(y[:2],y[2:],p);r=u-C-G
    det=M[0,0]*M[1,1]-M[0,1]**2
    return np.array([y[2],y[3],(M[1,1]*r[0]-M[0,1]*r[1])/det,(-M[0,1]*r[0]+M[0,0]*r[1])/det])

@njit
def reference(t,task):
    r=np.array([1.,.5])
    if task==1 or task==3:
        target=np.array([1.2,.3]) if task==1 else np.array([1.1,.4])
        duration=2. if task==1 else .7
        a=min(t/duration,1.);r=target*(10*a**3-15*a**4+6*a**5)
    if task==2:r=np.array([.7,.6])
    if task==4:r=np.array([.6*np.sin(.8*t),.4*np.sin(1.1*t)])
    return r

@njit
def simulate(k,p,phat,lim,task,sub=2,trace=False):
    dt=.002;T=10.;n=5000;y=np.zeros(4);z=np.zeros(2)
    sums=np.zeros(4);usq=0.;unsq=0.;sat=0.;over=0.;bad=-1;ok=1.;peakr=0.;peaka=0.
    tr=np.zeros((n if trace else 1,13));e=np.zeros(2);end=0.
    target=reference(T,task)
    for i in range(n):
        t=i*dt;end=t;r=reference(t,task);e=r-y[:2]
        _,_,ghat=terms(y[:2],y[2:],phat)
        u=np.zeros(2);ap=np.zeros(2)
        for j in range(2):
            u[j]=k[3*j]*e[j]+k[3*j+1]*z[j]-k[3*j+2]*y[j+2]+ghat[j]
            ap[j]=min(max(u[j],-lim[j]),lim[j])
            if abs(u[j])<=lim[j] or e[j]*(u[j]-ap[j])<=0:z[j]+=dt*e[j]
            sat+=1. if abs(u[j])>lim[j] else 0.
            usq+=dt*ap[j]**2;unsq+=dt*(ap[j]/lim[j])**2;peakr=max(peakr,abs(u[j]));peaka=max(peaka,abs(ap[j]))
            if task==0 or task==2:over=max(over,(y[j]-target[j])/target[j]*100.)
        if np.max(np.abs(e))>.02:bad=i
        sums[0]+=dt*np.sum(np.abs(e));sums[1]+=dt*np.sum(e**2)
        sums[2]+=dt*t*np.sum(np.abs(e));sums[3]+=dt*t*np.sum(e**2)
        if trace:
            tr[i,0]=t;tr[i,1:3]=y[:2];tr[i,3:5]=r;tr[i,5:7]=u;tr[i,7:9]=ap;tr[i,9:11]=y[2:];tr[i,11:13]=z
        h=dt/sub
        for _ in range(sub):
            a=deriv(y,ap,p);b=deriv(y+h*a/2,ap,p);c=deriv(y+h*b/2,ap,p);d=deriv(y+h*c,ap,p)
            y+=h*(a+2*b+2*c+d)/6
        if not np.all(np.isfinite(y)) or np.max(np.abs(y[:2]))>20 or np.max(np.abs(y[2:]))>200:
            ok=0.;break
    settling=(bad+1)*dt if bad<n-1 and task in (0,2) and ok else np.nan
    m=np.array([np.sqrt(sums[1]/(2*T)),sums[0],sums[1],sums[2],sums[3],np.sqrt(usq/(2*T)),sat/(2*n),1. if ok and np.max(np.abs(e))<=.02 else 0.,ok,over if task in (0,2) else np.nan,settling,end,peakr,peaka,unsq/(2*T)])
    if not ok:
        m[0]=20.;m[1]=400.;m[2:5]=1e12;m[5]=np.sqrt(np.mean(lim**2));m[6]=1.;m[7]=0.
    return m,tr

def limits(family,kind):
    p=params(family,5.);g=terms(np.zeros(2),np.zeros(2),p)[2]
    return g*(1.25 if kind=='tight' else 2.)

def score(m,method,lim):
    if not m[8]:return 1e12
    if method!='PEN':return m[{'IAE':1,'ISE':2,'ITAE':3,'ITSE':4}[method]]
    # Train tasks have nonnegative final targets; max target-relative overshoot
    # for moving train task is not defined in common metrics: use 0 there.
    over=0. if np.isnan(m[9]) else m[9]
    return m[1]/20+max(0.,over-5.)**2+5*m[6]**2+.5*m[14]

def writer(path,fields):
    f=path.open('w',newline='');w=csv.DictWriter(f,fieldnames=fields);w.writeheader();return f,w

def run(experiment,budget=256):
    out=ROOT/'results'/f'E{experiment}';out.mkdir(parents=True,exist_ok=True)
    if (out/'summary.json').exists():raise RuntimeError('Completed results exist; use a fresh output directory')
    family=0 if experiment<=2 else 1;m2=5. if experiment%2 else 6.
    p=params(family,m2);phat=params(family,5.);lim=limits(family,'tight')
    start=time.time();prefix=['experiment','seed','method']
    cf,cw=writer(out/'candidates.csv',prefix+['evaluation','score']+GKEYS)
    rf,rw=writer(out/'train_raw.csv',prefix+['evaluation','task']+MKEYS)
    sf,sw=writer(out/'selected.csv',prefix+['train_score']+GKEYS)
    tf,tw=writer(out/'test_raw.csv',prefix+['limit','task']+MKEYS)
    nf,nw=writer(out/'refinement.csv',prefix+['limit','task','base_rmse','refined_rmse','absolute_change'])
    seeds=list(range(110000+experiment*100+1,110000+experiment*100+9))
    calls=0;testcalls=0;refinecalls=0
    for seed in seeds:
        for method in METHODS:
            rng=np.random.default_rng(seed);pop=rng.random((32,6));inc=np.inf;best=None;count=0
            for generation in range(budget//32):
                scores=[]
                for x in pop:
                    count+=1;k=x*BOUNDS;vals=[]
                    for task in (0,1):
                        m,_=simulate(k,p,phat,lim,task);calls+=1
                        rw.writerow(dict(experiment=experiment,seed=seed,method=method,evaluation=count,task=task,**dict(zip(MKEYS,m))))
                        val=score(m,method,lim)
                        vals.append(val)
                    val=float(np.mean(vals));scores.append(val)
                    cw.writerow(dict(experiment=experiment,seed=seed,method=method,evaluation=count,score=val,**dict(zip(GKEYS,k))))
                    if val<inc:inc=val;best=x.copy()
                scores=np.array(scores);parents=[]
                for _ in range(32):
                    a,b=rng.integers(0,32,2);parents.append(pop[a if scores[a]<scores[b] else b].copy())
                new=np.array(parents)
                for j in range(0,32,2):
                    if rng.random()<.8:
                        mask=rng.random(6)<.5;a=new[j].copy();new[j,mask]=new[j+1,mask];new[j+1,mask]=a[mask]
                mask=rng.random((32,6))<1/6;new=np.clip(new+mask*rng.normal(0,.1,(32,6)),0,1);new[0]=best;pop=new
            k=best*BOUNDS;sw.writerow(dict(experiment=experiment,seed=seed,method=method,train_score=inc,**dict(zip(GKEYS,k))))
            for kind in ('tight','nominal'):
                testlim=limits(family,kind)
                for task in (2,3,4):
                    trflag=seed==seeds[0] and method in ('IAE','ISE','PEN') and kind=='tight'
                    m,tr=simulate(k,p,phat,testlim,task,trace=trflag);testcalls+=1
                    tw.writerow(dict(experiment=experiment,seed=seed,method=method,limit=kind,task=task,**dict(zip(MKEYS,m))))
                    if trflag:
                        import pandas as pd
                        pd.DataFrame(tr,columns=['t','q1','q2','r1','r2','requested1','requested2','applied1','applied2','v1','v2','z1','z2']).to_csv(out/f'trace_{method}_task{task}.csv.gz',index=False)
                    mr,_=simulate(k,p,phat,testlim,task,sub=4);refinecalls+=1
                    nw.writerow(dict(experiment=experiment,seed=seed,method=method,limit=kind,task=task,base_rmse=m[0],refined_rmse=mr[0],absolute_change=abs(mr[0]-m[0])))
            for f in (cf,rf,sf,tf,nf):f.flush()
            print(json.dumps(dict(experiment=experiment,seed=seed,method=method,candidates=count,train_calls=calls,elapsed_s=round(time.time()-start,2))),flush=True)
    # Fixed paper gains are deterministic transfer checks, not independent seeds.
    for name,k in PAPER.items():
        for kind in ('tight','nominal'):
            for task in (2,3,4):
                m,_=simulate(np.array(k),p,phat,limits(family,kind),task);testcalls+=1
                tw.writerow(dict(experiment=experiment,seed=-1,method='PAPER_'+name,limit=kind,task=task,**dict(zip(MKEYS,m))))
    for f in (cf,rf,sf,tf,nf):f.close()
    (out/'summary.json').write_text(json.dumps(dict(experiment=experiment,family=family,actual_parameters=p.tolist(),compensation_parameters=phat.tolist(),limits_tight=lim.tolist(),seeds=seeds,budget=budget,optimizations=40,candidate_evaluations=8*5*budget,training_rollouts=calls,test_rollouts=testcalls,refinement_rollouts=refinecalls,elapsed_s=time.time()-start,python=sys.version,platform=platform.platform(),code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--experiment',type=int,choices=[1,2,3,4],required=True);a.add_argument('--budget',type=int,default=256);v=a.parse_args();run(v.experiment,v.budget)
