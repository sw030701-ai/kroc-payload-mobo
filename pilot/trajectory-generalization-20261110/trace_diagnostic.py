import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/kroc-mpl')
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from simulator import sim
R=Path(__file__).resolve().parent;O=R/'results';S=pd.read_csv(O/'selected.csv');G=['kp1','ki1','kd1','kp2','ki2','kd2']
# Fixed illustrative condition selected before looking at follow-up test results.
fig,axes=plt.subplots(2,1,figsize=(9,6));parts=[]
for training,color in [('step','tab:blue'),('mixed','tab:orange')]:
 s=S[(S.seed==301)&(S.objective=='ISE')&(S.condition=='reduced')&(S.bound=='paper')&(S.training==training)&(S.budget==256)].iloc[0]
 _,_,tr=sim(s[G].to_numpy(float),np.array([42.,6.]),3,trace=True)
 pd.DataFrame(tr,columns=['t','q1','q2','r1','r2','requested1','requested2','applied1','applied2']).to_csv(O/f'trace_{training}.csv.gz',index=False)
 e=tr[:,3:5]-tr[:,1:3];axes[0].plot(tr[:,0],np.sqrt(np.mean(e**2,axis=1)),color=color,label=training)
 axes[1].plot(tr[:,0],tr[:,5],color=color,alpha=.5,linestyle='--',label=training+' requested joint1');axes[1].plot(tr[:,0],tr[:,7],color=color,label=training+' applied joint1')
 for lo,hi in [(0,1),(1,3),(3,10)]:
  mask=(tr[:,0]>=lo)&(tr[:,0]<hi);parts.append(dict(seed=301,objective='ISE',condition='reduced',bound='paper',training=training,task=3,start=lo,end=hi,rmse=np.sqrt(np.mean(e[mask]**2))))
axes[0].set_ylabel('Instant joint RMSE (rad)');axes[1].set_ylabel('Torque (Nm)');axes[1].set_xlabel('Time (s)');axes[1].axhline(42,color='gray');axes[1].axhline(-42,color='gray')
for ax in axes:ax.legend(fontsize=8);ax.grid(alpha=.2)
fig.suptitle('Fixed illustrative seed301 / ISE / reduced / paper / task3');fig.tight_layout();fig.savefig(O/'trace_diagnostic.png',dpi=180);pd.DataFrame(parts).to_csv(O/'trace_segment_errors.csv',index=False)
