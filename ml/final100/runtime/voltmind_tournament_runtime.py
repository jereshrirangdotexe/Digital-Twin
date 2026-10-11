"""Causal V3 challenger features. Oracle labels and profiles never enter this module."""
import math
from pathlib import Path
import numpy as np
import pandas as pd
import joblib, json, hashlib

RAW=['VR_V','VY_V','VB_V','IR_A','IY_A','IB_A','ambient_temp_C','top_oil_temp_C']
IRATED=100000/(math.sqrt(3)*433)
FOUR=['residual_C','residual_mean_30min_C','residual_mean_60min_C','residual_change_30min_C']
FEATURES=FOUR+['residual_mean_180min_C','residual_std_60min_C','residual_change_5min_C',
 'oil_change_30min_C','oil_change_60min_C','ambient_change_30min_C','load_sq',
 'load_sq_mean_60min','load_sq_change_30min','oil_rise_K','expected_oil_rise_K',
 'current_imbalance_pct','voltage_min_pu','oil_flatline_samples']

def sustained(mask,n=3):
    return pd.Series(np.asarray(mask,dtype=int)).rolling(n,min_periods=n).sum().eq(n).to_numpy()

def features(frame,cal):
    if frame.replay_id.nunique()!=1:raise ValueError('Process exactly one replay at a time')
    if frame.duplicated(['replay_id','timestamp_IST']).any():raise ValueError('Duplicate timestamp')
    ts=pd.to_datetime(frame.timestamp_IST,utc=True)
    if len(ts)>1 and not ts.diff().iloc[1:].eq(pd.Timedelta(minutes=5)).all():raise ValueError('Ordered 5-minute grid required; represent gaps as missing rows')
    b=frame[RAW].astype(float).replace([np.inf,-np.inf],np.nan).reset_index(drop=True)
    comm=frame.communication_available.to_numpy()==1 if 'communication_available' in frame else np.ones(len(b),dtype=bool)
    b.loc[~comm,:]=np.nan
    for c in RAW[:6]:b.loc[(b[c]<0)|(b[c]>(600 if c.startswith('V') else 1000)),c]=np.nan
    for c in RAW[6:]:b.loc[(b[c]<-50)|(b[c]>180),c]=np.nan
    a=b.to_numpy();n=len(a);expected=np.full(n,np.nan);age=np.zeros(n,dtype=int)
    prev_eq=None;prev_state=None;held=None;stale=0;initialized=0
    alpha=math.exp(-5/cal['tau'])
    for k,row in enumerate(a):
        drivers=row[3:7]
        if np.isfinite(drivers).all():held=drivers.copy();stale=0
        else:stale+=1
        if stale>6:prev_state=None;prev_eq=None;initialized=0
        if held is not None and stale<=6:
            eq=held[3]+cal['rise']*(cal['loss_ratio']+(1-cal['loss_ratio'])*np.mean((held[:3]/IRATED)**2))**.8+cal['bias']
            if prev_state is not None and prev_eq is not None:prev_state=alpha*prev_state+(1-alpha)*prev_eq
            elif np.isfinite(row[7]) and comm[k]:prev_state=float(row[7])
            prev_eq=eq
            if prev_state is not None:expected[k]=prev_state;initialized+=1
        age[k]=initialized
    oil=b.top_oil_temp_C;ambient=b.ambient_temp_C;res=oil-pd.Series(expected)
    load2=((b[RAW[3:6]]/IRATED)**2).mean(axis=1,skipna=False)
    im=b[RAW[3:6]].mean(axis=1,skipna=False)
    imbalance=b[RAW[3:6]].sub(im,axis=0).abs().max(axis=1,skipna=False)/im.replace(0,np.nan)*100
    imbalance.loc[im.eq(0)]=0
    flat=np.zeros(n);count=0;previous=None
    for k,v in enumerate(oil):
        count=count+1 if np.isfinite(v) and previous is not None and v==previous else 1 if np.isfinite(v) else 0
        flat[k]=count;previous=v if np.isfinite(v) else None
    jump=oil.diff().abs().gt(4)
    expected_s=pd.Series(expected)
    stuck=(flat>=36)&((expected_s.rolling(36).max()-expected_s.rolling(36).min())>3)
    valid=b.notna().all(axis=1).to_numpy() & comm
    sensor_suspect=jump.to_numpy()|np.asarray(stuck)
    clean=valid & ~sensor_suspect
    ready=sustained(clean,12)&(age>=12)&np.isfinite(expected)
    f=pd.DataFrame({'residual_C':res,'residual_mean_30min_C':res.rolling(6,min_periods=6).mean(),
      'residual_mean_60min_C':res.rolling(12,min_periods=12).mean(),'residual_change_30min_C':res.diff(6),
      'residual_mean_180min_C':res.rolling(36,min_periods=12).mean(),
      'residual_std_60min_C':res.rolling(12,min_periods=6).std(),
      'residual_change_5min_C':res.diff(),'oil_change_30min_C':oil.diff(6),'oil_change_60min_C':oil.diff(12),
      'ambient_change_30min_C':ambient.diff(6),'load_sq':load2,
      'load_sq_mean_60min':load2.rolling(12,min_periods=6).mean(),'load_sq_change_30min':load2.diff(6),
      'oil_rise_K':oil-ambient,'expected_oil_rise_K':expected_s-ambient,
      'current_imbalance_pct':imbalance,'voltage_min_pu':b[RAW[:3]].min(axis=1,skipna=False)/(433/math.sqrt(3)),
      'oil_flatline_samples':flat})
    context=pd.DataFrame({'assessable':ready,'expected_oil_C':expected,'sensor_suspect':sensor_suspect,
      'phase_loading_warning':sustained((b[RAW[3:6]].max(axis=1,skipna=False)>1.1*IRATED).fillna(False),3),
      'undervoltage_warning':b[RAW[:3]].lt(.9*433/math.sqrt(3)).any(axis=1)&valid,
      'imbalance_warning':sustained(imbalance.gt(40).fillna(False),3),'valid_measurements':valid})
    return f[FEATURES],context

