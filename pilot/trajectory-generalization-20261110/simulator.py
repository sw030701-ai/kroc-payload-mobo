import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/kroc-mpl')
import json,time,sys,platform,itertools
from pathlib import Path
import numpy as np
import pandas as pd
from numba import njit
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
NAMES=['IAE','ISE','ITAE','ITSE']
BOUNDS=np.array([200.,50.,10.,200.,50.,10.])
@njit
def terms(q,v):
    h=.1*np.sin(q[1]);c=np.cos(q[1])
    M=np.array([[.65+.2*c,.05+.1*c],[.05+.1*c,.05]])
    C=np.array([-h*(2*v[0]*v[1]+v[1]**2),h*v[0]**2])
    G=np.array([29.43*np.cos(q[0])+4.905*np.cos(q[0]+q[1]),4.905*np.cos(q[0]+q[1])])
    return M,C,G
@njit
def deriv(y,u):
    M,C,G=terms(y[:2],y[2:]);r=u-C-G
    det=M[0,0]*M[1,1]-M[0,1]**2
    return np.array([y[2],y[3],(M[1,1]*r[0]-M[0,1]*r[1])/det,(-M[0,1]*r[0]+M[0,0]*r[1])/det])
@njit
def sim(k,lim,task=0,dt=.002,sub=2,trace=False,derivative_weight=0.):
    n=int(round(10/dt));y=np.zeros(4);z=np.zeros(2);s=np.zeros(4);peakr=0.;peaka=0.;sat=0.;lastbad=-1;over=0.;ok=1.
    data=np.zeros((n if trace else 1,9));target=np.array([1.,.5])
    if task==1:target=np.array([.8,.7])
    if task==2:target=np.array([1.2,.3])
    if task==3 or task==5:target=np.array([.6,.9])
    if task==4:target=np.array([1.,.6])
    if task==6:target=np.array([.9,.8])
    duration=2.
    if task==3:duration=3.
    if task==4:duration=1.
    if task==6:duration=4.
    e=np.zeros(2)
    for i in range(n):
        t=i*dt;r=target.copy();rdot=np.zeros(2)
        if task==2 or task==3 or task==4 or task==6:
            a=min(t/duration,1.);r=target*(10*a**3-15*a**4+6*a**5);rdot=target*(30*a**2-60*a**3+30*a**4)/duration
        e=r-y[:2];u=np.zeros(2);ap=np.zeros(2)
        for j in range(2):
            u[j]=k[3*j]*e[j]+k[3*j+1]*z[j]-k[3*j+2]*y[j+2]+derivative_weight*k[3*j+2]*rdot[j]
            ap[j]=min(max(u[j],-lim[j]),lim[j])
            if abs(u[j])<=lim[j] or e[j]*(u[j]-ap[j])<=0:z[j]+=dt*e[j]
            sat+=(1. if abs(u[j])>lim[j] else 0.)
            peakr=max(peakr,abs(u[j]));peaka=max(peaka,abs(ap[j]))
            over=max(over,(y[j]-target[j])/target[j])
        if max(abs(e[0]),abs(e[1]))>.02:lastbad=i
        s[0]+=dt*np.sum(np.abs(e));s[1]+=dt*np.sum(e**2);s[2]+=dt*t*np.sum(np.abs(e));s[3]+=dt*t*np.sum(e**2)
        if trace:
            data[i,0]=t;data[i,1:3]=y[:2];data[i,3:5]=r;data[i,5:7]=u;data[i,7:9]=ap
        h=dt/sub
        for _ in range(sub):
            a=deriv(y,ap);b=deriv(y+h*a/2,ap);c=deriv(y+h*b/2,ap);d=deriv(y+h*c,ap);y+=h*(a+2*b+2*c+d)/6
        if not np.all(np.isfinite(y)) or np.max(np.abs(y[:2]))>20 or np.max(np.abs(y[2:]))>200:
            ok=0.;break
    settling=(lastbad+1)*dt if lastbad<n-1 and task in (0,1,5) and ok else np.nan
    metrics=np.array([np.sqrt(s[1]/20),s[0],settling,over if task in (0,1,5) else np.nan,peakr,peaka,sat/(2*n),ok,(1. if ok and np.max(np.abs(e))<=.02 else 0.)])
    if not ok:s[:]=1e12
    return s,metrics,data
MET=['rmse','iae','settling','overshoot','peak_requested','peak_applied','saturation_duty','numerical_ok','tracking_feasible']
