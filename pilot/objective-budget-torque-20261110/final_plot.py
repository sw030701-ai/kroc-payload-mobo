import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from run import OUT,NAMES
S=pd.read_csv(OUT/'selected_metrics.csv');X=S[(S.phase=='confirmatory')&(S.budget==1024)]
fig,axs=plt.subplots(1,2,figsize=(10,4),sharex=True)
for ax,task in zip(axs,[1,2]):
 for obj in NAMES:
  d=X[(X.task==task)&(X.objective==obj)].groupby('condition').rmse.agg(['mean','sem']).reindex(['nominal','reduced'])
  ax.errorbar([0,1],d['mean'],yerr=d['sem'],marker='o',capsize=3,label=obj)
 ax.set_xticks([0,1],['Nominal [70,10] Nm','Reduced [42,6] Nm']);ax.set_ylabel('Held-out RMSE [rad]');ax.set_title('Step test' if task==1 else 'Smooth quintic test');ax.grid(alpha=.2)
axs[0].legend(ncol=2);fig.suptitle('All objectives; independently retuned per limit; n=10, mean ± SE');fig.tight_layout();fig.savefig(OUT/'final_ranking.png',dpi=180)
