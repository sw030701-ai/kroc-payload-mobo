from experiment import *
from scipy.integrate import solve_ivp

def potential(q,p):
    m1,m2,l1,l2,r1,r2,I1,I2,g=p
    return (m1*r1+m2*l1)*g*np.sin(q[0])+m2*r2*g*np.sin(q[0]+q[1])

def main():
    rng=np.random.default_rng(771190);rows=[]
    for family in (0,1):
        for mass in (5.,6.):
            p=params(family,mass);errs=[];energy=[];eig=[]
            for _ in range(100):
                q=rng.uniform(-np.pi,np.pi,2);v=rng.normal(size=2);M,C,G=terms(q,v,p)
                h=1e-6;grad=np.array([(potential(q+np.eye(2)[j]*h,p)-potential(q-np.eye(2)[j]*h,p))/(2*h) for j in range(2)])
                errs.append(np.max(np.abs(grad-G)))
                md=(terms(q+h*v,v,p)[0]-terms(q-h*v,v,p)[0])/(2*h)
                energy.append(abs(v@C-.5*v@md@v));eig.append(np.linalg.eigvalsh(M).min())
            assert max(errs)<1e-7 and max(energy)<1e-7 and min(eig)>0
            # Independent scalar mass equations and high-accuracy solver for constant input.
            q=np.array([.3,-.2]);y=np.r_[q,[.1,-.1]];u=np.array([20.,2.])
            def independent(t,y):
                q1,q2,v1,v2=y;m1,m2,l1,l2,r1,r2,I1,I2,g=p
                b=m2*l1*r2;d=I2+m2*r2*r2
                m11=I1+I2+m1*r1*r1+m2*(l1*l1+r2*r2)+2*b*np.cos(q2)
                m12=d+b*np.cos(q2)
                rhs1=u[0]+b*np.sin(q2)*(2*v1*v2+v2*v2)-(m1*r1+m2*l1)*g*np.cos(q1)-m2*r2*g*np.cos(q1+q2)
                rhs2=u[1]-b*np.sin(q2)*v1*v1-m2*r2*g*np.cos(q1+q2)
                a=np.linalg.solve(np.array([[m11,m12],[m12,d]]),[rhs1,rhs2])
                return [v1,v2,*a]
            ref=solve_ivp(independent,[0,.1],y,rtol=1e-11,atol=1e-13).y[:,-1]
            z=y.copy();h=.0005
            for _ in range(200):
                a=deriv(z,u,p);b=deriv(z+h*a/2,u,p);c=deriv(z+h*b/2,u,p);d=deriv(z+h*c,u,p);z+=h*(a+2*b+2*c+d)/6
            err=np.max(np.abs(z-ref));assert err<1e-7
            # Exact compensation balances gravity for any static pose.
            assert np.max(np.abs(deriv(np.r_[q,[0.,0.]],terms(q,np.zeros(2),p)[2],p)))<1e-10
            k=np.array([200.,50.,10.,200.,50.,10.]);lim=limits(family,'tight')
            met,tr=simulate(k,p,params(family,5.),lim,2,trace=True)
            assert met[8]==1 and met[6]>0
            assert np.allclose(tr[:,7:9],np.clip(tr[:,5:7],-lim,lim),atol=1e-12)
            e=tr[:,3:5]-tr[:,1:3]
            assert abs(np.sqrt(np.mean(e**2))-met[0])<1e-12
            assert abs(np.sqrt(np.mean(tr[:,7:9]**2))-met[5])<1e-12
            assert abs(np.mean((tr[:,7:9]/lim)**2)-met[14])<1e-12
            rows.append(dict(family=family,mass=mass,min_eigenvalue=min(eig),potential_gradient_max=max(errs),energy_identity_max=max(energy),independent_solver_max=err,active_saturation_duty=met[6]))
    (ROOT/'validation.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
