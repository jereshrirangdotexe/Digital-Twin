"""Offline 100 kVA LR bundle. Canonical units, causal history, explicit abstention."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import pandas as pd
import joblib
import voltmind_tournament_runtime as vr
from round2_guarded_predict import calibration_issue

OIL_FEATURES=['inventory_deficit_L','inventory_change_115min_L','inventory_change_30min_L',
 'inventory_mean_60min_L','inventory_std_60min_L','level_fraction','oil_temperature_C','level_flat_samples']
TERMINAL_FEATURES=['terminal_rise_K','current_R_sq_A2','terminal_change_30min_C',
 'ambient_temp_C','terminal_excess_nominal_K']

def normalize(frame):
    f=frame.copy().reset_index(drop=True)
    if 'asset_id' in f and 'replay_id' not in f:f=f.rename(columns={'asset_id':'replay_id'})
    if not {'replay_id','timestamp_IST'}<=set(f):raise ValueError('replay_id and timestamp_IST required')
    if f.empty or f.replay_id.isna().any() or f.replay_id.nunique()!=1:raise ValueError('Exactly one nonempty asset history required')
    ts=pd.to_datetime(f.timestamp_IST,utc=True,errors='raise')
    if ts.isna().any() or (len(ts)>1 and not ts.diff().iloc[1:].eq(pd.Timedelta(minutes=5)).all()):raise ValueError('Ordered unique five-minute grid required; do not interpolate gaps')
    if 'transformer_rating_kva' in f and not pd.to_numeric(f.transformer_rating_kva,errors='coerce').eq(100).all():raise ValueError('100 kVA only')
    bounds={**{c:(0,600 if c.startswith('V') else 1000) for c in vr.RAW[:6]},
      'ambient_temp_C':(-50,180),'top_oil_temp_C':(-50,180),'oil_level_fraction':(0,1),'terminal_R_surface_temp_C':(-50,200)}
    for c,(lo,hi) in bounds.items():
        v=pd.to_numeric(f[c],errors='coerce') if c in f else pd.Series(np.nan,index=f.index)
        f[c]=v.where(np.isfinite(v)&v.between(lo,hi))
    comm=pd.to_numeric(f['communication_available'],errors='coerce').eq(1) if 'communication_available' in f else pd.Series(True,index=f.index)
    f['communication_available']=comm.astype(int)
    f.loc[~comm,list(bounds)]=np.nan
    for col,flag in [('oil_level_fraction','oil_level_sensor_available'),('terminal_R_surface_temp_C','terminal_sensor_available')]:
        # A supplied measurement without a flag is present; an explicit unavailable flag always wins.
        present=pd.to_numeric(f[flag],errors='coerce').eq(1) if flag in f else f[col].notna()
        f.loc[~present,col]=np.nan;f[flag]=(present&f[col].notna()).astype(int)
    return f

def optional_features(frame):
    f=normalize(frame);level=f.oil_level_fraction;oil=f.top_oil_temp_C
    inventory=(190+30*(level-.5))/(1+.000725*(oil-20))
    valid=inventory.notna();history=valid.rolling(24,min_periods=24).sum().eq(24)
    flat=[];last=None;count=0
    for x in level:
        count=count+1 if np.isfinite(x) and last is not None and x==last else (1 if np.isfinite(x) else 0)
        flat.append(count);last=x if np.isfinite(x) else None
    xf=pd.DataFrame({'inventory_deficit_L':190-inventory,
      'inventory_change_115min_L':(inventory-inventory.shift(23)).where(history),
      'inventory_change_30min_L':(inventory-inventory.shift(6)).where(valid.rolling(7,min_periods=7).sum().eq(7)),
      'inventory_mean_60min_L':inventory.rolling(12,min_periods=12).mean(),
      'inventory_std_60min_L':inventory.rolling(12,min_periods=12).std(),
      'level_fraction':level,'oil_temperature_C':oil,'level_flat_samples':flat})
    temp=f.terminal_R_surface_temp_C;ir=f.IR_A;ambient=f.ambient_temp_C
    tf=pd.DataFrame({'terminal_rise_K':temp-ambient,'current_R_sq_A2':ir**2,
      'terminal_change_30min_C':temp.diff(6),'ambient_temp_C':ambient,
      'terminal_excess_nominal_K':temp-ambient-ir**2*.0001*.9})
    tv=temp.notna()&ir.notna()&ambient.notna()
    # Strict continuous windows: a missing measurement breaks optional assessment.
    return {'oil':xf[OIL_FEATURES],'terminal':tf[TERMINAL_FEATURES]}, {'oil':history&xf.notna().all(axis=1),'terminal':tv.rolling(7,min_periods=7).sum().eq(7)&tf.notna().all(axis=1)}

def task_prediction(a,x,ready):
    r=np.asarray(ready,dtype=bool);s=np.full(len(x),np.nan)
    if r.any():s[r]=a['model'].predict_proba(x.loc[r,a['features']])[:,1]
    alarm=vr.sustained((s>=a['threshold'])&r,a['persistence'])
    return s,np.where(r,alarm.astype(float),np.nan)

def predict(frame,cal,bundle):
    f=normalize(frame);out=f[['replay_id','timestamp_IST']].copy()
    issue=calibration_issue(f,cal)
    if issue:
        out['thermal_score_uncalibrated']=np.nan;out['thermal_alert']=np.nan
        out['thermal_assessable']=False;out['thermal_status']=issue
    else:
        x,c=vr.features(f,cal);s,a=task_prediction(bundle['tasks']['thermal'],x,c.assessable)
        out['thermal_score_uncalibrated']=s;out['thermal_alert']=a;out['thermal_assessable']=c.assessable
        out['thermal_status']=np.where(c.assessable,'ASSESSED_SYNTHETIC_RESEARCH','INSUFFICIENT_VALID_HISTORY')
        out['phase_loading_warning']=c.phase_loading_warning;out['undervoltage_warning']=c.undervoltage_warning;out['imbalance_warning']=c.imbalance_warning
    xs,rs=optional_features(f)
    for task in ['oil','terminal']:
        s,a=task_prediction(bundle['tasks'][task],xs[task],rs[task])
        out[task+'_score_uncalibrated']=s;out[task+'_alert']=a;out[task+'_assessable']=rs[task]
        out[task+'_status']=np.where(rs[task],'ASSESSED_SYNTHETIC_RESEARCH','SENSOR_UNAVAILABLE_OR_INSUFFICIENT_HISTORY')
    for task in ['tank_pressure','internal_bushing','mechanical','internal_short_circuit','measured_impedance','measured_hotspot']:
        out[task+'_status']='UNASSESSED_NO_TRAINED_DETECTOR'
    return out

def load_locked(root):
    root=Path(root);lock=json.loads((root/'LOCK_MANIFEST.json').read_text());p=root/lock['primary_artifact']
    if hashlib.sha256(p.read_bytes()).hexdigest()!=lock['sha256']:raise ValueError('Model integrity failure')
    a=joblib.load(p)
    if a.get('rating_kVA')!=100 or a.get('family')!='LogisticRegression':raise ValueError('Model schema mismatch')
    return a

def main():
    p=argparse.ArgumentParser(description='Offline V4 LR inference; canonical volts, amps, Celsius and fraction units required')
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--calibration',type=Path)
    args=p.parse_args();root=Path(__file__).resolve().parent.parent
    if args.input.resolve()==args.output.resolve():raise ValueError('Output cannot overwrite input')
    bundle=load_locked(root);cal=json.loads(args.calibration.read_text()) if args.calibration else None
    f=pd.read_csv(args.input);key='replay_id' if 'replay_id' in f else 'asset_id'
    outputs=[predict(g,cal,bundle) for _,g in f.groupby(key,sort=False)]
    args.output.parent.mkdir(parents=True,exist_ok=True);pd.concat(outputs,ignore_index=True).to_csv(args.output,index=False)

if __name__=='__main__':main()
