import json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
from run import sim,OUT,NAMES
# Fixed gains transcribed from Eltayeb Table 5, never used as optimization warm starts.
gains={'ISE':[147.1182,43.1268,9.9803,198.0562,.7428,9.9872], 'IAE':[68.7215,49.8198,9.7411,193.5716,.5723,3.2319], 'ITAE':[57.2846,49.0422,6.7107,181.3745,.6170,4.7110], 'ITSE':[192.9441,42.0097,9.6103,126.4812,.8804,9.8813]}
rows=[]
for name,k in gains.items():
    for condition,lim in [('infinite_diagnostic',[np.inf,np.inf]),('nominal',[70.,10.]),('reduced',[42.,6.])]:
        s,m,_=sim(np.array(k),np.array(lim));rows.append(dict(source_gain=name,condition=condition,**dict(zip(NAMES,s)),rmse=m[0],settling=m[2],overshoot=m[3],peak_requested=m[4],peak_applied=m[5],saturation_duty=m[6],numerical_ok=m[7],tracking_feasible=m[8]))
pd.DataFrame(rows).to_csv(OUT/'paper_gain_sanity.csv',index=False)
prov={
'Eltayeb2024':dict(doi='10.3390/automation5030014',original='https://www.mdpi.com/2673-4052/5/3/14',checked='Full HTML eq1, eq5-8, Tables2-5,7-9; 2026-11-10',model_values=dict(l1=.2,l2=.1,m1=10,m2=5,g=9.81),paper_GA=dict(population=100,generations=100,crossover=.8,mutation=.01),paper_gain_bounds=dict(kp=[0,200],ki=[0,50],kd=[0,10]),paper_gains=gains,reproduction='Parameter-matched corrected-model benchmark ONLY; not original Simulink reproduction. Printed C2 uses dq2² instead of dq1². Printed gravity uses cos(q1)cos(q2) instead of cos(q1+q2); nonconservative mixed partials. Source implementation may differ from printing; cannot infer actual authors code. Solver, derivative kick implementation, RNG seed, precise cost joint aggregation insufficient for exact table reproduction.'),
'MassoudLibby2024':dict(doi='10.1109/ACCESS.2024.3480834',original='https://www.researchgate.net/publication/384914809_Comparative_Analysis_of_Evolutionary_Algorithms_for_PID_Controller_Optimization_in_Pneumatic_Soft_Robotic_Systems_A_Simulation_and_Experimental_Study',checked='Full-text author upload HTML sections II–VI and Algorithm5; downloadable PDF returned403.',facts='GA/PSO/SA/SBO × IAE/ISE/ITAE/ITSE; PWM valve pressure PID, measured data50s for nonlinear System Identification model;12PSI simulation test;50Hz valve PWM.',limits='Extracted text does not expose numeric table images; exact identified nonlinear plant and complete dataset/code not recovered. Earlier conversation Table6 numeric PSO example not independently revalidated here; excluded from quantitative claims. Pneumatic pressure plant is not manipulator torque plant.'),
'Azeez2023':dict(doi='10.1038/s41598-023-37895-3',original='https://www.nature.com/articles/s41598-023-37895-3.pdf',checked='Downloaded original PDF; Tables1-2 and Optimization of PID gains section, equations24–33, Data availability.',facts='3DOF; each link1kg,.5m,Izz=.020833kgm²; ABC/MGABC colony20,40iterations; bounds [300,100,15] to [550,200,65]; RK4 .001s,5s; torque ±200Nm; LBF compared with IAE,ISE,ITAE,MAE,MRSE (not the identical four-objective set).',limits='Not reproduced: SimMechanics/Simscape model, full trajectory/model setup; datasets available on request. Existing saturation prevents claim that saturation itself is novel.'),
'Zidan2018':dict(doi='10.5220/0006899802400247',original='https://www.scitepress.org/Papers/2018/68998/68998.pdf',checked='Retrieved publisher PDF matches prior attachment SHA256 exactly; pages240–243 and simulation section.',facts='PUMA560 first3 joints,Corke toolbox,IAE and CAV(total variation, despite variance name),40population100iterations,30repeats,0–4s;sudden death high penalty on error/torque violations,real robot oscillation constraints.',limits='Not a 1DOF voltage-motor reproduction; hard rejection constraint is not equivalent to applied torque clipping.')}
for key,fn in [('Azeez2023','azeez-original.pdf'),('Zidan2018','68998.pdf')]:
 p=Path('/tmp/kroc-papers')/fn
 if p.exists():prov[key]['original_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
(OUT.parent/'paper_provenance.json').write_text(json.dumps(prov,ensure_ascii=False,indent=2))
print(pd.DataFrame(rows).to_string(index=False))