def optional_features(frame,optional):
    if not frame[['replay_id','timestamp_IST']].reset_index(drop=True).equals(optional[['replay_id','timestamp_IST']].reset_index(drop=True)):
        raise ValueError('Optional sensor keys do not match core observations')
    level=optional.oil_level_fraction.reset_index(drop=True)
    temp=frame.top_oil_temp_C.reset_index(drop=True)
    ambient=frame.ambient_temp_C.reset_index(drop=True)
    ir=frame.IR_A.reset_index(drop=True)
    terminal=optional.terminal_R_surface_temp_C.reset_index(drop=True)
    # Fixed declared simulator geometry. Different hardware requires new calibration.
    inventory=(30*(level-.5)+190)/(1+.000725*(temp-20))
    oil=pd.DataFrame({'inventory_est_loss_L':190-inventory,'inventory_change_60min_L':inventory.diff(12),
      'level_change_60min':level.diff(12),'top_oil_temp_C':temp,'oil_level_fraction':level})
    terminal_f=pd.DataFrame({'terminal_rise_K':terminal-ambient,'current_R_sq_A2':ir**2,
      'terminal_change_30min_C':terminal.diff(6),'ambient_temp_C':ambient,
      'terminal_excess_nominal_K':terminal-ambient-(ir**2)*.0001*.9})
    return oil,terminal_f

def predict_scores(artifact,f):
    if artifact['kind']=='physics':return f.residual_mean_30min_C.to_numpy()
    return artifact['model'].predict_proba(f[artifact['features']])[:,1]

def predict(frame,cal,artifact):
    f,c=features(frame,cal);scores=predict_scores(artifact,f)
    decision=sustained((scores>=artifact['threshold'])&c.assessable.to_numpy(),artifact['persistence'])
    return pd.DataFrame({'replay_id':frame.replay_id.to_numpy(),'timestamp_IST':frame.timestamp_IST.to_numpy(),
      'thermal_alert':np.where(c.assessable,decision.astype(float),np.nan),
      'thermal_score_uncalibrated':np.where(c.assessable,scores,np.nan),
      'thermal_assessable':c.assessable,'expected_oil_C':c.expected_oil_C,
      'sensor_suspect':c.sensor_suspect,'phase_loading_warning':c.phase_loading_warning,
      'undervoltage_warning':c.undervoltage_warning,'imbalance_warning':c.imbalance_warning})

def load_locked(root):
    root=Path(root);lock=json.loads((root/'LOCK_MANIFEST.json').read_text())
    path=root/lock['primary_artifact']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=lock['sha256']:raise ValueError('Locked model integrity failure')
    return joblib.load(path)
