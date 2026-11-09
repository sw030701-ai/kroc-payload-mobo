"""Independent objective-only pilot; never writes outside this directory."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/kroc-pilot-mpl')
import sys, json, hashlib, platform, subprocess
from pathlib import Path
from copy import deepcopy
import numpy as np
# NumPy 2.4+ removed this alias still used by pinned pymoo 0.6.1.5.
if not hasattr(np, "row_stack"):
    np.row_stack = np.vstack
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize
from pymoo.operators.sampling.lhs import LHS
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from kroc_mobo.config import load_config, bounds
from kroc_mobo.simulation import simulate
OUT=Path(__file__).resolve().parent/'results'
OUT.mkdir(exist_ok=True)
C=load_config(ROOT/'configs/canonical_final.toml')
SPEC=dict(optimizer='pymoo NSGA-II 0.6.1.5', population=16, generations=4,
          evaluations=64, optimizer_seeds=[731,732,733], train_seeds=[51001,51002],
          validation_seeds=[61001,61002], test_seeds=[71001,71002,71003],
          payload=1.0, iae_targets=[0.005,0.01,0.025], target_relative_tolerance=0.10,
          matched_relative_tolerance=0.05, fixed_gains=[70.,30.,5.],
          tests=[['nominal',5.,0.,1.0471975512],['short45',4.,0.,np.pi/4],['reverse45',6.,0.,-np.pi/4]],
          metric_sampling='all n+1 control-grid samples including t=0,T; IAE=sum(abs(error))*dt; CAV=sum(abs(diff(torque))); torque2=trapezoid(torque**2,t)',
          torque_definition='eta*N*Kt*current: delivered electromagnetic joint torque, not net acceleration torque',
          source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), config=C)
(OUT/'config.json').write_text(json.dumps(SPEC,indent=2))
raw=[]; candidates=[]; traces=[]
MET=['IAE','CAV','torque_rms','peak_torque','torque2_integral']
def metric(trace,metrics,c):
    dt=c['simulation']['control_dt']; p=c['plant']
    tau=p['eta']*p['N']*p['K_t']*trace.current.to_numpy()
    tq=np.trapezoid(tau*tau,trace.t)
    return dict(IAE=float(np.abs(trace.error).sum()*dt),CAV=float(np.abs(np.diff(tau)).sum()),
                torque_rms=float(np.sqrt(tq/c['simulation']['duration'])),peak_torque=float(np.abs(tau).max()),
                torque2_integral=float(tq),feasible=metrics['feasible'],constraint_margin=metrics['constraint_margin'],
                max_current=metrics['max_current'],violation=metrics['violation'],numerical_failure=metrics['numerical_failure'])
def assess(g,ss,phase,tag,c=C,save_trace=False):
    rows=[]
    for seed in ss:
        r=simulate(g,1.,c,seed,record=True)
        if r.metrics['numerical_failure']:
            m={k:float('nan') for k in MET}; m.update(feasible=False,constraint_margin=1e6,max_current=r.metrics['max_current'],violation=r.metrics['violation'],numerical_failure=True)
        else:m=metric(r.trace,r.metrics,c)
        row=dict(phase=phase,tag=tag,noise_seed=seed,kp=g[0],ki=g[1],kd=g[2],**m)
        raw.append(row); rows.append(row)
        if save_trace:
            tr=r.trace.copy(); p=c['plant'];tr['torque']=p['eta']*p['N']*p['K_t']*tr.current
            tr.to_csv(OUT/f'trace_{tag}_{seed}.csv.gz',index=False,compression='gzip')
    return {**{k:float(np.mean([r[k] for r in rows])) for k in MET},'feasible':all(r['feasible'] for r in rows),'constraint_margin':max(r['constraint_margin'] for r in rows)}
class Problem(ElementwiseProblem):
    def __init__(self,obj,seed):
        b=bounds(C);super().__init__(n_var=3,n_obj=2,n_ieq_constr=1,xl=b[:,0],xu=b[:,1]);self.obj=obj;self.seed=seed;self.rows=[]
    def _evaluate(self,x,out,*args,**kwargs):
        ident=f'{self.obj}_{self.seed}_{len(self.rows):03d}'
        m=assess(x,SPEC['train_seeds'],'train',ident)
        row=dict(objective=self.obj,optimizer_seed=self.seed,candidate=len(self.rows),tag=ident,kp=x[0],ki=x[1],kd=x[2],**m)
        self.rows.append(row);out['F']=np.nan_to_num([m['IAE'],m[self.obj]],nan=1e12);out['G']=[max(m['constraint_margin'],0) if not m['feasible'] else -1e-12]
selected=[]; selection_status=[]
for seed in SPEC['optimizer_seeds']:
    val={}
    for obj in ['CAV','torque2_integral']:
        p=Problem(obj,seed)
        minimize(p,NSGA2(pop_size=16,sampling=LHS(),crossover=SBX(prob=0.9,eta=15),mutation=PM(eta=20),eliminate_duplicates=True),('n_gen',4),seed=seed,verbose=False)
        assert len(p.rows)==64
        candidates.extend(p.rows)
        print(f'{obj} seed={seed}: {len(p.rows)} evaluations, {sum(r["feasible"] for r in p.rows)} feasible',flush=True)
        vs=[]
        for r in p.rows:
            if r['feasible']:
                m=assess([r['kp'],r['ki'],r['kd']],SPEC['validation_seeds'],'validation',r['tag'])
                vs.append({**r,**m})
        val[obj]=pd.DataFrame(vs)
    # Common LHS initial population is paired exactly; subsequent proposals may diverge.
    a=[r for r in candidates if r['optimizer_seed']==seed and r['objective']=='CAV'][:16]
    b=[r for r in candidates if r['optimizer_seed']==seed and r['objective']=='torque2_integral'][:16]
    assert np.array_equal([[r[k] for k in ['kp','ki','kd']] for r in a],[[r[k] for k in ['kp','ki','kd']] for r in b])
    for target in SPEC['iae_targets']:
        pair=[]
        for obj,v in val.items():
            if v.empty:continue
            pool=v[v.feasible & (abs(v.IAE/target-1)<=0.10)]
            if len(pool):pair.append(pool.sort_values([obj,'IAE','candidate']).iloc[0].to_dict())
        status=dict(optimizer_seed=seed,target=target,n_selected=len(pair),validation_matched=False)
        if len(pair)==2:
            mismatch=abs(pair[0]['IAE']-pair[1]['IAE'])/((pair[0]['IAE']+pair[1]['IAE'])/2)
            status.update(validation_relative_IAE_gap=mismatch,validation_matched=mismatch<=0.05)
            for r in pair:selected.append(dict(**r,target=target,validation_matched=mismatch<=0.05))
        selection_status.append(status)
# No test information used for controller selection.
test=[]
for r in selected+[dict(objective='fixed',optimizer_seed=-1,target=-1,kp=70.,ki=30.,kd=5.,tag='fixed',validation_matched=False)]:
    for name,dur,start,end in SPEC['tests']:
        c=deepcopy(C);c['simulation'].update(duration=dur,theta_start=start,theta_end=end)
        tag=f'{r["tag"]}_target{r["target"]}_{name}'
        m=assess([r['kp'],r['ki'],r['kd']],SPEC['test_seeds'],'test',tag,c,save_trace=True)
        test.append({**{k:r[k] for k in ['objective','optimizer_seed','target','kp','ki','kd','validation_matched']},'trajectory':name,**m})
A=pd.DataFrame(candidates);T=pd.DataFrame(test)
A.to_csv(OUT/'candidates.csv',index=False);pd.DataFrame(raw).to_csv(OUT/'raw_rollouts.csv',index=False)
pd.DataFrame(selected).to_csv(OUT/'selected.csv',index=False);pd.DataFrame(selection_status).to_csv(OUT/'selection_status.csv',index=False);T.to_csv(OUT/'test_summary.csv',index=False)
pairs=[]
for (seed,target,name),g in T[T.objective!='fixed'].groupby(['optimizer_seed','target','trajectory']):
    a=g[g.objective=='CAV'].iloc[0];b=g[g.objective=='torque2_integral'].iloc[0]
    gap=abs(a.IAE-b.IAE)/((a.IAE+b.IAE)/2)
    pairs.append(dict(optimizer_seed=seed,target=target,trajectory=name,validation_matched=bool(a.validation_matched),test_relative_IAE_gap=gap,test_matched=gap<=.05,both_feasible=bool(a.feasible and b.feasible),same_gains=bool(np.array_equal(a[['kp','ki','kd']].to_numpy(),b[['kp','ki','kd']].to_numpy())),**{f'{k}_B_minus_A':b[k]-a[k] for k in MET},**{f'{k}_{side}':row[k] for side,row in [('A',a),('B',b)] for k in MET}))
P=pd.DataFrame(pairs);P.to_csv(OUT/'paired_comparison.csv',index=False)
fig,axes=plt.subplots(1,2,figsize=(10,4))
for obj,g in A[A.feasible].groupby('objective'):
    axes[0].scatter(g.IAE,g.CAV,label=obj,s=12,alpha=.5);axes[1].scatter(g.IAE,g.torque2_integral,label=obj,s=12,alpha=.5)
for ax in axes:ax.set_xlabel('Training IAE [rad s]');ax.legend(fontsize=8);ax.grid(alpha=.2)
axes[0].set_ylabel('CAV [N m]');axes[1].set_ylabel('Torque squared integral [N² m² s]');fig.tight_layout();fig.savefig(OUT/'common_axes.png',dpi=170);plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(12,3.8))
for ax,k in zip(axes,['CAV','torque_rms','peak_torque']):
    for name,g in P.groupby('trajectory'):
        ax.scatter(g.test_relative_IAE_gap*100,g[f'{k}_B_minus_A'],label=name)
    ax.axvline(5,color='gray',ls='--');ax.axhline(0,color='gray',lw=.7);ax.set_xlabel('Test IAE gap [%]');ax.set_ylabel(f'{k}: B minus A');ax.grid(alpha=.2)
axes[0].legend(fontsize=7);fig.tight_layout();fig.savefig(OUT/'matched_iae_test.png',dpi=170);plt.close(fig)
(OUT/'environment.txt').write_text(platform.platform()+'\n'+sys.version+'\n'+subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
print('Selected pairs:',len(selected)//2,'; test paired rows:',len(P),'; matched test rows:',sum(P.test_matched) if len(P) else 0,flush=True)
# Algebraic/constraint sanity checks independent of optimization rankings.
assert np.isclose(np.sum(np.abs(np.diff([0.,1.,-1.]))),3.)
assert np.isclose(np.trapezoid(np.array([2.,2.,2.])**2,dx=.5),4.)
for r in raw:
    if r['phase']=='test' and not r['numerical_failure']:
        duration=next(x[1] for x in SPEC['tests'] if r['tag'].endswith('_'+x[0]))
        assert np.isclose(r['torque_rms']**2*duration,r['torque2_integral'])
checks=dict(expected_candidates=384,actual_candidates=len(A),paired_initial_population=True,metric_identities_passed=True,test_feasible=int(T.feasible.sum()),test_total=len(T))
assert len(A)==384
(OUT/'checks.json').write_text(json.dumps(checks,indent=2))
(OUT/'sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.name!='sha256.json'},indent=2))
