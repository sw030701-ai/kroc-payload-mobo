"""Additional paired-noise diagnostics and audit of candidate divergence."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent/'results'
R=pd.read_csv(O/'raw_rollouts.csv');S=pd.read_csv(O/'selected.csv');A=pd.read_csv(O/'candidates.csv')
rows=[]
for (seed,target),g in S.groupby(['optimizer_seed','target']):
    for trajectory in ['nominal','short45','reverse45']:
        arm={r.objective:R[(R.phase=='test') & (R.tag==f'{r.tag}_target{target}_{trajectory}')].set_index('noise_seed') for r in g.itertuples()}
        for noise in [71001,71002,71003]:
            a=arm['CAV'].loc[noise];b=arm['torque2_integral'].loc[noise]
            gap=abs(a.IAE-b.IAE)/((a.IAE+b.IAE)/2)
            rows.append(dict(optimizer_seed=seed,target=target,trajectory=trajectory,noise_seed=noise,relative_IAE_gap=gap,test_matched=gap<=.05,both_feasible=bool(a.feasible and b.feasible),**{k+'_B_minus_A':b[k]-a[k] for k in ['IAE','CAV','torque_rms','peak_torque','torque2_integral']}))
pd.DataFrame(rows).to_csv(O/'paired_test_noise.csv',index=False)
aud=[]
for seed,g in A.groupby('optimizer_seed'):
    a=g[g.objective=='CAV'].sort_values('candidate');b=g[g.objective=='torque2_integral'].sort_values('candidate')
    same=np.all(a[['kp','ki','kd']].to_numpy()==b[['kp','ki','kd']].to_numpy(),axis=1)
    aud.append(dict(optimizer_seed=int(seed),identical_initial=int(same[:16].sum()),identical_later=int(same[16:].sum()),total=64))
(O/'candidate_audit.json').write_text(json.dumps(aud,indent=2))
(O/'sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.iterdir()) if p.name!='sha256.json'},indent=2))
print(pd.DataFrame(aud).to_string(index=False))
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/kroc-pilot-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=pd.read_csv(O/'paired_comparison.csv')
fig,axes=plt.subplots(1,3,figsize=(12,4.1))
for ax,k,label in zip(axes,['CAV','torque_rms','peak_torque'],['CAV [N m]','Torque RMS [N m]','Peak torque [N m]']):
    for name,color in zip(['nominal','short45','reverse45'],['tab:blue','tab:green','tab:orange']):
        for valid,marker in [(True,'o'),(False,'x')]:
            g=P[(P.trajectory==name)&(P.validation_matched==valid)]
            ax.scatter(g.test_relative_IAE_gap*100,g[f'{k}_B_minus_A'],color=color,marker=marker,label=name if valid else None)
    ax.axvline(5,color='gray',ls='--');ax.axhline(0,color='gray',lw=.7);ax.set_xlabel('Test IAE gap [%]');ax.set_ylabel(label+': B minus A');ax.grid(alpha=.2)
axes[0].legend(fontsize=7)
fig.suptitle('Circle: validation IAE matched; cross: validation mismatch. All test pairs shown.',fontsize=10)
fig.tight_layout();fig.savefig(O/'matched_iae_test.png',dpi=170);plt.close(fig)
assert (R.feasible==(R.constraint_margin<=0)).all()
(O/'sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.iterdir()) if p.name!='sha256.json'},indent=2))
