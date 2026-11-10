import json
import numpy as np
from run import terms,deriv,sim,OUT
rng=np.random.default_rng(982);res=[]
for _ in range(100):
    q=rng.uniform(-3,3,2);v=rng.normal(size=2);M,C,G=terms(q,v);eps=1e-6
    mdot=(terms(q+eps*v,v)[0]-terms(q-eps*v,v)[0])/(2*eps)
    res.append([np.linalg.eigvalsh(M).min(),abs(v@C-.5*v@mdot@v)])
assert min(x[0] for x in res)>0
assert max(x[1] for x in res)<1e-8
# gravity must be gradient of potential, including cross partial symmetry
q=np.array([.3,.4]);v=np.array([.7,-.2]);eps=1e-6
pot=lambda x:29.43*np.sin(x[0])+4.905*np.sin(x.sum())
grad=np.array([(pot(q+np.eye(2)[j]*eps)-pot(q-np.eye(2)[j]*eps))/(2*eps) for j in range(2)])
assert np.allclose(grad,terms(q,v)[2],atol=1e-8)
# zero velocity, exact gravity hold torque => zero acceleration
assert np.max(np.abs(deriv(np.r_[q,[0.,0.]],terms(q,np.zeros(2))[2])))<1e-10
k=np.array([100.,30.,7.,150.,10.,5.]);lim=np.array([42.,6.])
a=sim(k,lim,trace=True);b=sim(k,lim,trace=True)
assert np.array_equal(a[2],b[2]);assert np.all(np.abs(a[2][:,7:9])<=lim)
assert np.max(np.abs(a[2][:,5:7]-a[2][:,7:9]))>0
# paper printed C second component violates kinetic energy identity
M,C,G=terms(q,v);h=.1*np.sin(q[1]);wrong=C.copy();wrong[1]=h*v[1]**2
mdot=(terms(q+eps*v,v)[0]-terms(q-eps*v,v)[0])/(2*eps)
# failure penalty remains finite and archived
failed=sim(np.zeros(6),lim)[0]
summary=dict(min_mass_eigenvalue=min(x[0] for x in res),max_energy_identity_residual=max(x[1] for x in res),gravity_gradient_error=float(np.max(np.abs(grad-G))),printed_C_energy_residual=float(v@wrong-.5*v@mdot@v),deterministic_trace=True,saturation_verified=True,zero_gain_scores=failed.tolist())
(OUT/'model_checks.json').write_text(json.dumps(summary,indent=2));print(summary)
