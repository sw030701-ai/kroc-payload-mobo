import itertools,json,hashlib,re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run import OUT,ROOT,NAMES,MET,BOUNDS
S=pd.read_csv(OUT/'selected_metrics.csv');C=pd.read_csv(OUT/'candidates.csv.gz')
rng=np.random.default_rng(441)
rows=[];paired=[]
def estimate(x,meta):
    x=np.asarray(x,float);n=len(x);boot=np.mean(x[rng.integers(n,size=(10000,n))],axis=1)
    signs=np.array(list(itertools.product([-1,1],repeat=n)))
    p=np.mean(np.abs(np.mean(signs*x,axis=1))>=abs(x.mean())-1e-15)
    rows.append(dict(**meta,n=n,mean=float(x.mean()),ci_low=float(np.quantile(boot,.025)),ci_high=float(np.quantile(boot,.975)),sign_flip_p=p))
    for i,v in enumerate(x):paired.append(dict(**meta,seed=(101+i if meta['phase']=='exploratory' else 201+i),pair_index=i,value=v))
for phase in S.phase.unique():
    for task in [1,2]:
        X=S[(S.phase==phase)&(S.task==task)]
        for metric in ['rmse','iae']:
            for budget in sorted(X.budget.unique()):
                P=X[X.budget==budget].pivot(index='seed',columns=['condition','objective'],values=metric)
                for a,b in itertools.combinations(NAMES,2):
                    base=dict(phase=phase,task=task,metric=metric,budget=int(budget),a=a,b=b)
                    diffs={}
                    for condition in ['nominal','reduced']:
                        d=(P[(condition,b)]-P[(condition,a)]).to_numpy();diffs[condition]=d
                        estimate(d,dict(**base,contrast=condition))
                    estimate(diffs['reduced']-diffs['nominal'],dict(**base,contrast='objective_x_torque'))
            lo=X[X.budget==32].pivot(index='seed',columns=['condition','objective'],values=metric)
            hi=X[X.budget==X.budget.max()].pivot(index='seed',columns=['condition','objective'],values=metric)
            for a,b in itertools.combinations(NAMES,2):
                d={}
                for condition in ['nominal','reduced']:
                    d[condition]=(hi[(condition,b)]-hi[(condition,a)])-(lo[(condition,b)]-lo[(condition,a)])
                    estimate(d[condition],dict(phase=phase,task=task,metric=metric,budget=int(X.budget.max()),a=a,b=b,contrast=f'objective_x_budget_{condition}'))
                estimate(d['reduced']-d['nominal'],dict(phase=phase,task=task,metric=metric,budget=int(X.budget.max()),a=a,b=b,contrast='objective_x_torque_x_budget'))
R=pd.DataFrame(rows)
# Holm correction within each six-pair family; CIs remain unadjusted.
for _,idx in R.groupby(['phase','task','metric','budget','contrast']).groups.items():
    ix=R.loc[idx].sort_values('sign_flip_p').index;p=R.loc[ix,'sign_flip_p'].to_numpy();adj=np.minimum(1,np.maximum.accumulate(p*np.arange(len(p),0,-1)));R.loc[ix,'holm_p']=adj
R.to_csv(OUT/'paired_contrasts.csv',index=False);pd.DataFrame(paired).to_csv(OUT/'paired_seed_values.csv',index=False)
summary=S.groupby(['phase','task','condition','objective','budget'])[MET].agg(['mean','std','min','max','count']);summary.to_csv(OUT/'metric_summary.csv')
# Budget needed for explicit common targets, no inference beyond measured checkpoints.
thresholds=[]
for key,x in S[S.task!=0].groupby(['phase','seed','task','condition','objective']):
    for threshold in [.05,.1]:
        eligible=x[(x.rmse<=threshold)&(x.numerical_ok==1)]
        thresholds.append(dict(zip(['phase','seed','task','condition','objective'],key))|dict(target_rmse=threshold,first_observed_budget=None if eligible.empty else int(eligible.budget.min())))
pd.DataFrame(thresholds).to_csv(OUT/'budget_targets_descriptive.csv',index=False)
# Validate archive fairness and exact selection: all four objective metrics retained.
GAIN=['kp1','ki1','kd1','kp2','ki2','kd2']
assert len(C)==88064 and len(S)==1416
assert all(C.groupby(['phase','seed','condition','objective']).evaluation.max().to_numpy()==C.groupby(['phase','seed','condition','objective']).size().to_numpy())
for key,x in C.groupby(['phase','seed']):
    init=[g.sort_values('evaluation').head(32)[GAIN].to_numpy() for _,g in x.groupby(['condition','objective'])]
    assert all(np.array_equal(init[0],g) for g in init[1:])
for key,x in S.groupby(['phase','seed','condition','objective']):
    raw=C[(C.phase==key[0])&(C.seed==key[1])&(C.condition==key[2])&(C.objective==key[3])]
    for _,r in x[x.task==0].iterrows():
        v=raw[raw.evaluation<=r.budget].score.min();assert np.isclose(r.train_score,v,rtol=1e-13)
