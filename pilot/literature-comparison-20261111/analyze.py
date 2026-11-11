import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/kroc-new-mpl')
from experiment import *
import itertools
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

METRICS=['rmse','iae','torque_rms','saturation_duty','tracking_feasible','numerical_ok']

def interval(x,seed):
    x=np.asarray(x,float);rng=np.random.default_rng(seed)
    b=x[rng.integers(0,len(x),(20000,len(x)))].mean(axis=1)
    return float(x.mean()),*np.quantile(b,[.025,.975])

def main():
    out=ROOT/'results';alltests=[];aud=[];sums=[];contrasts=[];seedrows=[];papercontrasts=[]
    for e in range(1,5):
        p=out/f'E{e}';summary=json.loads((p/'summary.json').read_text())
        c=pd.read_csv(p/'candidates.csv');tr=pd.read_csv(p/'train_raw.csv');s=pd.read_csv(p/'selected.csv');t=pd.read_csv(p/'test_raw.csv');r=pd.read_csv(p/'refinement.csv')
        assert len(c)==10240 and len(tr)==20480 and len(s)==40 and len(t)==264 and len(r)==240
        assert c.groupby(['seed','method']).size().eq(256).all()
        assert tr.groupby(['seed','method']).size().eq(512).all()
        assert t[t.seed!=-1].groupby(['seed','method']).size().eq(6).all()
        maxsel=0.;initial=True
        for (seed,method),g in c.groupby(['seed','method']):
            sel=s[(s.seed==seed)&(s.method==method)].iloc[0]
            best=g.iloc[g.score.argmin()]
            maxsel=max(maxsel,float(np.max(abs(sel[GKEYS].to_numpy(float)-best[GKEYS].to_numpy(float)))))
            init=g.iloc[:32][GKEYS].to_numpy()/BOUNDS
            initial=initial and np.allclose(init,np.random.default_rng(seed).random((32,6)),atol=1e-14,rtol=0)
        assert maxsel<1e-12 and initial
        fam=summary['family'];tight=limits(fam,'tight')
        for method in METHODS:
            g=tr[tr.method==method].copy()
            if method=='PEN':
                scores=g.iae/20+np.maximum(0,g.overshoot_percent.fillna(0)-5)**2+5*g.saturation_duty**2+.5*g.normalized_effort
                scores=np.where(g.numerical_ok==1,scores,1e12)
            else:scores=np.where(g.numerical_ok==1,g[method.lower()],1e12)
            actual=g.assign(calc=scores).groupby(['seed','evaluation']).calc.mean()
            cg=c[c.method==method].set_index(['seed','evaluation']).score
            assert np.allclose(actual.sort_index(),cg.sort_index(),atol=1e-9,rtol=1e-10)
        fail=tr[tr.numerical_ok==0];fail.to_csv(p/'failed_train_rollouts.csv',index=False)
        aud.append(dict(experiment=e,train_failures=len(fail),test_failures=int((t.numerical_ok==0).sum()),max_selected_gain_discrepancy=maxsel,initial_rng_match=initial,max_fixed_dt_refinement_rmse_change=float(r.absolute_change.max()),code_sha256=summary['code_sha256'],active_tight_test_fraction=float((t[(t.seed!=-1)&(t['limit']=='tight')].saturation_duty>0).mean())))
        alltests.append(t)
        # first aggregate tasks within seed; trajectories are never independent n
        for kind in ('tight','nominal'):
            for taskgroup,tasks in [('all',[2,3,4]),('step',[2]),('fast',[3]),('sine',[4])]:
                z=t[(t['limit']==kind)&t.task.isin(tasks)]
                zs=z[z.seed!=-1].groupby(['seed','method'])[METRICS].mean().reset_index()
                for _,row in zs.iterrows():seedrows.append(dict(experiment=e,limit=kind,taskgroup=taskgroup,**row.to_dict()))
                for method,g in zs.groupby('method'):
                    for metric in METRICS:
                        mean,lo,hi=interval(g[metric],900000+e)
                        sums.append(dict(experiment=e,limit=kind,taskgroup=taskgroup,method=method,metric=metric,n=len(g),mean=mean,ci_low=lo,ci_high=hi,ci_type='optimizer seed percentile bootstrap'))
                for method,g in z[z.seed==-1].groupby('method'):
                    for metric in METRICS:sums.append(dict(experiment=e,limit=kind,taskgroup=taskgroup,method=method,metric=metric,n=0,mean=g[metric].mean(),ci_low=np.nan,ci_high=np.nan,ci_type='deterministic fixed gain; no seed CI'))
                for method in METHODS:
                    papername='PAPER_'+('IAE' if method=='PEN' else method)
                    fixed=z[(z.seed==-1)&(z.method==papername)][METRICS].mean()
                    tune=zs[zs.method==method]
                    for metric in METRICS:
                        d=tune[metric].to_numpy()-fixed[metric];mean,lo,hi=interval(d,700000+e)
                        papercontrasts.append(dict(experiment=e,limit=kind,taskgroup=taskgroup,contrast=method+'-'+papername,metric=metric,n=len(d),fixed_value=fixed[metric],mean=mean,ci_low=lo,ci_high=hi,interpretation='gain transfer baseline; unequal original tuning budgets; exploratory'))
                a=zs[zs.method=='IAE'].set_index('seed')
                for method in ('ISE','ITAE','ITSE','PEN'):
                    b=zs[zs.method==method].set_index('seed')
                    for metric in METRICS:
                        d=(b[metric]-a[metric]).sort_index().to_numpy();mean,lo,hi=interval(d,800000+e)
                        signs=np.array(list(itertools.product([-1,1],repeat=len(d))))
                        pval=float(np.mean(abs((signs*d).mean(axis=1))>=abs(d.mean())-1e-14))
                        primary=kind=='tight' and taskgroup=='all' and method in ('ISE','PEN') and metric=='rmse'
                        contrasts.append(dict(experiment=e,limit=kind,taskgroup=taskgroup,contrast=method+'-IAE',metric=metric,n=len(d),mean=mean,ci_low=lo,ci_high=hi,negative_seeds=int((d<0).sum()),sign_flip_p=pval,primary=primary))
    S=pd.DataFrame(sums);C=pd.DataFrame(contrasts);P=C[C.primary].copy();order=P.sign_flip_p.sort_values().index;running=0.
    for i,idx in enumerate(order):
        running=max(running,(len(order)-i)*C.loc[idx,'sign_flip_p']);C.loc[idx,'holm_primary_p']=min(1.,running)
    S.to_csv(out/'metric_summary.csv',index=False);C.to_csv(out/'paired_contrasts.csv',index=False)
    C[C.primary].to_csv(out/'primary_contrasts.csv',index=False)
    pd.DataFrame(papercontrasts).to_csv(out/'paper_gain_contrasts.csv',index=False)
    pd.DataFrame(seedrows).to_csv(out/'seed_metrics.csv',index=False)
    pd.concat(alltests).to_csv(out/'all_test_raw.csv',index=False)
    (out/'audit.json').write_text(json.dumps(aud,indent=2))
    fig,ax=plt.subplots(figsize=(8,5));colors={'ISE-IAE':'#2864A0','PEN-IAE':'#B34E29'}
    p=C[C.primary].reset_index(drop=True)
    for i,row in p.iterrows():
        ax.errorbar(row['mean'],i,xerr=[[row['mean']-row.ci_low],[row.ci_high-row['mean']]],fmt='o',color=colors[row.contrast],capsize=4)
    ax.set_yticks(range(len(p)),[f'E{r.experiment} {r.contrast}' for _,r in p.iterrows()]);ax.axvline(0,color='gray',lw=1)
    ax.set_xlabel('Paired test RMSE difference (rad); negative is better')
    ax.set_title('Tight torque: 8 independent seeds, 95% paired bootstrap CI')
    fig.tight_layout();fig.savefig(out/'primary_contrasts.png',dpi=180);plt.close(fig)
    fig,axs=plt.subplots(2,2,figsize=(11,7),sharey=True)
    for e,ax in zip(range(1,5),axs.flat):
        z=S[(S.experiment==e)&(S['limit']=='tight')&(S.taskgroup=='all')&(S.metric=='rmse')].set_index('method')
        names=METHODS+['PAPER_IAE','PAPER_ISE','PAPER_ITAE','PAPER_ITSE'];z=z.loc[names]
        ax.bar(range(len(z)),z['mean'],color=['#2864A0']*5+['#8B939C']*4)
        for i,(_,r) in enumerate(z.iterrows()):
            if np.isfinite(r.ci_low):ax.errorbar(i,r['mean'],yerr=[[r['mean']-r.ci_low],[r.ci_high-r['mean']]],color='black',capsize=2)
        ax.set_xticks(range(len(z)),[x.replace('PAPER_','P:') for x in names],rotation=45,ha='right');ax.set_title(f'E{e}');ax.set_ylabel('Test RMSE (rad)')
    fig.suptitle('Common test tasks and torque; fixed paper gains are transfer baselines')
    fig.tight_layout();fig.savefig(out/'common_benchmark.png',dpi=180);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,4))
    for method in METHODS:
        z=S[(S['limit']=='tight')&(S.taskgroup=='all')&(S.method==method)]
        for ax,metric in zip(axs,['saturation_duty','tracking_feasible']):
            g=z[z.metric==metric].sort_values('experiment');ax.plot(g.experiment,g['mean'],marker='o',label=method);ax.set_xticks(range(1,5));ax.set_xlabel('Experiment')
    axs[0].set_ylabel('Joint-time saturation fraction');axs[1].set_ylabel('Terminal tracking feasibility fraction');axs[1].legend()
    fig.tight_layout();fig.savefig(out/'saturation_feasibility.png',dpi=180);plt.close(fig)
    fig,axs=plt.subplots(2,3,figsize=(12,6))
    for row,task in enumerate((2,4)):
        tr=pd.read_csv(out/'E4'/f'trace_IAE_task{task}.csv.gz')
        for j in (0,1):
            ax=axs[row,j];ax.plot(tr.t,tr[f'r{j+1}'],'--',label='reference',color='#777777');ax.plot(tr.t,tr[f'q{j+1}'],label='actual',color='#2864A0')
            ax.set_ylabel(f'Joint {j+1} angle (rad)');ax.set_xlabel('Time (s)')
        ax=axs[row,2];lim=limits(1,'tight')[0]
        ax.plot(tr.t,tr.requested1,label='requested',color='#B34E29',alpha=.8);ax.plot(tr.t,tr.applied1,label='applied',color='#2864A0')
        ax.axhline(lim,color='gray',ls=':',label='torque limit');ax.axhline(-lim,color='gray',ls=':')
        ax.set_ylabel('Joint 1 torque (Nm)');ax.set_xlabel('Time (s)');ax.legend(fontsize=8)
        axs[row,0].set_title('Step' if task==2 else 'Sine');axs[row,0].legend(fontsize=8)
    fig.suptitle('E4 IAE: first seed 110401, tight torque (representative traces)')
    fig.tight_layout();fig.savefig(out/'trace_examples.png',dpi=180);plt.close(fig)
    print(json.dumps(aud,indent=2));print(C[C.primary].to_string(index=False))

if __name__=='__main__':main()
