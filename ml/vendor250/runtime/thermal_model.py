"""Causal previous-interval zero-order-hold nominal oil state."""
import numpy as np
def equilibrium(voltage,current,ambient,calibration):
 vn=433/np.sqrt(3);ir=250000/(np.sqrt(3)*433)
 loss=calibration['p0_W']*np.mean((np.asarray(voltage)/vn)**2)+calibration['pload_W']*np.mean((np.asarray(current)/ir)**2)
 return np.float64(ambient)+calibration['rise_K']*np.power(loss/(calibration['p0_W']+calibration['pload_W']),calibration['exponent'])+calibration.get('bias_C',0)

def evolve(previous,target,tau_min):return target+(previous-target)*np.exp(-5/tau_min)
