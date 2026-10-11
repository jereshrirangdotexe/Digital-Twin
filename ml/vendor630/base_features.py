import math
from collections import deque
from .thermal_model import rated_current,step
FEATURE_NAMES=['residual_C','residual_mean_120_C','residual_slope_C_per_min','residual_std_120_C','residual_fraction_gt8','loading_rms_pu','loading_mean_120_pu','ambient_change_120_C','expected_oil_C','current_imbalance_pct','voltage_imbalance_pct']
class FeatureEngine:
    def __init__(self,config):
        self.c=config;self.history=deque();self.previous=None;self.expected=None;self.valid_minutes=0;self.frozen_minutes=0;self.last_features=None
    def update(self,row):
        dt=0 if self.previous is None else (row['_dt']-self.previous['_dt']).total_seconds()/60
        if self.previous and dt<=0:raise ValueError('Timestamps must increase within each asset/replay')
        problems=list(row['_problems']);gap=dt>30
        if dt>0 and dt<1:problems.append('UNSUPPORTED_SUBMINUTE_THERMAL_SAMPLING')
        if row['communication_available'] is False:problems.append('COMMUNICATION_LOSS')
        if gap:problems.append('TIMESTAMP_GAP')
        prev=self.previous
        if prev and row['top_oil_temp_C'] is not None and prev['top_oil_temp_C'] is not None and 0<dt<=30:
            diff=abs(row['top_oil_temp_C']-prev['top_oil_temp_C'])
            if diff/dt>1.2:problems.append('TEMPERATURE_SPIKE_OR_RECOVERY')
            self.frozen_minutes=self.frozen_minutes+dt if diff==0 else 0
            if self.frozen_minutes>=120:problems.append('FROZEN_TEMPERATURE')
        currents=[row[x] for x in ['IR_A','IY_A','IB_A']];volts=[row[x] for x in ['VR_V','VY_V','VB_V']]
        electrical_valid=all(v is not None for v in currents+volts) and not any('OUT_OF_RANGE' in p for p in problems)
        load=math.sqrt(sum(i*i for i in currents)/3)/rated_current(self.c) if electrical_valid else None
        maxload=max(currents)/rated_current(self.c)*100 if electrical_valid else None
        def imbalance(a):
            mean=sum(a)/3;return max(abs(x-mean) for x in a)/max(mean,1e-9)*100
        ci=imbalance(currents) if electrical_valid else None;vi=imbalance(volts) if electrical_valid else None
        warnings=[]
        if electrical_valid:
            if maxload>100:warnings.append('PHASE_LOADING_WARNING')
            if min(volts)<0.90*self.c['secondary_line_V']/math.sqrt(3):warnings.append('UNDERVOLTAGE_WARNING')
            if ci>15 or vi>3:warnings.append('IMBALANCE_WARNING')
        valid=not problems and electrical_valid
        if valid:
            if self.expected is None:self.expected=row['ambient_temp_C'];self.valid_minutes=0
            elif prev and prev.get('_load') is not None and prev['ambient_temp_C'] is not None:
                self.expected=step(self.expected,prev['ambient_temp_C'],prev['_load'],dt,self.c);self.valid_minutes+=dt
            residual=row['top_oil_temp_C']-self.expected
            self.history.append((row['_dt'],residual,load,row['ambient_temp_C']))
            while self.history and (row['_dt']-self.history[0][0]).total_seconds()>7200:self.history.popleft()
            n=len(self.history);mean=sum(x[1] for x in self.history)/n;std=math.sqrt(sum((x[1]-mean)**2 for x in self.history)/n)
            minutes=(row['_dt']-self.history[0][0]).total_seconds()/60
            self.last_features=[residual,mean,(residual-self.history[0][1])/max(minutes,5),std,sum(x[1]>8 for x in self.history)/n,load,sum(x[2] for x in self.history)/n,row['ambient_temp_C']-self.history[0][3],self.expected,ci,vi]
        else:
            self.last_features=None;residual=None;self.expected=None;self.valid_minutes=0;self.history.clear()
        row['_load']=load;self.previous=row
        ready=valid and self.valid_minutes>=3*max(self.c['tau_heat_min'],self.c['tau_cool_min'])
        return dict(features=self.last_features,ready=ready,expected=self.expected,residual=residual,problems=problems,warnings=warnings,loading=maxload,load=load,current_imbalance=ci,voltage_imbalance=vi)
