"""Bounded per-asset incremental replica of the locked nominal features."""
from collections import deque
import numpy as np
from .thermal_model import equilibrium,evolve
from .data_quality_250kVA import SIGNALS
IRATED=250000/(np.sqrt(3)*433);VNOM=433/np.sqrt(3)

def finite(x):return x is not None and np.isfinite(x)
def nullable_persistence(values,n):
 if len(values)<n or any(x is None for x in list(values)[-n:]):return None
 return all(list(values)[-n:])

class RollingMean:
 """Compensated add/remove accumulator matching the frozen pandas rolling mean."""
 def __init__(self,n):
  self.n=n;self.values=deque();self.count=0;self.total=0.;self.add_comp=0.;self.remove_comp=0.;self.negative=0;self.consecutive=0;self.previous=np.nan
 def push(self,value):
  if len(self.values)==self.n:
   old=self.values.popleft()
   if np.isfinite(old):
    self.count-=1;y=-old-self.remove_comp;t=self.total+y;self.remove_comp=t-self.total-y;self.total=t;self.negative-=int(np.signbit(old))
  self.values.append(float(value))
  if np.isfinite(value):
   self.count+=1;y=value-self.add_comp;t=self.total+y;self.add_comp=t-self.total-y;self.total=t;self.negative+=int(np.signbit(value))
   self.consecutive=self.consecutive+1 if value==self.previous else 1;self.previous=value
 def mean(self):
  if self.count<self.n//2:return np.nan
  result=self.total/self.count
  if self.consecutive>=self.count:return self.previous
  if self.negative==0 and result<0:return 0.
  if self.negative==self.count and result>0:return 0.
  return result

class FeatureState:
 def __init__(self,reference,display_calibration):
  self.reference=reference;self.calibration=display_calibration
  self.samples=0;self.initialized=0;self.expected=None;self.display_expected=None;self.eq=None;self.display_eq=None
  self.drivers=[None]*7;self.oil=deque(maxlen=73);self.load=deque(maxlen=72);self.ambient=deque(maxlen=72);self.residual=deque(maxlen=13)
  self.nominal_history=deque(maxlen=12);self.good=deque(maxlen=12);self.phases=[deque(maxlen=3) for _ in range(3)];self.imbalance=deque(maxlen=3)
  self.means={name+str(n):RollingMean(n) for n in [36,72] for name in ['loading','ambient']}
 def step(self,row):
  x=np.array([row[name] if row[name] is not None else np.nan for name in SIGNALS],float);v=x[:3];i=x[3:6];ambient=x[6];oil=x[7]
  vm=v.mean();im=i.mean()
  with np.errstate(divide='ignore',invalid='ignore'):
   vi=np.max(np.abs(v-vm))/vm*100;ii=0. if im==0 else np.max(np.abs(i-im))/im*100
  load=np.sum(v*i)/2500;valid=bool(np.isfinite(x).all() and row['communication_available'] is True)
  current_eq=None
  for k in range(7):
   if np.isfinite(x[k]):self.drivers[k]=float(x[k])
  if all(finite(z) for z in self.drivers):
   current_eq=equilibrium(self.drivers[:3],self.drivers[3:6],self.drivers[6],self.reference)
   current_display_eq=equilibrium(self.drivers[:3],self.drivers[3:6],self.drivers[6],self.calibration)
  else:current_display_eq=None
  if finite(self.expected) and finite(self.eq):self.expected=evolve(self.expected,self.eq,self.reference['tau_min'])
  elif finite(oil) and finite(current_eq):self.expected=float(oil)
  if finite(self.display_expected) and finite(self.display_eq):self.display_expected=evolve(self.display_expected,self.display_eq,self.calibration['tau_min'])
  elif finite(oil) and finite(current_display_eq):self.display_expected=float(oil)
  self.eq=current_eq;self.display_eq=current_display_eq
  if finite(self.expected):self.initialized+=1
  f={'mean_phase_voltage_V':vm,'voltage_imbalance_pct':vi,'loading_pct':load,'max_phase_loading_pct':i.max()/IRATED*100,'current_imbalance_pct':ii,'ambient_temp_C':ambient,'top_oil_temp_C':oil,'oil_rise_K':oil-ambient}
  for n in [6,12]:f[f'oil_change_{n*5}min_C']=oil-self.oil[-n] if len(self.oil)>=n else np.nan
  for n in [36,72]:
   for name,buffer in [('loading',self.load),('ambient',self.ambient)]:
    f[f'past_{name}_mean_{n*5}min_'+('pct' if name=='loading' else 'C')]=self.means[name+str(n)].mean()
  f['nominal_oil_residual_C']=oil-self.expected if finite(self.expected) else np.nan
  jump=bool(len(self.oil) and np.isfinite(oil) and np.isfinite(self.oil[-1]) and abs(oil-self.oil[-1])>2.5)
  self.oil.append(float(oil));self.nominal_history.append(self.expected if finite(self.expected) else np.nan)
  plateau=False
  if len(self.oil)>=12 and len(self.nominal_history)==12:
   a=np.array(list(self.oil)[-12:]);ex=np.array(self.nominal_history)
   plateau=bool(np.isfinite(a).all() and np.isfinite(ex).all() and a.max()==a.min() and ex.max()-ex.min()>1)
  suspect=jump or plateau;self.good.append(valid and not suspect)
  assessable=bool(valid and not suspect and len(self.good)==12 and all(self.good) and self.initialized>288)
  for k in range(3):self.phases[k].append(bool(i[k]>1.1*IRATED) if np.isfinite(i[k]) else None)
  phase_flags=[nullable_persistence(z,3) for z in self.phases]
  phase=True if True in phase_flags else None if None in phase_flags else False
  uv=True if np.any(np.isfinite(v)&(v<.9*VNOM)) else None if not np.isfinite(v).all() else False
  self.imbalance.append(bool(ii>15) if np.isfinite(ii) else None);imb=nullable_persistence(self.imbalance,3)
  self.load.append(float(load));self.ambient.append(float(ambient));self.residual.append(float(f['nominal_oil_residual_C']));self.samples+=1
  for n in [36,72]:self.means['loading'+str(n)].push(load);self.means['ambient'+str(n)].push(ambient)
  residuals=np.array(self.residual,float);trend=(residuals[-1]-residuals[-7])/30 if len(residuals)>=7 and np.isfinite(residuals[-1]) and np.isfinite(residuals[-7]) else None
  return f,dict(assessable=assessable,sensor_suspect=suspect,valid=valid,warmup=self.initialized<=288,phase=phase,undervoltage=uv,imbalance=imb,expected=self.display_expected,residual=oil-self.display_expected if finite(self.display_expected) and np.isfinite(oil) else None,residual_trend=trend,residual_mean=float(np.nanmean(residuals[-6:])) if np.isfinite(residuals[-6:]).any() else None)