# Incumbent own training fitness monotonic, held-out metric need not be.
monotonic=all(np.all(np.diff(x.sort_values('budget').train_score)<=1e-10) for _,x in S[S.task==0].groupby(['phase','seed','condition','objective']))
assert monotonic
fail=C[C.numerical_ok!=1];fail.to_csv(OUT/'failed_candidates.csv',index=False)
B=S[(S.phase=='confirmatory')&(S.budget==1024)]
boundary=np.mean((B[GAIN].to_numpy()/BOUNDS>.99)|(B[GAIN].to_numpy()/BOUNDS<.01),axis=0)
audit=dict(candidate_count=len(C),optimizer_runs=C.groupby(['phase','seed','condition','objective']).ngroups,selected_rollouts=len(S),failed_numerical_candidates=len(fail),candidate_tracking_feasible=int(C.tracking_feasible.sum()),same_initial_populations=True,selection_matches_archive=True,monotonic_own_training=True,final_gain_boundary_fraction=dict(zip(GAIN,boundary)),confirmatory_test_numerical_failures=int((B[B.task!=0].numerical_ok!=1).sum()))
(OUT/'audit.json').write_text(json.dumps(audit,indent=2))
# Clean journal-like overview, mean±seed SE (explicitly not CI).
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(2,2,figsize=(10,7),sharex=True)
for row,task in enumerate([1,2]):
    for col,condition in enumerate(['nominal','reduced']):
        ax=axs[row,col];X=S[(S.phase=='confirmatory')&(S.task==task)&(S.condition==condition)]
        for name in NAMES:
            a=X[X.objective==name].groupby('budget').rmse.agg(['mean','sem']);ax.errorbar(a.index,a['mean'],yerr=a['sem'],marker='o',capsize=2,label=name)
        ax.set_title(f'{condition}: '+('held-out step' if task==1 else 'held-out quintic'));ax.set_xscale('log',base=2);ax.set_ylabel('RMSE [rad]');ax.grid(alpha=.2)
        if row==1:ax.set_xlabel('Candidate evaluations')
axs[0,0].legend(ncol=2);fig.suptitle('Independent confirmatory seeds n=10; mean ± SE');fig.tight_layout();fig.savefig(OUT/'budget_rmse.png',dpi=180);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(10,4))
for ax,task in zip(axs,[1,2]):
    d=R[(R.phase=='confirmatory')&(R.task==task)&(R.metric=='rmse')&(R.a=='IAE')&(R.b=='ITAE')&(R.contrast=='objective_x_torque')].sort_values('budget')
    ax.errorbar(d.budget,d['mean'],yerr=np.array([d['mean']-d.ci_low,d.ci_high-d['mean']]),marker='o',capsize=3);ax.axhline(0,color='black',lw=1);ax.set_xscale('log',base=2);ax.set_title('step' if task==1 else 'quintic');ax.set_xlabel('Candidate evaluations');ax.set_ylabel('(ITAE−IAE) reduced − nominal [rad]');ax.grid(alpha=.2)
fig.suptitle('Paired objective × torque contrast; 95% bootstrap CI (unadjusted)');fig.tight_layout();fig.savefig(OUT/'interaction.png',dpi=180);plt.close(fig)
fig,axs=plt.subplots(2,2,figsize=(10,6),sharex=True)
for col,condition in enumerate(['nominal','reduced']):
    tr=pd.read_csv(OUT/f'trace_{condition}.csv.gz')
    for j in [1,2]:
        axs[0,col].plot(tr.t,tr[f'q{j}'],label=f'q{j}');axs[0,col].plot(tr.t,tr[f'r{j}'],'--',alpha=.5)
        axs[1,col].plot(tr.t,tr[f'requested{j}'],label=f'requested{j}');axs[1,col].plot(tr.t,tr[f'applied{j}'],'--',label=f'applied{j}')
    axs[0,col].set_title(condition);axs[0,col].set_ylabel('Angle [rad]');axs[1,col].set_ylabel('Torque [Nm]');axs[1,col].set_xlabel('Time [s]');axs[0,col].legend();axs[1,col].legend(fontsize=8)
fig.suptitle('Prespecified example: seed201, IAE, budget1024, held-out step');fig.tight_layout();fig.savefig(OUT/'trace.png',dpi=180);plt.close(fig)
times=[]
for line in (ROOT/'execution.log').read_text().splitlines():
    a=line.split()
    if len(a)==6:times.append(dict(phase=a[0],seed=int(a[1]),condition=a[2],objective=a[3],evaluations=int(a[4]),seconds=float(a[5])))
pd.DataFrame(times).to_csv(OUT/'execution_times.csv',index=False)
print(json.dumps(audit,indent=2));print(B[B.task!=0].groupby(['task','condition','objective'])[['rmse','iae','saturation_duty','tracking_feasible']].mean().to_string())
print(R[(R.phase=='confirmatory')&(R.metric=='rmse')&(R.a=='IAE')&(R.b=='ITAE')].to_string(index=False))
