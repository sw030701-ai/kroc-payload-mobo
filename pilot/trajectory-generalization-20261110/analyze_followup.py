import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/kroc-mpl')
import json,hashlib,itertools
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent;O=R/'results'
K=['seed','objective','condition','bound','training'];G=['kp1','ki1','kd1','kp2','ki2','kd2']
def stats(x):
    x=np.asarray(x,float);rng=np.random.default_rng(91211);means=x[rng.integers(0,len(x),(10000,len(x)))].mean(axis=1)
    signs=np.array(list(itertools.product([-1,1],repeat=len(x))))
    p=np.mean(np.abs((signs*x).mean(axis=1))>=abs(x.mean())-1e-15)
    return dict(n=len(x),mean=x.mean(),ci_low=np.quantile(means,.025),ci_high=np.quantile(means,.975),sign_flip_p=p,negative_seeds=int(sum(x<0)))
def main():
    C=json.loads((R/'config.json').read_text());A=pd.read_csv(O/'candidates.csv.gz');S=pd.read_csv(O/'selected.csv');T=pd.read_csv(O/'test_metrics.csv');F=pd.read_csv(O/'refinement.csv')
    assert len(A)==24576 and len(S)==256 and len(T)==1024 and len(F)==512
    initial=None
    for key,group in A.groupby(K):
        assert len(group)==(256 if key[-1]=='step' else 128)
        bounds=np.array(C['bounds'][key[-2]],float);normalized=group.head(32)[G].to_numpy()/bounds
        expected=np.random.default_rng(key[0]).random((32,6));assert np.allclose(normalized,expected,rtol=0,atol=1e-14)
    for _,s in S.iterrows():
        mask=np.ones(len(A),bool)
        for k in K:mask&=A[k].eq(s[k])
        group=A[mask & (A.training_rollouts<=s.budget)];idx=group.score.idxmin();row=A.loc[idx]
        assert np.isclose(row.score,s.score,rtol=1e-13);assert np.allclose(row[G].to_numpy(float),s[G].to_numpy(float),rtol=1e-13)
    audit=dict(archive_selection_verified=True,shared_normalized_initial_populations=True,ga_runs=int(A.groupby(K).ngroups),training_rollouts=int(A.groupby(K).training_rollouts.max().sum()),gain_candidates=len(A),failed_candidates=int(sum(~A.numerical_ok)),failed_test_rollouts=int(sum(T.numerical_ok!=1)),failed_refinement_rollouts=int(sum(F.numerical_ok!=1)),maximum_absolute_refinement_relative_change=float(F.relative_change.abs().max()))
    assert audit['training_rollouts']==32768
    assert audit['failed_test_rollouts']==0 and audit['failed_refinement_rollouts']==0, 'No improvement claims allowed with failed final tests'
    (O/'audit.json').write_text(json.dumps(audit,indent=2))
    T.groupby(['objective','condition','bound','training','budget','task'])[['rmse','iae','saturation_duty','tracking_feasible']].agg(['mean','std','count']).to_csv(O/'task_summary.csv')
    P=T[T.task.isin([3,4,6])].groupby(K+['budget'],as_index=False)[['rmse','iae','saturation_duty','tracking_feasible']].mean();P.to_csv(O/'smooth_seed_metrics.csv',index=False)
    P.groupby(['objective','condition','bound','training','budget'])[['rmse','iae','saturation_duty','tracking_feasible']].agg(['mean','std','count']).to_csv(O/'smooth_summary.csv')
    tradeoffs=[]
    for obj,bound in itertools.product(C['objectives'],C['bounds']):
        f=T[(T.objective==obj)&(T.bound==bound)&(T.condition=='reduced')&(T.budget==256)&(T.task==5)].pivot(index='seed',columns='training',values='rmse')
        tradeoffs.append(dict(objective=obj,bound=bound,step_rmse=f.step.mean(),mixed_rmse=f.mixed.mean(),relative_change_percent=100*(f.mixed.mean()/f.step.mean()-1),**stats(f.mixed-f.step)))
    pd.DataFrame(tradeoffs).to_csv(O/'secondary_step_tradeoff.csv',index=False)
    contrasts=[];raw=[]
    for obj,bound,cond,budget in itertools.product(C['objectives'],C['bounds'],C['limits'],C['rollout_budgets']):
        f=P[(P.objective==obj)&(P.bound==bound)&(P.condition==cond)&(P.budget==budget)].pivot(index='seed',columns='training',values='rmse')
        x=f.mixed-f.step
        contrasts.append(dict(objective=obj,bound=bound,condition=cond,budget=budget,step_rmse=f.step.mean(),mixed_rmse=f.mixed.mean(),relative_change_percent=100*(f.mixed.mean()/f.step.mean()-1),primary=cond=='reduced' and budget==256,**stats(x)))
        for seed,v in x.items():raw.append(dict(seed=seed,objective=obj,bound=bound,condition=cond,budget=budget,mixed_minus_step=v))
    D=pd.DataFrame(contrasts);D['holm_primary_p']=np.nan;idx=D[D.primary].sort_values('sign_flip_p').index;last=0
    for rank,i in enumerate(idx):last=max(last,min(1,D.loc[i,'sign_flip_p']*(len(idx)-rank)));D.loc[i,'holm_primary_p']=last
    D.to_csv(O/'training_contrasts.csv',index=False);pd.DataFrame(raw).to_csv(O/'training_seed_contrasts.csv',index=False)
    interactions=[]
    for bound,tr,budget in itertools.product(C['bounds'],C['training'],C['rollout_budgets']):
        f=P[(P.bound==bound)&(P.training==tr)&(P.budget==budget)].pivot(index='seed',columns=['condition','objective'],values='rmse')
        x=(f['reduced','ISE']-f['reduced','IAE'])-(f['nominal','ISE']-f['nominal','IAE'])
        interactions.append(dict(bound=bound,training=tr,budget=budget,kind='objective_x_torque',**stats(x)))
    # Direct interaction differences; differing significance alone is not an interaction.
    Q=P.pivot(index='seed',columns=['bound','training','budget','condition','objective'],values='rmse')
    for bound in C['bounds']:
        def interaction(tr,b):return (Q[bound,tr,b,'reduced','ISE']-Q[bound,tr,b,'reduced','IAE'])-(Q[bound,tr,b,'nominal','ISE']-Q[bound,tr,b,'nominal','IAE'])
        interactions.append(dict(bound=bound,training='mixed-minus-step',budget=256,kind='training_x_objective_x_torque',**stats(interaction('mixed',256)-interaction('step',256))))
        for tr in C['training']:interactions.append(dict(bound=bound,training=tr,budget=256,kind='budget_x_objective_x_torque',**stats(interaction(tr,256)-interaction(tr,128))))
    for tr in C['training']:
        def bybound(bound):return (Q[bound,tr,256,'reduced','ISE']-Q[bound,tr,256,'reduced','IAE'])-(Q[bound,tr,256,'nominal','ISE']-Q[bound,tr,256,'nominal','IAE'])
        interactions.append(dict(bound='double-minus-paper',training=tr,budget=256,kind='bounds_x_objective_x_torque',**stats(bybound('double')-bybound('paper'))))
    A[~A.numerical_ok].to_csv(O/'failed_candidates.csv',index=False)
    pd.DataFrame(interactions).to_csv(O/'exploratory_interactions.csv',index=False)
    hit=[]
    for key,f in S[S.budget==256].groupby(['objective','condition','bound','training']):
        x=f[G].to_numpy()/np.array(C['bounds'][key[2]])
        hit.append(dict(zip(['objective','condition','bound','training'],key))|dict(zip(G,((x<=.01)|(x>=.99)).mean(axis=0))))
    pd.DataFrame(hit).to_csv(O/'gain_boundary_fraction.csv',index=False)
    fig,axes=plt.subplots(2,2,figsize=(10,7),sharey=True)
    for ax,(bound,cond) in zip(axes.flat,itertools.product(C['bounds'],C['limits'])):
        for obj,style in [('IAE','o-'),('ISE','s--')]:
            for tr,color in [('step','tab:blue'),('mixed','tab:orange')]:
                f=P[(P.bound==bound)&(P.condition==cond)&(P.objective==obj)].groupby(['training','budget']).rmse
                m=f.mean().loc[tr];se=f.sem().loc[tr];ax.errorbar(m.index,m, yerr=se,fmt=style,color=color,label=f'{obj}/{tr}')
        ax.set_title(f'{bound} bounds / {cond} torque');ax.set_xlabel('Training simulator rollouts');ax.set_ylabel('Mean unseen smooth RMSE (rad)');ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8);fig.tight_layout();fig.savefig(O/'generalization.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4));p=D[D.primary];labels=p.objective+'/'+p.bound
    ax.errorbar(p['mean'],np.arange(4),xerr=np.array([p['mean']-p.ci_low,p.ci_high-p['mean']]),fmt='o');ax.set_yticks(np.arange(4),labels);ax.axvline(0,color='gray');ax.set_xlabel('Mixed minus step: RMSE (rad), paired 95% bootstrap CI');ax.set_title('Reduced torque, 256 training rollouts, n=8 optimizer seeds');fig.tight_layout();fig.savefig(O/'primary_contrasts.png',dpi=180);plt.close(fig)
    print(json.dumps(audit,indent=2));print(D[D.primary].to_string(index=False));print(pd.DataFrame(interactions).to_string(index=False))
if __name__=='__main__':main()
