import importlib.util,json
from pathlib import Path
import numpy as np
from simulator import sim,terms
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('old',R.parent/'objective-budget-torque-20261110/run.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
k=np.array([120.,40.,8.,180.,2.,7.]);lim=np.array([42.,6.]);checks={}
for task in [0,1,2]:
    a=sim(k,lim,task);b=old.sim(k,lim,task)
    assert np.array_equal(a[0],b[0]) and np.array_equal(a[1],b[1],equal_nan=True)
checks['original_three_task_outputs_bitwise_equal']=True
for task,target,duration in [(3,[.6,.9],3.),(4,[1.,.6],1.),(6,[.9,.8],4.)]:
    _,_,tr=sim(k,lim,task,trace=True)
    assert np.array_equal(tr[0,3:5],np.zeros(2));assert np.allclose(tr[int(duration/.002),3:5],target)
    assert np.max(np.abs(tr[:,7:9])-lim)<1e-12
    assert np.any(np.abs(tr[:,5:7]-tr[:,7:9])>1e-6)
checks['new_smooth_endpoints_and_real_actuator_clipping']=True
# Algebraic mechanics at generic states, independent finite differences.
rng=np.random.default_rng(123);mineig=1.;residual=0.
for _ in range(100):
    q=rng.uniform(-3,3,2);v=rng.normal(size=2);M,c,g=terms(q,v);mineig=min(mineig,np.linalg.eigvalsh(M).min());eps=1e-6
    mdot=(terms(q+eps*v,v)[0]-terms(q-eps*v,v)[0])/(2*eps)
    residual=max(residual,abs(v@mdot@v-2*v@c))
    def potential(q):return 29.43*np.sin(q[0])+4.905*np.sin(q.sum())
    grad=np.array([(potential(q+np.eye(2)[j]*eps)-potential(q-np.eye(2)[j]*eps))/(2*eps) for j in range(2)])
    assert np.max(abs(grad-g))<1e-7
assert mineig>0 and residual<1e-7
checks.update(minimum_mass_eigenvalue=mineig,max_energy_identity_residual=residual,gravity_gradient_verified=True,validation_simulator_calls=9)
(R/'validation.json').write_text(json.dumps(checks,indent=2));print(checks)
